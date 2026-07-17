"""Evaluate citation retrieval and abstention for the fictional-policy example."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from examples.insurance_rag.retriever import PolicyKnowledgeAssistant


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--policy",
        type=Path,
        default=PROJECT_ROOT / "examples" / "insurance_rag" / "fictional_policy.json",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=PROJECT_ROOT / "examples" / "insurance_rag" / "evaluation_questions.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "work" / "insurance_rag_evaluation.json",
    )
    parser.add_argument("--keyword-only", action="store_true")
    args = parser.parse_args()

    assistant = PolicyKnowledgeAssistant(
        args.policy, semantic_enabled=not args.keyword_only
    )
    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    results = []
    for item in questions:
        answer = assistant.ask(item["question"])
        top_id = answer["citations"][0]["document_id"] if answer["citations"] else None
        passed = (
            top_id == item["expected_document_id"]
            if item["should_answer"]
            else answer["status"] == "insufficient_evidence"
        )
        results.append({**item, "result": answer, "passed": passed})
    report = {
        "questions": len(results),
        "passed": sum(item["passed"] for item in results),
        "pass_rate": sum(item["passed"] for item in results) / len(results),
        "semantic_ready": assistant.semantic_ready,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("questions", "passed", "pass_rate", "semantic_ready")}, indent=2))
    return 0 if report["passed"] == report["questions"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
