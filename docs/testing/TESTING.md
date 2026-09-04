# Testing

This project is verified by a set of **self-contained** test batteries. They
exercise the production workflow (the exact code paths the API and UI call) and
are honest about model nondeterminism.

## 1. Unit / ingestion test (no LLM required)

`tests/test_ingestion.py` validates the PDF → pages → chunks → embeddings path
end to end using a tiny synthetic PDF generated on the fly, so it needs no
bundled data and no machine-specific paths.

```bash
python tests/test_ingestion.py
```

Expected: every assertion `[PASS]`, final `RESULT: OK`. Covers load, chunking,
and embedding dimensions/counts.

## 2. Live LLM test batteries

`run_tests.py` runs the full live suite against the production workflow. It
covers: retrieval, unknown-rejection, definitions, examples, follow-ups,
anti-hallucination, context-conflict, and answer quality. Each test reports
`QUESTION / REWRITTEN / RETRIEVAL / BEST SCORE / ANSWER / GROUNDING / RESULT`,
and the final summary prints `TOTAL / PASSED / FAILED / ERRORS / ACCURACY` plus
per-category accuracies.

```bash
python run_tests.py
```

`test_genericity.py` runs the **same production workflow, unchanged**, against
independent per-subject vector stores (Machine Learning, Computer Networks,
Database Systems) built from synthetic lecture PDFs. It checks that in-document
questions are answered, rephrased questions still retrieve, follow-ups resolve
references, and out-of-document / cross-subject questions are refused.

```bash
python scripts/build_vectorstore.py --all   # build all demo stores first
python test_genericity.py
```

## 2b. Quiz / MCQ generation battery

`tests/test_quizzes.py` verifies the MCQ generator deterministically, then
optionally against a live provider:

- **Parsing & normalization** — JSON-array extraction from fenced/prose output,
  exactly-4-option enforcement, correct-letter mapping, invalid-input rejection.
- **Grounding** — a `FakePassLLM` verifier yields `ok`, a `FakeRaisingLLM`
  yields a `llm_error` dict, unsupported correct answers / explanations and
  non-verbatim evidence are rejected.
- **Structural validation & dedup** — duplicate options, invalid difficulty,
  empty explanations, and near-duplicate questions are rejected.
- **Lifecycle & scoring** — save/reload, CREATED → STARTED → COMPLETED /
  PARTIAL, correct-map accuracy, timer expirations, persistence, deletion.
- **Generation loop** — candidate parsing and transient-provider retries.
- **API routing** — a Flask `test_client` for create / start / submit / result /
  delete, including hidden answers pre-submit, 404 handling, and server-side
  scores.
- **Live E2E** — guarded by provider keys (skipped, not failed, when absent):
  generates a real quiz and asserts structural self-consistency.

```bash
python tests/test_quizzes.py
# requires `src` importable; run from the repo root with the project on the path,
# e.g. PYTHONPATH=. python tests/test_quizzes.py
```

The battery guarantees the safety properties: correct answers never leak before
submission, unsupported (hallucinated) questions are dropped, no near-duplicates
survive, and a `PARTIAL` result always carries a structured reason.

## 3. Interpreting failures honestly

- **Errors** are counted **separately** from failures (rate limits / provider
  outages are not scored as answer failures).
- Free-tier answer/grounding models are nondeterministic on some in-scope
  questions: the same `RELEVANT` question can occasionally return `UNKNOWN` or
  fail grounding twice even though the context is present. This is a
  **model-reliability** issue, not a system bug — the corrective passes
  (re-generation on `UNKNOWN`-with-relevant-context and on grounding `FAIL`)
  reduce but do not fully remove it.
- Safety guarantees hold regardless: an answer is **never** emitted without
  passing grounding, and off-topic questions are always refused.

## 4. Verification checks

- Prompts contain no subject-specific constants (the suite greps `src/`).
- All parameters come from `src/config.py`.
- See [Benchmark](BENCHMARK.md) for measured results.
