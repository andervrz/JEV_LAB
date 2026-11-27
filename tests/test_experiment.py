import json
from pathlib import Path

import pytest

from jev_lab.cases import Case, Choice, Passage, build_pair
from jev_lab.client import JevRequestError, JevResponse
from jev_lab.experiment import run_experiment
from jev_lab.questions import build_request


@pytest.fixture
def renewal_case() -> Case:
    return Case(
        case_id="example-renewal",
        question="How much advance notice is required to prevent renewal?",
        evidence=Passage("Non-renewal requires 60 days' notice.", "Example contract", 0, 15),
        distractors=(
            Passage("Invoices are payable within 15 days.", "Example contract", 1, 0),
            Passage("A breach must be cured within 30 days.", "Example contract", 2, 0),
            Passage("The parties may amend the contract in writing.", "Example contract", 3, 7),
        ),
    )


def _response(request: dict[str, object], choice: Choice, score: float) -> JevResponse:
    usage = {"input_tokens": 120, "output_tokens": 12}
    return JevResponse(
        requested_model=str(request["model"]),
        returned_model="jev-example-version",
        choice=choice,
        score=score,
        usage=usage,
        raw_response=json.dumps(
            {
                "model": "jev-example-version",
                "answers": {"passage": {"choice": choice}, "sufficiency": {"score": score}},
                "usage": usage,
            }
        ),
    )


def _read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_run_experiment_records_both_variants_with_their_local_reference(tmp_path, renewal_case):
    results_dir = tmp_path / "results"
    observed_requests = []
    results = iter([("B", 1.8), ("B", 0.7)])

    def query(request):
        observed_requests.append(request)
        return _response(request, *next(results))

    path = run_experiment(
        [(1, renewal_case)], query, simulated=True, results_dir=results_dir, model="jev-test"
    )
    with_evidence, without_evidence = _read_records(path)

    assert list(results_dir.iterdir()) == [path]
    assert path.suffix == ".jsonl"
    assert observed_requests == [
        build_request(variant, model="jev-test")
        for variant in build_pair(renewal_case, case_index=1)
    ]
    for record, request, score in zip(
        (with_evidence, without_evidence), observed_requests, (1.8, 0.7), strict=True
    ):
        assert record["run_id"] == path.stem
        assert record["case_id"] == renewal_case.case_id
        assert record["case_index"] == 1
        assert record["attempt"] == 1
        assert record["simulated"] is True
        assert record["status"] == "success"
        assert record["request"] == request
        assert record["requested_model"] == "jev-test"
        assert record["returned_model"] == "jev-example-version"
        assert record["choice"] == "B"
        assert record["score"] == score
        response = _response(request, "B", score)
        assert record["usage"] == response.usage
        assert record["response"] == response.raw_response
        assert record["annotated_evidence"]["text"] == renewal_case.evidence.text
        assert record["annotated_evidence"]["start_offset"] == 15
        assert set(request) == {"model", "state", "questions"}
        assert set(request["state"]) == {"question", "passages"}

    assert with_evidence["condition"] == "with_evidence"
    assert with_evidence["expected_choice"] == "B"
    assert with_evidence["passage_sources"]["B"]["start_offset"] == 15
    assert without_evidence["condition"] == "without_evidence"
    assert without_evidence["expected_choice"] == "none"
    assert without_evidence["passage_sources"]["B"]["start_offset"] == 7
    without_passages = without_evidence["request"]["state"]["passages"]
    assert renewal_case.evidence.text not in without_passages.values()


def test_run_experiment_persists_failed_attempt_before_retrying(tmp_path, renewal_case):
    attempts = 0

    def query(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise JevRequestError("timeout", "The Jev request timed out.")
        if attempts == 2:
            [path] = tmp_path.glob("*.jsonl")
            [first_attempt] = _read_records(path)
            assert first_attempt["status"] == "timeout"
            assert first_attempt["request"] == request
            return _response(request, "A", 1.8)
        return _response(request, "none", 0.7)

    path = run_experiment(
        [(0, renewal_case)], query, simulated=True, results_dir=tmp_path, max_attempts=2
    )
    records = _read_records(path)

    assert [(row["condition"], row["attempt"], row["status"]) for row in records] == [
        ("with_evidence", 1, "timeout"),
        ("with_evidence", 2, "success"),
        ("without_evidence", 1, "success"),
    ]
    assert records[0]["choice"] is None
    assert records[0]["score"] is None
    assert records[2]["choice"] == "none"


def test_run_experiment_records_http_failure_and_moves_on(tmp_path, renewal_case):
    outcomes = iter([False, True])

    def query(request):
        if not next(outcomes):
            raise JevRequestError(
                "http_error", "Jev returned HTTP 401.", http_status=401, raw_response="Unauthorized"
            )
        return _response(request, "none", 0.7)

    path = run_experiment(
        [(0, renewal_case)], query, simulated=True, results_dir=tmp_path, max_attempts=3
    )
    failed, succeeded = _read_records(path)

    assert failed["status"] == "http_error"
    assert failed["attempt"] == 1
    assert failed["returned_model"] is None
    assert failed["response"] == "Unauthorized"
    assert failed["error"] == {"message": "Jev returned HTTP 401.", "http_status": 401}
    assert succeeded["condition"] == "without_evidence"
    assert succeeded["status"] == "success"


def test_run_experiment_bounds_transient_failures_per_variant(tmp_path, renewal_case):
    def query(request):
        raise JevRequestError("http_error", "Jev returned HTTP 503.", http_status=503)

    path = run_experiment(
        [(0, renewal_case)], query, simulated=True, results_dir=tmp_path, max_attempts=2
    )
    records = _read_records(path)

    assert [row["status"] for row in records] == ["http_error"] * 4
    assert [(row["condition"], row["attempt"]) for row in records] == [
        ("with_evidence", 1),
        ("with_evidence", 2),
        ("without_evidence", 1),
        ("without_evidence", 2),
    ]


def test_run_experiment_rejects_duplicate_case_ids_before_running(tmp_path, renewal_case):
    def query(request):
        pytest.fail("No query should be made for a run with duplicate case IDs.")

    with pytest.raises(ValueError, match="Case IDs must be unique"):
        run_experiment(
            [(0, renewal_case), (1, renewal_case)], query, simulated=True, results_dir=tmp_path
        )

    assert list(tmp_path.iterdir()) == []
