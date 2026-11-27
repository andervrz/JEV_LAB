import json
from io import BytesIO
from pathlib import Path
from urllib.error import URLError

from jev_lab import cli, client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = PROJECT_ROOT / "data" / "cases.json"
SIMULATED_RUN = PROJECT_ROOT / "results" / "6e79a209e3464bb3be4811c2238224bc.jsonl"


def _response() -> BytesIO:
    return BytesIO(
        json.dumps(
            {
                "model": "jev-test-version",
                "answers": {"passage": {"choice": "none"}, "sufficiency": {"score": 0.7}},
                "usage": {"input_tokens": 100, "output_tokens": 10},
            }
        ).encode("utf-8")
    )


def _unexpected_call(*args, **kwargs):
    raise AssertionError("This command must not read credentials or contact Jev.")


def _read_run(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_preview_emits_only_the_requested_variant_without_credentials(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setattr(cli, "dotenv_values", _unexpected_call)
    monkeypatch.setattr(client, "urlopen", _unexpected_call)
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    _, legacy, *_ = cases
    first, second, third = legacy["distractors"]

    assert cli.main([
        "preview", "--case", legacy["case_id"], "--condition", "without_evidence",
        "--model", "jev-test-model",
    ]) == 0

    captured = capsys.readouterr()
    request = json.loads(captured.out)
    assert set(request) == {"model", "state", "questions"}
    assert request["model"] == "jev-test-model"
    assert request["state"] == {
        "question": legacy["question"],
        "passages": {"A": first["text"], "B": third["text"], "C": second["text"]},
    }
    assert captured.err == ""


def test_run_can_query_twenty_variants_from_the_default_sample(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setenv("TYPESAFE_API_KEY", "fixture-key")
    monkeypatch.setattr(cli, "dotenv_values", _unexpected_call)
    requests = []

    def open_response(request, *, timeout):
        assert request.get_header("Authorization") == "Bearer fixture-key"
        assert timeout == 30.0
        requests.append(json.loads(request.data))
        return _response()

    monkeypatch.setattr(client, "urlopen", open_response)

    assert cli.main(["run", "--count", "10", "--results-dir", str(tmp_path)]) == 0

    captured = capsys.readouterr()
    path = Path(captured.out.strip())
    records = _read_run(path)
    assert len(records) == len(requests) == 20
    assert len({record["case_id"] for record in records}) == 10
    assert [record["request"] for record in records] == requests
    assert [record["expected_choice"] for record in records[::2]] == list("ABCABCABCA")
    assert [record["condition"] for record in records] == ["with_evidence", "without_evidence"] * 10
    assert all(record["status"] == "success" and record["simulated"] is False for record in records)
    assert "fixture-key" not in path.read_text(encoding="utf-8")
    assert captured.err == ""


def test_run_loads_local_key_and_keeps_the_selected_cases_original_index(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    (tmp_path / ".env").write_text("TYPESAFE_API_KEY=fixture-local-key\n", encoding="utf-8")

    def open_response(request, *, timeout):
        assert request.get_header("Authorization") == "Bearer fixture-local-key"
        assert timeout == 2.5
        return _response()

    monkeypatch.setattr(client, "urlopen", open_response)

    assert cli.main([
        "run", "--cases", str(CASES_PATH), "--case", "legacy-education-renewal-notice",
        "--timeout", "2.5",
    ]) == 0

    path = Path(capsys.readouterr().out.strip())
    assert path.parent == Path("results")
    records = _read_run(path)
    assert [record["case_index"] for record in records] == [1, 1]
    assert [record["expected_choice"] for record in records] == ["B", "none"]


def test_run_requires_a_key_before_creating_a_run(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(client, "urlopen", _unexpected_call)

    assert cli.main(["run", "--cases", str(CASES_PATH)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "TYPESAFE_API_KEY" in captured.err
    assert not (tmp_path / "results").exists()


def test_run_prints_the_saved_path_even_when_queries_fail(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TYPESAFE_API_KEY", "fixture-key")

    def fail_to_connect(request, *, timeout):
        raise URLError(ConnectionRefusedError())

    monkeypatch.setattr(client, "urlopen", fail_to_connect)

    assert cli.main(["run", "--cases", str(CASES_PATH)]) == 1

    captured = capsys.readouterr()
    records = _read_run(Path(captured.out.strip()))
    assert [record["status"] for record in records] == ["network_error", "network_error"]
    assert "2 variant(s) failed" in captured.err


def test_report_formats_the_saved_simulation_without_credentials(monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.setattr(cli, "dotenv_values", _unexpected_call)
    monkeypatch.setattr(client, "urlopen", _unexpected_call)

    assert cli.main(["report", str(SIMULATED_RUN)]) == 0

    captured = capsys.readouterr()
    for value in ("simulated", "1/1 (100.0%)", "0/1 (0.0%)", "+1.1", "Incomplete pairs"):
        assert value in captured.out
    assert "zounds-renewal-notice" in captured.out
    assert captured.err == ""
