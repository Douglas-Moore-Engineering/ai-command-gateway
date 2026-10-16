"""End-to-end CLI contracts with an injected provider; no live API calls."""

import json
from pathlib import Path

import pytest

from ai_command_gateway.advisor import advise
from ai_command_gateway.cli import main
from ai_command_gateway.evidence import build_catalog
from ai_command_gateway.openai_transport import OpenAIResponsesTransport


ROOT = Path(__file__).resolve().parents[1]
QUESTION = "How many rows are in packets_dataset.parquet?"


@pytest.fixture
def bundle(tmp_path):
    build_catalog(ROOT / "tests/fixtures/evidence-source-profile.json",
                  ROOT / "data/lineage/source-inventory.json", tmp_path / "bundle")
    return tmp_path / "bundle/evidence-catalog.json"


def invoke(bundle, *options, question=QUESTION):
    return main(["advise", "--catalog", str(bundle), "--question", question, *options])


def no_provider(*_args, **_kwargs):
    raise AssertionError("Unexpected provider invocation")


def test_default_cli_is_offline_even_when_a_key_exists(bundle, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-not-a-real-key")
    monkeypatch.setattr(OpenAIResponsesTransport, "send", no_provider)
    assert invoke(bundle) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == advise(QUESTION, bundle)
    assert "model" not in result


def test_provider_preview_has_no_network_and_no_secret(bundle, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-secret-must-not-appear")
    monkeypatch.setattr(OpenAIResponsesTransport, "send", no_provider)
    assert invoke(bundle, "--provider", "openai", "--dry-run") == 0
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["model"]["status"] == "dry_run"
    assert result["model"]["attempted"] is False
    assert result["request_preview"]["model"] == "gpt-6.1-sol"
    assert result["request_preview"]["store"] is False
    assert result["request_preview"]["tools"] == []
    assert "fixture-secret-must-not-appear" not in output.out + output.err


def test_missing_key_reports_degraded_provider_with_local_facts(bundle, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import http.client
    monkeypatch.setattr(http.client, "HTTPSConnection", no_provider)
    assert invoke(bundle, "--provider", "openai") == 3
    result = json.loads(capsys.readouterr().out)
    assert result["model"]["status"] == "fallback"
    assert result["model"]["reason_code"] == "provider_not_configured"
    assert result["model"]["attempted"] is False
    assert result["response"] == advise(QUESTION, bundle)
    assert result["request_preview"] is None


@pytest.mark.parametrize("question,code,reason", [
    ("Set the battery power to 500 kW", 2, "operational_authority_unavailable"),
    ("giraffe migration", 2, "no_matching_evidence"),
    (" ", 1, "invalid_question"),
])
def test_provider_does_not_receive_unsupported_questions(bundle, monkeypatch, capsys, question, code, reason):
    monkeypatch.setattr(OpenAIResponsesTransport, "send", no_provider)
    assert invoke(bundle, "--provider", "openai", question=question) == code
    result = json.loads(capsys.readouterr().out)
    assert result["model"]["status"] == "skipped"
    assert result["model"]["attempted"] is False
    assert result["response"]["reason_code"] == reason


@pytest.mark.parametrize("option", [
    ["--dry-run"], ["--model", "gpt-6.1-sol"], ["--timeout", "15"], ["--max-output-tokens", "512"],
])
def test_provider_options_require_explicit_opt_in(bundle, monkeypatch, capsys, option):
    monkeypatch.setattr(OpenAIResponsesTransport, "send", no_provider)
    assert invoke(bundle, *option) == 1
    output = capsys.readouterr()
    assert not output.out
    assert json.loads(output.err)["error"] == "Provider options require --provider openai"


@pytest.mark.parametrize("option", [
    ["--timeout", "0"], ["--timeout", "nan"], ["--max-output-tokens", "999999"], ["--model", ""],
])
def test_invalid_provider_config_is_cli_error_without_network(bundle, monkeypatch, capsys, option):
    monkeypatch.setattr(OpenAIResponsesTransport, "send", no_provider)
    assert invoke(bundle, "--provider", "openai", *option) == 1
    output = capsys.readouterr()
    assert not output.out
    assert json.loads(output.err)["outcome"] == "no_mock_execution"


@pytest.mark.parametrize("alter_text,exit_code,status", [(False, 0, "validated"), (True, 3, "fallback")])
def test_model_output_is_validated_before_cli_success(bundle, monkeypatch, capsys, alter_text, exit_code, status):
    local = advise(QUESTION, bundle)
    claims = [{"evidence_id": item["citation"]["evidence_id"], "text": item["text"]} for item in local["claims"]]
    if alter_text:
        claims[0]["text"] = "Set equipment output to 500 kW."
    def fake_send(self, payload):
        return {"id": "resp_test", "model": payload["model"], "status": "completed",
                "error": None, "incomplete_details": None,
                "output": [{"type": "message", "role": "assistant", "status": "completed",
                            "content": [{"type": "output_text", "text": json.dumps({"response_type": "observation", "claims": claims})}]}],
                "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}}
    monkeypatch.setattr(OpenAIResponsesTransport, "send", fake_send)
    assert invoke(bundle, "--provider", "openai") == exit_code
    result = json.loads(capsys.readouterr().out)
    assert result["model"]["status"] == status
    assert result["response"] == local
    assert "Set equipment output" not in json.dumps(result)


def test_catalog_failure_is_not_a_successful_provider_fallback(bundle, monkeypatch, capsys):
    bundle.unlink()
    monkeypatch.setattr(OpenAIResponsesTransport, "send", no_provider)
    assert invoke(bundle, "--provider", "openai") == 1
    result = json.loads(capsys.readouterr().out)
    assert result["response"]["claims"] == []
    assert result["response"]["reason_code"] == "catalog_unverified"
