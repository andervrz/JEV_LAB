# Jev × CUAD

A Python lab for evaluating evidence selection and abstention on contract questions. It uses the TypeSafe System One API and ten annotated cases from CUAD v1 about the notice required to prevent automatic renewal. [TypeSafe API reference](https://docs.typesafe.ai/api/system-one)

## Experimental design

Each case contains a contract question, an annotated answer passage, and three distractors from the same contract. The lab sends two variants of the question to Jev.

| Variant | Passages | Expected choice |
| --- | --- | --- |
| `with_evidence` | The annotated passage and two distractors | The label of the annotated passage |
| `without_evidence` | The third distractor replaces the annotated passage in the same position | `none` |

Each pair shares the same question, instructions, and two distractors. The position of the annotated passage rotates among `A`, `B`, and `C` based on the case's index in the source file. Running a case individually preserves that position.

Each request sends the question and three labeled passages as shared state. Jev evaluates two questions independently.

- **Passage choice** selects `A`, `B`, or `C` if that passage answers the question on its own. It selects `none` otherwise.
- **Evidence sufficiency** assesses the three passages together on a scale from 0 to 2. The rubric anchors are no relevant evidence, relevant but incomplete evidence, and explicit support for a complete answer.

The expected choice, condition, and source annotations are recorded locally. `preview` and `run` use the same request builder.

## CLI

The project requires Python 3.10 or later. Use `uv` to install and run it. The CLI uses `argparse` for command parsing, `urllib.request` for HTTPS requests, and Rich for terminal reports.

```bash
git clone https://github.com/andervrz/JEV_LAB.git
cd JEV_LAB
uv sync
uv run jev-lab --help
```

Use `preview` to inspect a request body and `report` to read a saved run. Both commands work offline. The repository includes a simulated JSONL fixture for trying the report command.

```bash
uv run jev-lab preview --case zounds-renewal-notice --condition without_evidence
uv run jev-lab report results/6e79a209e3464bb3be4811c2238224bc.jsonl
```

To query Jev, set `TYPESAFE_API_KEY` in your environment or in a local `.env` file. `run` sends one `POST` request per variant to `https://api.typesafe.ai/v1/systemone` using `jev-latest` by default. It prints the path of the resulting JSONL file. Use `--case` to select one case by ID or `--count 10` to run the first ten cases.

```bash
uv run jev-lab run --case zounds-renewal-notice
```

One attempt per variant is the default. Increase `--max-attempts` to retry timeouts, connection failures, and HTTP 408 or 5xx responses. Each attempt is recorded before the next one begins.

## Run records and metrics

A run writes one UTF-8 JSONL file under `results/`. Each line records the run and case IDs, condition, attempt number, exact request, requested model, expected choice, passage provenance, simulation flag, and response status. Successful records include the returned model, validated choice and score, original response body, and token usage when available. Failure records retain the error category and any available HTTP details.

The evaluator uses the highest-numbered attempt for each case and condition. It reports the following metrics.

| Metric | Definition |
| --- | --- |
| Selection accuracy | Correct choices divided by valid responses with evidence |
| Abstention accuracy | Choices of `none` divided by valid responses without evidence |
| Paired score change | Sufficiency with evidence minus sufficiency without evidence for each pair with two valid scores |

The report keeps negative and zero score changes and shows the denominators, failed attempts, failed variants, and incomplete pairs. It reads the saved JSONL without contacting Jev.

## Package layout

| Module | Responsibility |
| --- | --- |
| `cases.py` | Case data, passage provenance, and deterministic variant construction |
| `questions.py` | Shared request state and the choice and score rubrics |
| `client.py` | Authenticated requests, timeouts, and response validation |
| `experiment.py` | Paired execution, retries, and JSONL logging |
| `evaluation.py` | Offline metrics and per-case comparisons |
| `cli.py` | Command-line entry points and report formatting |

The test suite uses simulated transport and covers variant construction, request serialization, response validation, retry logging, evaluation, and CLI behavior.

```bash
uv run --extra test pytest -q
```

## Data provenance

The Atticus Project publishes CUAD v1 under **CC BY 4.0**. The raw dataset included here is pinned to revision `a3c393f5d103fd0c516374e4fdff676c8176dcb1`. [Repository copy](data/raw/CUAD_v1.json) · [Pinned source](https://huggingface.co/datasets/theatticusproject/cuad/blob/a3c393f5d103fd0c516374e4fdff676c8176dcb1/CUAD_v1/CUAD_v1.json) · [Dataset card and license](https://huggingface.co/datasets/theatticusproject/cuad)

The ten-case sample uses the `Details` text from each selected CUAD question. The evidence and distractors are verbatim excerpts. Each excerpt stores its document title, paragraph index, and start offset. The distractors were selected so that, even taken together, they leave the renewal notice question unanswered. [Curated sample](data/cases.json)
