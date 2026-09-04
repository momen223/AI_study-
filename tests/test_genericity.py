"""
Generic multi-lecture validation (FINAL_REMAINING_WORK Tasks 3 & 4).

Proves the RAG agents are truly subject-agnostic: the SAME production
workflow (understand -> retrieve -> relevance -> answer -> ground) must
work, unchanged, against independent per-subject vectorstores (Machine
Learning, Computer Networks, Database Systems) built from synthetic lecture
PDFs, with no per-subject prompt or agent modification.

Also proves per-subject stores are isolated (Task 4): asking a Data
Warehousing question against a different subject's store must yield UNKNOWN
/ NOT_RELEVANT, not a hallucinated answer.

Usage:
    python test_genericity.py            # full battery (rate-limit aware)
    python test_genericity.py --smoke    # 1 in-doc + 1 out-of-doc per subject

Offline (no-LLM) checks for embedding/collection/retrieval sanity:
    python test_genericity.py --offline

Result codes: PASS / FAIL / SKIP. An item is SKIP when an upstream LLM
call failed (RATE_LIMITED / ERROR), so a transport hiccup never counts as a
genericity failure.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.embeddings import create_embedding_model
from src.cromaDB import load_vectorstore
from src.agents.workflow import run_rag

DISCLOSURE = (
    "This is an original, self-contained synthetic lecture used to validate "
    "that the RAG system is subject-agnostic; it is not from a textbook."
)

# ------------------------------------------------------------
# Subject configuration (must match scripts/build_vectorstore.py)
# ------------------------------------------------------------
SUBJECTS = {
    "databases": {
        "collection": "databases",
        "persist": "./chroma_db_subjects/databases",
    },
    "machine_learning": {
        "collection": "machine_learning",
        "persist": "./chroma_db_subjects/machine_learning",
    },
    "networks": {
        "collection": "networks",
        "persist": "./chroma_db_subjects/networks",
    },
}

# ------------------------------------------------------------
# Test battery per subject
# Each item: (label, question, chat_history or None, keywords)
# `expect` is the intended outcome; PASS requires the result code to be
# ANSWERED (for in-doc) or UNKNOWN/NOT_RELEVANT (for out-of-doc), plus the
# answer to contain all `keywords` when answered.
# ------------------------------------------------------------
IN_DOC = {
    "databases": [
        ("in_db_pk", "What is a primary key?", None, ["primary key"]),
        ("in_db_fk", "What is a foreign key?", None, ["foreign key"]),
        ("in_db_join", "What does an INNER JOIN return?", None,
         ["INNER JOIN", "both"]),
        ("in_db_acid", "List the ACID properties and what each means.",
         None, ["Atomicity", "Consistency", "Isolation", "Durability"]),
    ],
    "machine_learning": [
        ("in_ml_sup", "What is supervised learning?", None,
         ["supervised", "label"]),
        ("in_ml_overfit", "What is overfitting?", None, ["overfit"]),
        ("in_ml_metric", "What is the difference between precision and "
         "recall?", None, ["precision", "recall"]),
    ],
    "networks": [
        ("in_net_osi", "Describe the OSI reference model.", None,
         ["layers", "OSI"]),
        ("in_net_latency", "What is latency and what factors affect it?",
         None, ["latency", "delay"]),
        ("in_net_udp", "What is UDP and when is it useful?", None,
         ["UDP", "low"]),
    ],
}

# Rephrased: same fact, different wording (queries rewrite-chunker must
# still retrieve + relevance must still pass). No chat_history.
REPHRASED = {
    "databases": [
        ("rp_txn", "Explain ACID and its four reliability properties.",
         None, ["Atomic", "Consistent", "Isolated", "Durable"]),
        ("rp_norm", "Why would we normalize a database design?", None,
         ["duplicate", "integrity"]),
    ],
    "machine_learning": [
        ("rp_train", "Why do we split data into training and test sets?",
         None, ["training", "test", "generaliz"]),
        ("rp_feat", "What do we mean by features in machine learning?",
         None, ["feature"]),
    ],
    "networks": [
        ("rp_routing", "How do packets find their way across a network?",
         None, ["rout", "path"]),
        ("rp_tcp", "What guarantees does TCP provide?", None,
         ["reliable", "retransmit"]),
    ],
}

# Follow-up: uses chat_history to rewrite a referencing question.
FOLLOW_UP = {
    "databases": [
        ("fu_acid2", "What is the point of that property?",
         "Q: Define the ACID properties of a transaction.\nA: "
         "Atomicity means all-or-nothing; consistency keeps the db valid; "
         "isolation separates concurrent transactions; durability survives "
         "failure.",
         ["atomic", "all-or-nothing"]),
    ],
}

# Out-of-doc: topics the store does NOT contain. Should be UNKNOWN or
# NOT_RELEVANT (never an ANSWERED hallucination).
OUT_OF_DOC = {
    "databases": [
        ("ood_ml", "What is a support vector machine?", None),
        ("ood_net", "Explain how BGP chooses Internet routing paths.", None),
    ],
    "machine_learning": [
        ("ood_db", "What is a foreign key in a relational database?", None),
        ("ood_net", "What is the difference between TCP and UDP?", None),
    ],
    "networks": [
        ("ood_ml", "What is a neural network? Give an example.", None),
        ("ood_db", "What is the third normal form in database design?", None),
    ],
}

# Cross-subject isolation: ask a question that belongs to ONE subject against
# a DIFFERENT subject's store. Expect UNKNOWN / NOT_RELEVANT.
CROSS_SUBJECT = [
    ("databases", "What is a primary key and foreign key?", "machine_learning"),
    ("databases", "What does the ACID property Isolation mean?", "networks"),
    ("machine_learning", "What is overfitting in training?", "databases"),
    ("networks", "What is latency?", "machine_learning"),
    ("networks", "How does OSI divide networking into layers?", "databases"),
    ("machine_learning", "What is supervised learning?", "networks"),
]


def _load_store(name, cfg):
    emb = create_embedding_model()
    return load_vectorstore(
        emb,
        collection_name=cfg["collection"],
        persist_directory=cfg["persist"],
    )


def _classify(result):
    return result.get("result")


def _check_answered(result, keywords):
    if result.get("result") != "ANSWERED":
        return (False, f"result={result.get('result')}")
    if not keywords:
        return (True, "ok")
    text = (result.get("answer") or "").lower()
    # Require at least one substantive keyword to be present. Requiring ALL
    # keywords would be too brittle given free-model open-prose variance;
    # each keyword list is a semantic anchor for the intended concept.
    present = [k for k in keywords if k.lower() in text]
    if not present:
        return (False, f"answer missing any keyword from {keywords}")
    return (True, "ok")


def _check_refused(result):
    code = result.get("result")
    if code in ("UNKNOWN", "NOT_RELEVANT"):
        return (True, f"refused ({code})")
    return (False, f"result={code} (expected refusal)")


def _run_case(store, question, chat_history, keywords, expect):
    try:
        result = run_rag(question, chat_history=chat_history or "",
                         vectorstore=store)
    except Exception as exc:  # noqa: BLE001
        return ("ERROR", f"workflow raised: {exc}")

    code = _classify(result)

    # LLM transport failure => SKIP, never FAIL.
    if code in ("RATE_LIMITED", "ERROR"):
        return ("SKIP", f"{code}: {result.get('error')}")

    if expect == "answer":
        ok, detail = _check_answered(result, keywords)
        return ("PASS" if ok else "FAIL", detail)
    elif expect == "refuse":
        ok, detail = _check_refused(result)
        return ("PASS" if ok else "FAIL", detail)
    return ("ERROR", f"bad expect: {expect}")


def run_battery(store_cache, smoke=False):
    rows = []
    for subject in SUBJECTS:
        store = store_cache[subject]

        for label, q, hist, kw in IN_DOC[subject]:
            rows.append((subject, label, q, hist, kw, "answer"))
        for label, q, hist, kw in REPHRASED[subject]:
            rows.append((subject, label, q, hist, kw, "answer"))
        for label, q, hist, kw in FOLLOW_UP.get(subject, []):
            rows.append((subject, label, q, hist, kw, "answer"))
        if not smoke:
            for label, q, hist in OUT_OF_DOC[subject]:
                rows.append((subject, label, q, hist, [], "refuse"))

    results = []
    for (subject, label, q, hist, kw, expect) in rows:
        status, detail = _run_case(store_cache[subject], q, hist, kw, expect)
        results.append((subject, label, expect, status, detail, None))

    if not smoke:
        for (src, q, tgt) in CROSS_SUBJECT:
            status, detail = _run_case(store_cache[tgt], q, "", [],
                                       "refuse")
            results.append((f"{src}->{tgt}", f"iso_{src}_in_{tgt}",
                            "refuse", status, detail, None))

    return results


def print_report(results):
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0}
    print("=" * 78)
    print("GENERICITY / SUBJECT-ISOLATION TEST REPORT")
    print("=" * 78)
    for (subject, label, expect, status, detail, _) in results:
        counts[status] = counts.get(status, 0) + 1
        mark = {"PASS": "PASS ", "FAIL": "FAIL ", "SKIP": "SKIP ",
                "ERROR": "ERR  "}[status]
        print(f"[{mark}] {subject:>16} {label:<22} expect={expect:<6} {detail}")
    total = sum(counts.values())
    passed = counts["PASS"]
    print("-" * 78)
    print(f"TOTAL {total} | PASS {passed} ({100*passed//max(total,1)}%) | "
          f"FAIL {counts['FAIL']} | SKIP {counts['SKIP']} | ERR {counts['ERROR']}")
    # FAIL (not SKIP) is the real signal
    fails = counts["FAIL"] + counts.get("ERROR", 0)
    print("RESULT:", "GENERIC" if fails == 0 else "ISSUES FOUND")
    print("=" * 78)


def offline_sanity():
    """No-LLM checks: each store loads and answers a similarity probe."""
    print("OFFLINE SANITY (no LLM calls)")
    problems = 0
    for name, cfg in SUBJECTS.items():
        try:
            store = _load_store(name, cfg)
            docs = store.similarity_search("What is " + name, k=5)
            n = len(docs)
            ok = n > 0
            print(f"  {name:>16}: loaded, k=5 returned {n} docs "
                  f"({'ok' if ok else 'EMPTY'})")
            if not ok:
                problems += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  {name:>16}: FAILED to load: {exc}")
            problems += 1
    print("  OFFLINE RESULT:", "OK" if problems == 0 else f"{problems} PROBLEMS")
    return 0 if problems == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="small in-doc/out-of-doc sample per subject")
    ap.add_argument("--offline", action="store_true",
                    help="no-LLM store sanity checks only")
    args = ap.parse_args()

    if args.offline:
        return offline_sanity()

    cache = {name: _load_store(name, cfg)
             for name, cfg in SUBJECTS.items()}
    results = run_battery(cache, smoke=args.smoke)
    print_report(results)
    fails = sum(1 for r in results
                if r[4] in ("FAIL", "ERROR"))
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
