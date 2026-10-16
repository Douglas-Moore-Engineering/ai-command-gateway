"""Create readable offline and simulated-provider examples; no credentials/network."""
import json
from pathlib import Path
import tempfile

from ai_command_gateway.advisor import advise
from ai_command_gateway.answer_display import render_answer
from ai_command_gateway.evidence import build_catalog
from ai_command_gateway.model_advisor import advise_with_model

ROOT = Path(__file__).resolve().parents[1]
QUESTION = 'How many rows are in process_dataset.parquet?'


class SimulatedProvider:
    """Hand-authored integration fixture, not a model or model-quality result."""
    def send(self, payload):
        data = json.loads(payload['input'][0]['content'][0]['text'])
        value = {'response_type': 'observation', 'claims': data['claims'],
                 'sentences': [{'text': 'The process dataset contains 13,912 recorded rows.',
                                'evidence_ids': [c['evidence_id'] for c in data['claims']]}]}
        return {'status': 'completed', 'output': [{
            'type': 'message', 'role': 'assistant', 'status': 'completed',
            'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}


def main():
    destination = ROOT / 'outputs/answers'
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gateway-answer-example-') as directory:
        bundle = Path(directory)
        build_catalog(ROOT / 'tests/fixtures/evidence-source-profile.json',
                      ROOT / 'data/lineage/source-inventory.json', bundle)
        catalog = bundle / 'evidence-catalog.json'
        offline = render_answer(advise(QUESTION, catalog))
        result = advise_with_model(QUESTION, catalog, transport=SimulatedProvider(), explain=True)
        assert result['model']['status'] == 'validated'
        simulated = ('SIMULATED PROVIDER: hand-authored test response; no live LLM inference.\n\n'
                     + render_answer(result))
        (destination / 'offline-answer.txt').write_text(offline, encoding='utf-8')
        (destination / 'simulated-model-answer.txt').write_text(simulated, encoding='utf-8')
        print(offline)
        print(simulated)
        print(f'Saved examples: {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
