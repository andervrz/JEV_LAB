import json
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from jev_lab import client
from jev_lab.cases import Passage, Variant
from jev_lab.questions import build_request


@pytest.fixture
def request_body() -> dict[str, object]:
    return build_request(
        Variant(
            case_id="example-renewal",
            question="How much advance notice is required to prevent renewal?",
            condition="without_evidence",
            passages=(
                Passage("Invoices are payable within 15 days.", "Example contract", 0, 0),
                Passage("Changes require a written agreement.", "Example contract", 1, 0),
                Passage(
                    "The parties may extend the term by mutual consent.", "Example contract", 2, 0
                ),
            ),
            expected_choice="none",
        )
    )


@pytest.fixture
def response_body() -> dict:
    return {
        "model": "jev-example-version",
        "answers": {
            "passage": {"type": "choice", "choice": "none", "confidence": 0.95},
            "sufficiency": {"type": "score", "score": 0.7, "confidence": 0.6},
        },
        "usage": {"input_tokens": 120, "output_tokens": 12},
    }


def test_query_jev_sends_the_request_and_preserves_a_valid_abstention(
    monkeypatch, request_body, response_body
):
    raw_response = json.dumps(response_body, indent=2) + "\n"

    def open_response(request: Request, *, timeout: float) -> BytesIO:
        assert request.full_url == "https://api.typesafe.ai/v1/systemone"
        assert request.get_method() == "POST"
        assert request.get_header("Authorization") == "Bearer test-key"
        assert "Authorization" not in request.headers
        assert request.get_header("Content-type") == "application/json"
        assert json.loads(request.data) == request_body
        assert timeout == 4.5
        return BytesIO(raw_response.encode("utf-8"))

    monkeypatch.setattr(client, "urlopen", open_response)
    result = client.query_jev(request_body, api_key="test-key", timeout=4.5)

    assert result.choice == "none"
    assert result.score == 0.7
    assert result.requested_model == "jev-latest"
    assert result.returned_model == "jev-example-version"
    assert result.usage == {"input_tokens": 120, "output_tokens": 12}
    assert result.raw_response == raw_response


@pytest.mark.parametrize(("choice", "score"), [("A", 0), ("B", 1.8), ("C", 2)])
def test_query_jev_accepts_rubric_bounds_and_missing_usage(
    monkeypatch, request_body, response_body, choice, score
):
    response_body["answers"]["passage"]["choice"] = choice
    response_body["answers"]["sufficiency"]["score"] = score
    del response_body["usage"]
    body = json.dumps(response_body).encode("utf-8")
    monkeypatch.setattr(client, "urlopen", lambda *args, **kwargs: BytesIO(body))

    result = client.query_jev(request_body, api_key="test-key")

    assert result.choice == choice
    assert result.score == score
    assert result.usage is None


@pytest.mark.parametrize(
    ("failure", "kind"),
    [
        (TimeoutError(), "timeout"),
        (URLError(TimeoutError()), "timeout"),
        (URLError(ConnectionRefusedError()), "network_error"),
    ],
)
def test_query_jev_classifies_transport_failures(monkeypatch, request_body, failure, kind):
    def fail_to_connect(*args, **kwargs):
        raise failure

    monkeypatch.setattr(client, "urlopen", fail_to_connect)

    with pytest.raises(client.JevRequestError) as raised:
        client.query_jev(request_body, api_key="test-key")

    assert raised.value.kind == kind
    assert raised.value.raw_response is None


def test_query_jev_preserves_http_error_details(monkeypatch, request_body):
    raw_response = '{"message": "Rate limit exceeded"}'

    def return_http_error(request, *, timeout):
        raise HTTPError(
            request.full_url, 429, "Too Many Requests", None, BytesIO(raw_response.encode("utf-8"))
        )

    monkeypatch.setattr(client, "urlopen", return_http_error)

    with pytest.raises(client.JevRequestError) as raised:
        client.query_jev(request_body, api_key="test-key")

    assert raised.value.kind == "http_error"
    assert raised.value.http_status == 429
    assert raised.value.raw_response == raw_response


@pytest.mark.parametrize("body", [b"not JSON", b"{}", b"[]", b"\xff"])
def test_query_jev_rejects_malformed_responses(monkeypatch, request_body, body):
    monkeypatch.setattr(client, "urlopen", lambda *args, **kwargs: BytesIO(body))

    with pytest.raises(client.JevRequestError) as raised:
        client.query_jev(request_body, api_key="test-key")

    assert raised.value.kind == "invalid_response"
    assert raised.value.raw_response == body.decode("utf-8", errors="replace")


@pytest.mark.parametrize(
    ("answer", "field", "value"),
    [
        ("passage", "choice", "D"),
        ("passage", "choice", None),
        ("sufficiency", "score", -0.1),
        ("sufficiency", "score", 2.1),
        ("sufficiency", "score", "0.7"),
        ("sufficiency", "score", True),
        ("sufficiency", "score", float("nan")),
    ],
)
def test_query_jev_rejects_invalid_answers(
    monkeypatch, request_body, response_body, answer, field, value
):
    response_body["answers"][answer][field] = value
    raw_response = json.dumps(response_body)
    body = raw_response.encode("utf-8")
    monkeypatch.setattr(client, "urlopen", lambda *args, **kwargs: BytesIO(body))

    with pytest.raises(client.JevRequestError) as raised:
        client.query_jev(request_body, api_key="test-key")

    assert raised.value.kind == "invalid_response"
    assert raised.value.raw_response == raw_response
