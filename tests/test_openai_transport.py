"""Network-free verification of the optional, bounded HTTPS transport."""

import hashlib
import json
import ssl
import traceback
from types import SimpleNamespace

import pytest

from ai_command_gateway import openai_transport as transport_module
from ai_command_gateway.openai_transport import (
    OpenAIConfig, OpenAIResponsesTransport, ProviderError,
    REQUEST_MAX_BYTES, RESPONSE_MAX_BYTES,
)


SECRET = "test-key-that-must-not-escape"


class FakeResponse:
    def __init__(self, body=b'{"id":"resp_example","output":[]}', status=200,
                 content_length=None, error=None):
        self.body = body
        self.status = status
        self.content_length = content_length
        self.error = error
        self.read_sizes = []

    def getheader(self, name):
        assert name == "Content-Length"
        return self.content_length

    def read(self, size):
        self.read_sizes.append(size)
        if self.error is not None:
            raise self.error
        return self.body[:size]


class FakeConnection:
    def __init__(self, response, request_error=None, response_error=None, close_error=None):
        self.response = response
        self.request_error = request_error
        self.response_error = response_error
        self.close_error = close_error
        self.requests = []
        self.closed = 0

    def request(self, method, path, body, headers):
        self.requests.append((method, path, body, headers))
        if self.request_error is not None:
            raise self.request_error

    def getresponse(self):
        if self.response_error is not None:
            raise self.response_error
        return self.response

    def close(self):
        self.closed += 1
        if self.close_error is not None:
            raise self.close_error


@pytest.fixture
def fake_https(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    connection = FakeConnection(FakeResponse())
    calls = []

    def connect(*args, **kwargs):
        calls.append((args, kwargs))
        return connection

    monkeypatch.setattr(transport_module.http.client, "HTTPSConnection", connect)
    return connection, calls


def assert_safe_error(exc_info, expected):
    error = exc_info.value
    assert error.code == expected
    assert str(error) == expected
    assert error.args == (expected,)
    assert error.__context__ is None
    assert error.__cause__ is None
    assert SECRET not in "".join(traceback.format_exception(type(error), error, error.__traceback__))


def test_success_fixed_endpoint_tls_and_canonical_payload(fake_https, monkeypatch):
    connection, calls = fake_https
    monkeypatch.setenv("HTTPS_PROXY", "https://attacker.invalid")
    monkeypatch.setenv("HTTP_PROXY", "http://attacker.invalid")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://attacker.invalid")
    payload = {"model": "gpt-6.1-sol", "input": "caf\u00e9", "store": False}
    config = OpenAIConfig(timeout_seconds=12.5)
    client = OpenAIResponsesTransport(config)
    result = client.send(payload)
    assert result == {"id": "resp_example", "output": []}
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("api.openai.com",)
    assert kwargs["port"] == 443
    assert kwargs["timeout"] == 12.5
    assert kwargs["context"].verify_mode == ssl.CERT_REQUIRED
    assert kwargs["context"].check_hostname is True
    method, path, body, headers = connection.requests[0]
    assert (method, path) == ("POST", "/v1/responses")
    expected = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
    assert body == expected
    assert hashlib.sha256(body).hexdigest() == hashlib.sha256(expected).hexdigest()
    assert headers == {"Authorization": "Bearer " + SECRET,
                       "Content-Type": "application/json", "Accept": "application/json"}
    assert connection.response.read_sizes == [RESPONSE_MAX_BYTES + 1]
    assert connection.closed == 1
    assert SECRET not in repr(vars(client))


def test_constructor_does_not_read_credentials_or_open_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Construction must not access credentials or network.")
    monkeypatch.setattr(transport_module, "os", SimpleNamespace(
        environ=type("NoEnvironment", (), {"get": forbidden})()))
    monkeypatch.setattr(transport_module.http.client, "HTTPSConnection", forbidden)
    assert OpenAIResponsesTransport().config == OpenAIConfig()


@pytest.mark.parametrize("key", [None, "", " ", "test key", "test\r\nInjected: yes", "test\x00key",
                                  "test\x7fkey", "\u2603", "x" * 4097])
def test_missing_or_malformed_credentials_never_open_connection(fake_https, monkeypatch, key):
    connection, calls = fake_https
    if key is None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    else:
        # The real environment disallows NUL; a mapping lets validation be tested.
        monkeypatch.setattr(transport_module, "os", SimpleNamespace(environ={"OPENAI_API_KEY": key}))
    with pytest.raises(ProviderError) as error:
        OpenAIResponsesTransport().send({})
    assert_safe_error(error, "provider_not_configured")
    assert not calls
    assert not connection.requests


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308, 400, 401, 429, 500, 503])
def test_http_failures_do_not_read_bodies_redirect_or_retry(fake_https, status):
    connection, calls = fake_https
    connection.response = FakeResponse(body=SECRET.encode(), status=status)
    with pytest.raises(ProviderError) as error:
        OpenAIResponsesTransport().send({})
    assert_safe_error(error, "provider_http_error")
    assert len(calls) == len(connection.requests) == 1
    assert connection.response.read_sizes == []
    assert connection.closed == 1


@pytest.mark.parametrize("stage,exception,code", [
    ("request", TimeoutError(SECRET), "provider_timeout"),
    ("response", TimeoutError(SECRET), "provider_timeout"),
    ("read", TimeoutError(SECRET), "provider_timeout"),
    ("request", OSError(SECRET), "provider_unavailable"),
    ("response", transport_module.http.client.HTTPException(SECRET), "provider_unavailable"),
    ("read", ssl.SSLError(SECRET), "provider_unavailable"),
    ("request", RuntimeError(SECRET), "provider_unavailable"),
])
def test_transport_errors_are_redacted_and_connection_closed(fake_https, stage, exception, code):
    connection, calls = fake_https
    if stage == "read":
        connection.response.error = exception
    else:
        setattr(connection, stage + "_error", exception)
    with pytest.raises(ProviderError) as error:
        OpenAIResponsesTransport().send({})
    assert_safe_error(error, code)
    assert connection.closed == 1
    assert len(calls) == 1


def test_connection_creation_failure_is_redacted(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    def fail(*args, **kwargs):
        raise OSError(SECRET)
    monkeypatch.setattr(transport_module.http.client, "HTTPSConnection", fail)
    with pytest.raises(ProviderError) as error:
        OpenAIResponsesTransport().send({})
    assert_safe_error(error, "provider_unavailable")


def test_close_error_does_not_leak_or_replace_success(fake_https):
    connection, _ = fake_https
    connection.close_error = RuntimeError(SECRET)
    assert OpenAIResponsesTransport().send({})["id"] == "resp_example"
    assert connection.closed == 1


@pytest.mark.parametrize("body", [
    b'{"x":1,"x":2}', b'{"nested":{"x":1,"x":2}}', b'{"x":NaN}',
    b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e999}', b'{"x":-1e999}',
    b'[]', b'null', b'"string"', b'42', b'', b'{} trailing', b'{"x":}',
    b'{"x":"\xff"}', b'\xef\xbb\xbf{}', b'{"x":"\\ud800"}',
    b'{"\\udfff":0}', b'{"x":' + b'1' * 129 + b'}',
    b'{"x":' + b'[' * 65 + b'0' + b']' * 65 + b'}',
    b'[' * 100000,
], ids=lambda body: "json-" + hashlib.sha256(body).hexdigest()[:8])
def test_invalid_response_json_is_rejected(fake_https, body):
    connection, _ = fake_https
    connection.response = FakeResponse(body=body)
    with pytest.raises(ProviderError) as error:
        OpenAIResponsesTransport().send({})
    assert_safe_error(error, "provider_invalid_response")
    assert connection.closed == 1


def test_brackets_and_escapes_in_strings_do_not_count_as_depth(fake_https):
    connection, _ = fake_https
    value = '[]{}"\\' * 100
    connection.response = FakeResponse(body=json.dumps({"text": value, "emoji": "\U0001f600"}).encode())
    assert OpenAIResponsesTransport().send({}) == {"text": value, "emoji": "\U0001f600"}


@pytest.mark.parametrize("length", [str(RESPONSE_MAX_BYTES + 1), "-1", "1, 1", "garbage", "", "1.0", "1e6", "1" * 100])
def test_invalid_or_oversized_declared_response_length_not_read(fake_https, length):
    connection, _ = fake_https
    connection.response = FakeResponse(content_length=length)
    with pytest.raises(ProviderError) as error:
        OpenAIResponsesTransport().send({})
    assert_safe_error(error, "provider_invalid_response")
    assert not connection.response.read_sizes
    assert connection.closed == 1


def test_truncated_content_length_rejected(fake_https):
    connection, _ = fake_https
    connection.response = FakeResponse(body=b'{}', content_length="3")
    with pytest.raises(ProviderError) as error:
        OpenAIResponsesTransport().send({})
    assert_safe_error(error, "provider_invalid_response")


def test_exact_response_cap_accepted_but_larger_body_rejected(fake_https):
    connection, _ = fake_https
    body = b'{"x":"' + b'x' * (RESPONSE_MAX_BYTES - 8) + b'"}'
    assert len(body) == RESPONSE_MAX_BYTES
    connection.response = FakeResponse(body=body, content_length=str(len(body)))
    assert len(OpenAIResponsesTransport().send({})["x"]) == RESPONSE_MAX_BYTES - 8
    connection.response = FakeResponse(body=body + b' ')
    with pytest.raises(ProviderError) as error:
        OpenAIResponsesTransport().send({})
    assert_safe_error(error, "provider_invalid_response")
    assert connection.response.read_sizes == [RESPONSE_MAX_BYTES + 1]


def test_request_cap_accounts_for_json_and_unicode_escaping(fake_https):
    connection, calls = fake_https
    client = OpenAIResponsesTransport()
    client.send({"x": "x" * (REQUEST_MAX_BYTES - 8)})
    assert len(connection.requests[0][2]) == REQUEST_MAX_BYTES
    for payload in ({"x": "x" * (REQUEST_MAX_BYTES - 7)}, {"x": "\u2603" * 12000},
                    {"x": "x" * (REQUEST_MAX_BYTES + 1)}, {"x": [0] * (REQUEST_MAX_BYTES + 1)}):
        with pytest.raises(ProviderError) as error:
            client.send(payload)
        assert_safe_error(error, "provider_request_too_large")
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [[], None, "{}", {1: "bad"}, {"x": float("nan")},
                                     {"x": float("inf")}, {"x": object()}, {"x": (1, 2)},
                                     {"x": 10 ** 200}, {"x": "\ud800"}, {"\udfff": 0}])
def test_invalid_request_rejected_before_network(fake_https, payload):
    connection, calls = fake_https
    with pytest.raises(ProviderError) as error:
        OpenAIResponsesTransport().send(payload)
    assert_safe_error(error, "provider_invalid_request")
    assert not calls


def test_circular_and_deep_request_rejected_before_network(fake_https):
    connection, calls = fake_https
    circular = {}
    circular["x"] = circular
    deep = {}
    for _ in range(70):
        deep = {"x": deep}
    for payload in (circular, deep):
        with pytest.raises(ProviderError) as error:
            OpenAIResponsesTransport().send(payload)
        assert_safe_error(error, "provider_invalid_request")
    assert not calls


@pytest.mark.parametrize("field,value", [
    ("model", ""), ("model", "x" * 129), ("model", "model\nheader"), ("model", "\u2603"),
    ("model", True), ("timeout_seconds", 0), ("timeout_seconds", 61), ("timeout_seconds", True),
    ("timeout_seconds", "30"), ("timeout_seconds", float("nan")), ("timeout_seconds", float("inf")),
    ("timeout_seconds", 10 ** 1000), ("max_output_tokens", 255), ("max_output_tokens", 4097),
    ("max_output_tokens", 1024.0), ("max_output_tokens", True),
])
def test_config_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        OpenAIConfig(**{field: value})


def test_config_bounds_and_fixed_errors():
    assert OpenAIConfig(timeout_seconds=1, max_output_tokens=256).timeout_seconds == 1
    assert OpenAIConfig(timeout_seconds=60, max_output_tokens=4096).max_output_tokens == 4096
    assert ProviderError(SECRET).code == "provider_unavailable"
    assert ProviderError([]).code == "provider_unavailable"
    with pytest.raises(ValueError):
        OpenAIResponsesTransport({})
