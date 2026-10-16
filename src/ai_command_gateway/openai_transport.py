"""Optional, bounded HTTPS transport for a single OpenAI Responses request.

Importing this module and constructing a transport do not inspect credentials or
make network requests. The caller supplies the complete JSON payload. This layer
does not interpret model claims or grant any command authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import math
import os
import re
import ssl
from typing import Any


REQUEST_MAX_BYTES = 64 * 1024
RESPONSE_MAX_BYTES = 1024 * 1024
_MAX_JSON_DEPTH = 64
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z", re.ASCII)
_ERROR_CODES = frozenset({
    "provider_not_configured", "provider_timeout", "provider_http_error",
    "provider_unavailable", "provider_invalid_response",
    "provider_request_too_large", "provider_invalid_request",
})


class ProviderError(Exception):
    """A fixed error code with no provider body, credential, or exception text."""

    def __init__(self, code: str):
        self.code = code if type(code) is str and code in _ERROR_CODES else "provider_unavailable"
        super().__init__(self.code)


@dataclass(frozen=True)
class OpenAIConfig:
    """Runtime bounds; timeout_seconds is the HTTPS socket-operation timeout."""

    model: str = "gpt-6.1-sol"
    timeout_seconds: float = 30
    max_output_tokens: int = 2048

    def __post_init__(self) -> None:
        if type(self.model) is not str or _MODEL.fullmatch(self.model) is None:
            raise ValueError("Invalid OpenAI model identifier.")
        if (type(self.timeout_seconds) not in (int, float)
                or not 1 <= self.timeout_seconds <= 60
                or not math.isfinite(self.timeout_seconds)):
            raise ValueError("OpenAI timeout must be between 1 and 60 seconds.")
        if (type(self.max_output_tokens) is not int
                or not 256 <= self.max_output_tokens <= 4096):
            raise ValueError("OpenAI output token limit must be between 256 and 4096.")


def _request_bytes(payload: dict[str, Any]) -> tuple[bytes | None, str | None]:
    """Reject non-JSON Python objects before calling their conversion methods."""
    if type(payload) is not dict:
        return None, "provider_invalid_request"
    stack = [(payload, 0)]
    nodes = 0
    characters = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > _MAX_JSON_DEPTH:
            return None, "provider_invalid_request"
        if nodes > REQUEST_MAX_BYTES:
            return None, "provider_request_too_large"
        if type(item) is dict:
            if len(item) > REQUEST_MAX_BYTES:
                return None, "provider_request_too_large"
            for key, value in item.items():
                if type(key) is not str:
                    return None, "provider_invalid_request"
                if any(0xD800 <= ord(char) <= 0xDFFF for char in key):
                    return None, "provider_invalid_request"
                characters += len(key)
                stack.append((value, depth + 1))
        elif type(item) is list:
            if len(item) > REQUEST_MAX_BYTES:
                return None, "provider_request_too_large"
            stack.extend((value, depth + 1) for value in item)
        elif type(item) is str:
            if any(0xD800 <= ord(char) <= 0xDFFF for char in item):
                return None, "provider_invalid_request"
            characters += len(item)
        elif type(item) is float:
            if not math.isfinite(item):
                return None, "provider_invalid_request"
        elif type(item) is int:
            if item.bit_length() > 426:
                return None, "provider_invalid_request"
        elif item is not None and type(item) is not bool:
            return None, "provider_invalid_request"
        if characters > REQUEST_MAX_BYTES:
            return None, "provider_request_too_large"
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None, "provider_invalid_request"
    if len(encoded) > REQUEST_MAX_BYTES:
        return None, "provider_request_too_large"
    return encoded, None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite JSON number.")
    return result


def _bounded_int(value: str) -> int:
    if len(value.lstrip("-")) > 128:
        raise ValueError("Oversized JSON integer.")
    return int(value)


def _reject_constant(value: str) -> None:
    raise ValueError("Invalid JSON constant.")


def _response_json(body: bytes) -> dict[str, Any] | None:
    try:
        decoded = body.decode("utf-8")
        # Bound nesting before parsing, including malformed, deeply nested JSON.
        depth = 0
        quoted = False
        escaped = False
        for character in decoded:
            if quoted:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    quoted = False
            elif character == '"':
                quoted = True
            elif character in "[{":
                depth += 1
                if depth > _MAX_JSON_DEPTH:
                    return None
            elif character in "]}":
                depth -= 1
                if depth < 0:
                    return None
        parsed = json.loads(decoded, object_pairs_hook=_unique_object,
                            parse_float=_finite_float, parse_int=_bounded_int,
                            parse_constant=_reject_constant)
        stack = [parsed]
        while stack:
            value = stack.pop()
            if type(value) is dict:
                stack.extend(value.keys())
                stack.extend(value.values())
            elif type(value) is list:
                stack.extend(value)
            elif type(value) is str and any(0xD800 <= ord(char) <= 0xDFFF for char in value):
                return None
        return parsed if type(parsed) is dict else None
    except (UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
        return None


class OpenAIResponsesTransport:
    """Send once to the fixed HTTPS endpoint; never follow redirects or retry.

    ``http.client`` does not consume environment proxy settings. Its HTTPS
    connection receives a fresh default TLS context with certificate and
    hostname verification enabled. Error response bodies are never read.
    """

    def __init__(self, config: OpenAIConfig | None = None):
        if config is not None and type(config) is not OpenAIConfig:
            raise ValueError("OpenAI transport requires OpenAIConfig.")
        self.config = config if config is not None else OpenAIConfig()

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        encoded, error_code = _request_bytes(payload)
        if error_code is not None:
            raise ProviderError(error_code)
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if (not api_key or len(api_key) > 4096 or not api_key.isascii()
                or any(ord(character) <= 32 or ord(character) == 127
                       for character in api_key)):
            raise ProviderError("provider_not_configured")

        connection = None
        result = None
        try:
            connection = http.client.HTTPSConnection(
                "api.openai.com", port=443, timeout=self.config.timeout_seconds,
                context=ssl.create_default_context(),
            )
            connection.request("POST", "/v1/responses", body=encoded, headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            })
            response = connection.getresponse()
            if type(response.status) is not int or not 200 <= response.status < 300:
                error_code = "provider_http_error"
            else:
                content_length = response.getheader("Content-Length")
                if content_length is not None and (
                    type(content_length) is not str
                    or re.fullmatch(r"[0-9]{1,10}", content_length) is None
                    or int(content_length) > RESPONSE_MAX_BYTES
                ):
                    error_code = "provider_invalid_response"
                else:
                    body = response.read(RESPONSE_MAX_BYTES + 1)
                    if (type(body) is not bytes or len(body) > RESPONSE_MAX_BYTES
                            or content_length is not None and len(body) != int(content_length)):
                        error_code = "provider_invalid_response"
                    else:
                        result = _response_json(body)
                        if result is None:
                            error_code = "provider_invalid_response"
        except TimeoutError:
            error_code = "provider_timeout"
        except Exception:
            # Provider and transport exception text can contain request details.
            error_code = "provider_unavailable"
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
        # Raise outside exception handlers so the original exception is neither
        # a cause nor context on the safe, caller-visible ProviderError.
        if error_code is not None:
            raise ProviderError(error_code)
        if result is None:
            raise ProviderError("provider_invalid_response")
        return result
