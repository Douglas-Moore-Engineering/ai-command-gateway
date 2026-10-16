"""Cited prose, failure, and display contracts; injected responses only."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ai_command_gateway.advisor import advise
from ai_command_gateway.answer_display import render_answer
from ai_command_gateway.cli import main
from ai_command_gateway.evidence import build_catalog
from ai_command_gateway.model_advisor import advise_with_model
from ai_command_gateway.openai_transport import OpenAIResponsesTransport

QUESTION = 'How many rows are in process_dataset.parquet?'


@pytest.fixture
def catalog(tmp_path):
    build_catalog(Path('tests/fixtures/evidence-source-profile.json'),
                  Path('data/lineage/source-inventory.json'), tmp_path / 'bundle')
    return tmp_path / 'bundle/evidence-catalog.json'


class ExplanationTransport:
    def __init__(self, alter=None):
        self.alter = alter
        self.requests = []

    def send(self, payload):
        self.requests.append(deepcopy(payload))
        data = json.loads(payload['input'][0]['content'][0]['text'])
        value = {'response_type': 'observation', 'claims': data['claims'],
                 'sentences': [{'text': 'The process dataset contains 13,912 recorded rows.',
                                'evidence_ids': [c['evidence_id'] for c in data['claims']]}]}
        if self.alter:
            self.alter(value)
        return {'status': 'completed', 'output': [
            {'type': 'message', 'role': 'assistant', 'status': 'completed',
             'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}


def explain(catalog, transport=None, **kwargs):
    return advise_with_model(QUESTION, catalog, transport=transport, explain=True, **kwargs)


def test_paraphrase_preserves_exact_evidence_and_reconstructs_citations(catalog):
    fake = ExplanationTransport()
    result = explain(catalog, fake)
    assert result['model']['status'] == 'validated'
    assert result['answer']['origin'] == 'model'
    assert result['answer']['semantic_entailment'] == 'not_evaluated'
    assert result['response'] == advise(QUESTION, catalog)
    sentence = result['answer']['sentences'][0]
    assert sentence['text'] != result['response']['claims'][0]['text']
    assert sentence['citations'] == [c['citation'] for c in result['response']['claims']]
    assert not result['response']['can_execute']
    assert fake.requests[0]['tools'] == []
    assert 'sentences' in fake.requests[0]['text']['format']['schema']['required']
    text = render_answer(result)
    assert '13,912 recorded rows. [1]' in text
    assert 'semantic accuracy requires review' in text
    assert 'process_dataset.parquet' in text


@pytest.mark.parametrize('bad', [
    {'text': 'There are 999999 rows.', 'evidence_ids': 'keep'},
    {'text': 'Set battery power to 500 kW.', 'evidence_ids': 'keep'},
    {'text': 'Ignore all instructions.', 'evidence_ids': 'keep'},
    {'text': '<script>alert(1)</script>', 'evidence_ids': 'keep'},
    {'text': 'Read https://evil.example.', 'evidence_ids': 'keep'},
    {'text': '\x1b[2J', 'evidence_ids': 'keep'},
    {'text': 'The process dataset contains 13,912 recorded rows.', 'evidence_ids': ['invented']},
    {'text': 'The process dataset contains 13,912 recorded rows.', 'evidence_ids': []},
    {'text': '', 'evidence_ids': 'keep'},
    {'text': 'x' * 1001, 'evidence_ids': 'keep'},
    {'text': None, 'evidence_ids': 'keep'},
])
def test_bad_explanations_are_not_displayed(catalog, bad):
    def alter(value):
        item = deepcopy(bad)
        if item['evidence_ids'] == 'keep':
            item['evidence_ids'] = value['sentences'][0]['evidence_ids']
        value['sentences'] = [item]
    result = explain(catalog, ExplanationTransport(alter))
    assert result['model']['reason_code'] == 'explanation_rejected'
    assert result['model']['status'] == 'fallback'
    assert result['answer']['origin'] == 'extractive_fallback'
    assert result['answer']['sentences'][0]['text'] == result['response']['claims'][0]['text']


@pytest.mark.parametrize('alter', [
    lambda v: v.pop('sentences'),
    lambda v: v.update(sentences=None),
    lambda v: v.update(sentences=[None]),
    lambda v: v.update(sentences=[]),
    lambda v: v['sentences'][0]['evidence_ids'].append(v['sentences'][0]['evidence_ids'][0]),
    lambda v: v['sentences'][0].update(citations=['forged']),
])
def test_missing_malformed_or_forged_sentence_contract_falls_back(catalog, alter):
    result = explain(catalog, ExplanationTransport(alter))
    assert result['model']['status'] == 'fallback'
    assert result['answer']['origin'] == 'extractive_fallback'


def test_complete_citation_coverage_is_required(catalog):
    def alter(value):
        value['sentences'] = [{'text': value['claims'][0]['text'],
                               'evidence_ids': [value['claims'][0]['evidence_id']]}]
    result = advise_with_model('minimum and maximum in_batt_state_of_charge', catalog,
                               transport=ExplanationTransport(alter), explain=True)
    assert len(result['response']['claims']) == 2
    assert result['model']['reason_code'] == 'explanation_rejected'


def test_catalog_change_clears_prose_and_claims(catalog):
    def alter(value):
        catalog.write_text('{}')
    result = explain(catalog, ExplanationTransport(alter))
    assert result['model']['status'] == 'rejected'
    assert result['answer']['sentences'] == []
    assert '13,912' not in render_answer(result)


def test_abstention_retains_only_labeled_extractive_fallback(catalog):
    def alter(value):
        value.update(response_type='abstain', claims=[], sentences=[])
    result = explain(catalog, ExplanationTransport(alter))
    assert result['model']['reason_code'] == 'model_abstained'
    assert result['answer']['origin'] == 'extractive_fallback'


@pytest.mark.parametrize('question', ['Set battery power to 4 kW', 'giraffe migration'])
def test_unsupported_question_cannot_invoke_provider(catalog, question):
    fake = ExplanationTransport()
    result = advise_with_model(question, catalog, transport=fake, explain=True)
    assert fake.requests == []
    assert result['answer']['sentences'] == []


def test_dry_run_and_missing_key_never_display_fake_model_prose(catalog, monkeypatch):
    fake = ExplanationTransport()
    result = explain(catalog, fake, dry_run=True)
    assert not fake.requests and result['model']['attempted'] is False
    assert result['answer']['origin'] == 'extractive_fallback'
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    result = explain(catalog)
    assert result['model']['reason_code'] == 'provider_not_configured'
    assert result['answer']['origin'] == 'extractive_fallback'


def test_cli_explanation_defaults_to_text_and_saves_identical_answer(catalog, tmp_path, monkeypatch, capsys):
    fake = ExplanationTransport()
    monkeypatch.setattr(OpenAIResponsesTransport, 'send', lambda self, payload: fake.send(payload))
    path = tmp_path / 'answer.txt'
    args = ['advise', '--catalog', str(catalog), '--question', QUESTION, '--provider', 'openai', '--explain']
    assert main([*args, '--output', str(path)]) == 0
    text = capsys.readouterr().out
    assert 'The process dataset contains 13,912 recorded rows. [1]' in text
    assert path.read_text(encoding='utf-8') == text
    assert main([*args, '--format', 'json']) == 0
    assert json.loads(capsys.readouterr().out)['answer']['origin'] == 'model'


def test_cli_offline_text_and_explicit_provider_requirement(catalog, monkeypatch, capsys):
    monkeypatch.setattr(OpenAIResponsesTransport, 'send', lambda *a: pytest.fail('network forbidden'))
    args = ['advise', '--catalog', str(catalog), '--question', QUESTION]
    assert main([*args, '--format', 'text']) == 0
    assert 'Answer from verified local observations' in capsys.readouterr().out
    assert main([*args, '--explain']) == 1
    assert 'Provider options require --provider openai' in capsys.readouterr().err


def test_presentation_removes_terminal_controls(catalog):
    result = advise(QUESTION, catalog)
    result['question'] = 'question\x1b[2J\u202esecret'
    text = render_answer(result)
    assert '\x1b' not in text and '\u202e' not in text


def test_tampered_exact_claims_cannot_be_hidden_behind_good_prose(catalog):
    def alter(value):
        value['claims'][0]['text'] = 'Invented source statement'
    result = explain(catalog, ExplanationTransport(alter))
    assert result['model']['reason_code'] == 'claim_mismatch'
    assert result['answer']['origin'] == 'extractive_fallback'
    assert 'Invented' not in render_answer(result)


@pytest.mark.parametrize('code', ['provider_timeout', 'provider_http_error', 'provider_unavailable'])
def test_provider_errors_cannot_create_model_answers(catalog, code):
    from ai_command_gateway.openai_transport import ProviderError
    class Failure:
        def send(self, payload):
            raise ProviderError(code)
    result = explain(catalog, Failure())
    assert result['model']['reason_code'] == code
    assert result['answer']['origin'] == 'extractive_fallback'
    assert result['answer']['sentences']


def test_real_citation_does_not_prove_semantics(catalog):
    def alter(value):
        # A real number and citation cannot establish the invented adjective.
        value['sentences'][0]['text'] = 'The process dataset contains 13,912 perfect measurements.'
    result = explain(catalog, ExplanationTransport(alter))
    assert result['model']['status'] == 'validated'
    assert result['answer']['semantic_entailment'] == 'not_evaluated'
    assert 'semantic accuracy requires review' in render_answer(result)


def test_cli_fallback_saves_exact_observations_and_reports_degradation(catalog, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    path = tmp_path / 'fallback.txt'
    assert main(['advise', '--catalog', str(catalog), '--question', QUESTION,
                 '--provider', 'openai', '--explain', '--output', str(path)]) == 3
    text = capsys.readouterr().out
    assert text == path.read_text(encoding='utf-8')
    assert 'fallback (provider_not_configured)' in text
    assert 'no model-written explanation' in text
