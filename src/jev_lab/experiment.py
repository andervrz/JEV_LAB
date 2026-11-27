"""Run paired Jev queries and record every attempt in a run's JSONL file."""

import json
from collections.abc import Callable, Iterable
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from .cases import PASSAGE_LABELS, Case, build_pair
from .client import JevRequestError, JevResponse
from .questions import DEFAULT_MODEL, build_request


Query = Callable[[dict[str, object]], JevResponse]


def run_experiment(
    indexed_cases: Iterable[tuple[int, Case]],
    query: Query,
    *,
    simulated: bool,
    results_dir: str | Path = "results",
    model: str = DEFAULT_MODEL,
    max_attempts: int = 1,
) -> Path:
    """Run cases at their original sample indices and return the JSONL path."""
    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer.")
    if not model.strip():
        raise ValueError("The run needs a model name.")

    selected_cases = tuple(indexed_cases)
    if not selected_cases:
        raise ValueError("Select at least one case.")
    if len({case.case_id for _, case in selected_cases}) != len(selected_cases):
        raise ValueError("Case IDs must be unique within a run.")
    variants = [
        (case_index, case.evidence, variant)
        for case_index, case in selected_cases
        for variant in build_pair(case, case_index=case_index)
    ]

    run_id = uuid4().hex
    path = Path(results_dir) / f"{run_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="\n") as output:
        for case_index, evidence, variant in variants:
            request = build_request(variant, model=model)
            record = {
                "run_id": run_id,
                "case_id": variant.case_id,
                "case_index": case_index,
                "condition": variant.condition,
                "simulated": simulated,
                "request": request,
                "requested_model": model,
                "expected_choice": variant.expected_choice,
                "annotated_evidence": asdict(evidence),
                "passage_sources": {
                    label: {
                        "document_title": passage.document_title,
                        "paragraph_index": passage.paragraph_index,
                        "start_offset": passage.start_offset,
                    }
                    for label, passage in zip(PASSAGE_LABELS, variant.passages, strict=True)
                },
            }

            for attempt in range(1, max_attempts + 1):
                outcome, retryable = _query_once(query, request)
                entry = {**record, "attempt": attempt, **outcome}
                output.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + "\n")
                output.flush()
                if not retryable:
                    break

    return path


def _query_once(query: Query, request: dict[str, object]) -> tuple[dict[str, object], bool]:
    """Capture the outcome of a single query and whether it can be retried."""
    try:
        response = query(request)
    except JevRequestError as error:
        return {
            "status": error.kind,
            "returned_model": None,
            "choice": None,
            "score": None,
            "usage": None,
            "response": error.raw_response,
            "error": {"message": str(error), "http_status": error.http_status},
        }, _is_retryable(error)

    return {
        "status": "success",
        "returned_model": response.returned_model,
        "choice": response.choice,
        "score": response.score,
        "usage": response.usage,
        "response": response.raw_response,
        "error": None,
    }, False


def _is_retryable(error: JevRequestError) -> bool:
    status = error.http_status
    return error.kind in {"timeout", "network_error"} or (
        error.kind == "http_error" and status is not None and (status == 408 or 500 <= status < 600)
    )
