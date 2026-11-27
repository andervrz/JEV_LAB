# Jev × CUAD · Instructions for Codex

## 1. Build and review workflow

Ander is learning software design. Keep the full architecture in mind and develop **one module per iteration**. When Ander asks for architecture or an explanation, answer at that level. When he asks to start implementation, begin with the module he specifies or default to `cases.py`.

1. **Before writing code**, name the module and describe the problem it solves, its inputs, its output, and an example Ander can check by hand. Briefly explain in Spanish why each relevant class or function belongs in the design.
2. **Implement the agreed piece.** Limit changes to the active module and the minimum tests or data needed to verify it. Use test data or a stub function for services that will be implemented later. Create other modules and their scaffolding in their own iterations.
3. **Hand over the module for review.** List the changed files in the suggested reading order. Walk through an example from input to output, explain one design decision, and give the exact command to verify it. State which tests ran, what they showed, and what remains open.
4. **Pause after the handoff.** Wait for Ander to review the code and explicitly approve moving forward. Answer questions and make requested corrections within the current module. A passing test still requires Ander's approval before the next module. If a change requires editing another approved module, explain why and agree on the scope first.

## 2. Code language and style

Write all code in English, including notebook code cells. Use English for modules, classes, functions, methods, parameters, variables, constants, tests, internal JSON fields, CLI options, messages, model instructions, and rubrics. Use `snake_case` for modules, functions, and variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Preserve Jev's external field names and the original CUAD text.

Write comments in English where they clarify a decision or constraint. An example is `# Keep the replacement in the same slot to control for position effects.` Write docstrings in English as well. Use descriptive names and small functions. Justify each class by the data or behavior it groups. Explain design decisions and review findings to Ander in Spanish.

## 3. Project goal

Build a Python tool to test whether Jev finds the clause that answers a contract question and detects insufficient evidence. The Rich CLI previews exactly what the model receives, runs one or ten cases, and inspects saved runs. The Kaggle notebook reuses the package to walk through a case, reproduce results, and chart differences. Previewing and reporting work offline and require no credentials.

## 4. Data and experiment design

Use CUAD v1 from The Atticus Project at revision `a3c393f5d103fd0c516374e4fdff676c8176dcb1` in `data/raw/CUAD_v1.json`. Document the source, revision, license, and adaptations in the README. [Dataset](https://huggingface.co/datasets/theatticusproject/cuad)

Start with one reviewed case about the notice required to prevent renewal. Expand the sample to ten cases in `data/cases.json`. Each `Case` contains an identifier, a question, an annotated passage sufficient to answer it, and three distractors with traceable sources. Verify that the distractors leave the question unanswered even when read together.

Build two `Variant` objects per case. In `with_evidence`, present the correct passage and two distractors. In `without_evidence`, replace the correct passage with the third distractor in the same slot. Vary the correct passage's position across cases in a reproducible way. Offer A, B, C, and `none` in both variants. Keep the expected label, experimental condition, and annotations in the local record. Send the model only the contract question, the three visible passages, and the instructions for both tasks.

## 5. Jev API contract

Send one JSON request per variant to `POST https://api.typesafe.ai/v1/systemone` with Bearer authentication and `Content-Type: application/json`. The entry point reads `TYPESAFE_API_KEY` from the environment and passes it to the client. Record the requested model and the model returned by the API. Use `jev-latest` initially.

Jev evaluates each typed question independently against the shared state. `choice` selects a passage. `score` measures whether the full set of passages contains enough evidence to answer the contract question. Choice confidence and the sufficiency score have distinct meanings. The following request uses fictional clauses.

```json
{
  "model": "jev-latest",
  "state": {
    "question": "How much advance notice is required to prevent renewal?",
    "passages": {
      "A": "Invoices are payable within 15 days.",
      "B": "Preventing automatic renewal requires 60 days' notice.",
      "C": "Early termination during the term requires 30 days' notice."
    }
  },
  "questions": {
    "passage": {
      "type": "choice",
      "instructions": "Select the passage that fully answers the question by itself.",
      "criteria": {"A": "Passage A", "B": "Passage B", "C": "Passage C", "none": "No passage fully answers the question"}
    },
    "sufficiency": {
      "type": "score",
      "instructions": "Rate the evidence across all passages for answering the question.",
      "criteria": ["No relevant evidence", "Relevant but incomplete evidence", "Both the notice period and its application to non-renewal are explicit"]
    }
  }
}
```

Read `answers.passage.choice` and `answers.sufficiency.score`. Validate the selected option and preserve the decimal score between 0 and 2. Record timeouts, HTTP errors, and invalid responses as failures. Treat a valid `none` as abstention. [Official documentation](https://docs.typesafe.ai/introduction/quickstart)

## 6. Modules and dependencies

Build in the order below. Deliver each row for its own review.

| Order | Module or artifact | Contract and verification |
|---|---|---|
| 1 | `src/jev_lab/cases.py` | Define `Case`, `Variant`, and `build_pair`. Build two variants from a case. Check that exactly one passage changes and that both variants contain three passages. |
| 2 | `questions.py` | Build the request from the model, question, and visible passages. Include the rubric and use the same builder for previewing and running. Verify the JSON without credentials. |
| 3 | `client.py` | Send the request with `urllib.request` and a timeout. Validate the response, keep the original response, and record token usage when available. Test success and failure with a simulated transport. |
| 4 | `experiment.py` | Coordinate the variants and the query function. Associate each attempt with the local reference and write one record per attempt to a JSONL file in `results/`, with one file per run. Verify one pair first using a simulated query. |
| 5 | `evaluation.py` | Read saved records and produce metrics and per-pair results. Test the acceptance example in section 7 offline. |
| 6 | `cli.py` | Use `argparse` and Rich to offer `preview`, `run`, and `report`. Delegate request construction, execution, and metric calculation to the corresponding modules. |
| 7 | `notebooks/cuad_jev.ipynb` | Load the same run as the CLI, reuse the evaluator, and chart per-pair differences with Matplotlib. Review the notebook separately after the CLI is approved. |

Declare dependencies in `pyproject.toml`. Use `json`, `pathlib`, and `dataclasses` from the standard library, `python-dotenv` for the local environment, and `pytest` to verify behavior. Add classes only when you can explain the concrete need they address.

## 7. Logging, metrics, and acceptance

Record the run, case, variant, and attempt identifiers, the exact request, the local expected label, the returned model, and the response and its status in JSONL. Include token usage when available. Keep credentials out of the records and identify simulations. Make retries auditable and count each variant once in the summary.

- **Correct selection.** Divide correct selections by valid responses with evidence.
- **Correct abstention.** Divide `none` selections by valid responses without evidence.
- **Change per pair.** Calculate `score_with - score_without`. Preserve negative values and zeros. Show denominators, failures, and incomplete pairs.
- **Example to check by hand.** If B is correct with evidence, Jev chooses B in both variants, and the scores are 1.8 and 0.7, the summary must show one correct selection with evidence, one abstention error, and a drop of 1.1.
- **Final acceptance.** The CLI and notebook reproduce the same report from the same JSONL file offline. Document evidence from live API calls separately.
