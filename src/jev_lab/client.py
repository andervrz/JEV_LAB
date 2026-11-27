"""Send a Jev request and validate the answers used by the lab."""

import json
from dataclasses import dataclass
from http.client import HTTPException
from typing import Literal, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .cases import PASSAGE_LABELS, Choice


SYSTEM_ONE_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_TIMEOUT = 30.0

FailureKind = Literal["timeout", "http_error", "network_error", "invalid_response"]


@dataclass(frozen=True)
class JevResponse:
    """Keep the lab's observations alongside the original response body."""

    requested_model: str
    returned_model: str
    choice: Choice
    score: float
    usage: dict[str, object] | None
    raw_response: str


class JevRequestError(Exception):
    """Report a failed attempt with its category and any available HTTP details."""

    def __init__(
        self,
        kind: FailureKind,
        message: str,
        *,
        http_status: int | None = None,
        raw_response: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.http_status = http_status
        self.raw_response = raw_response


def query_jev(
    request_body: dict[str, object],
    *,
    api_key: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> JevResponse:
    """Send one authenticated request and return its validated response."""
    requested_model = request_body.get("model")
    if not isinstance(requested_model, str) or not requested_model.strip():
        raise ValueError("The request needs a model name.")
    if not api_key or any(character.isspace() for character in api_key):
        raise ValueError("A non-empty API key without whitespace is required.")
    if not 0 < timeout < float("inf"):
        raise ValueError("The timeout must be positive and finite.")

    request = Request(
        SYSTEM_ONE_URL,
        data=json.dumps(request_body, ensure_ascii=False, allow_nan=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    request.add_unredirected_header("Authorization", f"Bearer {api_key}")

    try:
        with urlopen(request, timeout=timeout) as response:
            response_bytes = response.read()
    except HTTPError as error:
        raise JevRequestError(
            "http_error",
            f"Jev returned HTTP {error.code}.",
            http_status=error.code,
            raw_response=_read_error_body(error),
        ) from None
    except (OSError, HTTPException) as error:
        reason = error.reason if isinstance(error, URLError) else error
        if isinstance(reason, TimeoutError):
            raise JevRequestError("timeout", "The Jev request timed out.") from None
        raise JevRequestError("network_error", "The Jev connection failed.") from None

    try:
        raw_response = response_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise JevRequestError(
            "invalid_response",
            "Jev returned a body that is not UTF-8.",
            raw_response=response_bytes.decode("utf-8", errors="replace"),
        ) from None

    return _parse_response(raw_response, requested_model)


def _read_error_body(error: HTTPError) -> str | None:
    try:
        with error:
            return error.read().decode("utf-8", errors="replace")
    except (OSError, HTTPException):
        # The HTTP status is still useful when the error body cannot be read.
        return None


def _parse_response(raw_response: str, requested_model: str) -> JevResponse:
    try:
        body = json.loads(raw_response)
        returned_model = body["model"]
        choice = body["answers"]["passage"]["choice"]
        score = body["answers"]["sufficiency"]["score"]
    except (ValueError, KeyError, TypeError):
        raise JevRequestError(
            "invalid_response",
            "Jev returned invalid JSON or omitted a required field.",
            raw_response=raw_response,
        ) from None

    if not isinstance(returned_model, str) or not returned_model.strip():
        raise JevRequestError(
            "invalid_response", "Jev returned an invalid model name.", raw_response=raw_response
        )
    if choice not in (*PASSAGE_LABELS, "none"):
        raise JevRequestError(
            "invalid_response", "Jev returned an invalid passage choice.", raw_response=raw_response
        )
    if type(score) not in (int, float) or not 0 <= score <= 2:
        raise JevRequestError(
            "invalid_response",
            "Jev returned a sufficiency score outside the numeric range from 0 to 2.",
            raw_response=raw_response,
        )

    usage = body.get("usage")
    return JevResponse(
        requested_model=requested_model,
        returned_model=returned_model,
        choice=cast(Choice, choice),
        score=float(score),
        usage=usage if isinstance(usage, dict) else None,
        raw_response=raw_response,
    )
