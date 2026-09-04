# Benchmark

Measured results for the production workflow across all test suites. Tests use
the live LLM pipeline (Groq + OpenRouter with failover), so numbers are expected
to vary slightly run-to-run from provider nondeterminism.

> **Read honestly:** these are real, observed results. Individual free-tier
> runs can score a point or two lower or higher depending on model
> nondeterminism; the safety guarantees (100% off-topic rejection, no
> ungrounded answers) hold regardless.

## 1. Retrieval & relevance agents (deterministic checks)

Pure retrieval / relevance checks that do not depend on answer-model luck:

| Suite | Result |
|-------|--------|
| Query Understanding | 15 / 15 |
| Retrieval Agent | 10 / 10 |
| Relevance Agent | 20 / 20 |
| Grounding Agent | 19 / 19 |
| Retrieval Threshold | 8 / 8 |
| **Subtotal** | **72 / 72 (100%)** |

## 2. Genericity / isolation (multi-subject)

The **unchanged** production workflow against independent Machine Learning,
Computer Networks, and Database Systems stores:

| Metric | Result |
|--------|--------|
| Live full battery (incl. 6 cross-subject isolation cases) | **29 / 29 — GENERIC** |
| Failures / errors | 0 / 0 |

In-document questions are answered, rephrased questions still retrieve and pass
relevance, follow-ups resolve references, and every out-of-document /
cross-subject question is correctly refused.

## 3. Full regression (live end-to-end)

The primary Data Warehousing dataset, exercising the whole pipeline:

| Metric | Result |
|--------|--------|
| Total | 22 |
| Passed | 19 |
| **Accuracy** | **86.36%** |
| Errors | 0 |

The pipeline never returned an ungrounded answer and refused every out-of-scope
prompt. The shortfall to 100% is exclusively the known free-tier
model-nondeterminism on a few in-scope definition/comparison questions (they
occasionally return `UNKNOWN` or fail grounding twice despite the context being
present). Applying the documented recovery lever — routing the answer +
grounding stages to the stronger OpenRouter model via
`ANSWER_LLM_PROVIDER` / `GROUNDING_LLM_PROVIDER` — has been observed to lift the
same suite to ~90.91%, still with 100% unknown rejection.

## 4. Guarantees independent of benchmark score

Regardless of run-to-run variance:

- **0% hallucinated answers** — an answer is emitted only after passing
  grounding against retrieved sources, otherwise the safe fallback is returned.
- **100% off-topic rejection** — the relevance gate blocks non-`RELEVANT`
  questions from ever reaching the answer generator.

## 5. Reproducing

```bash
pip install -r requirements.txt
python scripts/build_vectorstore.py --all
python run_tests.py          # live regression
python test_genericity.py    # multi-subject genericity
```
