from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.retrieval import search


EVAL_DATASET_PATH = PROJECT_ROOT / "data" / "eval" / "retrieval_eval.json"
DEFAULT_TOP_K = 3


def _load_eval_dataset(dataset_path: Path) -> list[dict[str, str]]:
    with dataset_path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def _match_rank(question: str, expected_document_prefix: str, top_k: int) -> tuple[int | None, float]:
    result = search(question=question, top_k=top_k)

    for index, hit in enumerate(result.hits, start=1):
        if hit.document_id.startswith(expected_document_prefix):
            return index, hit.score

    return None, result.hits[0].score if result.hits else 0.0


def evaluate_retrieval(top_k: int = DEFAULT_TOP_K) -> dict:
    dataset = _load_eval_dataset(EVAL_DATASET_PATH)
    per_question: list[dict] = []

    hits_at_1 = 0
    hits_at_k = 0
    reciprocal_rank_sum = 0.0
    top_score_sum = 0.0

    for item in dataset:
        rank, top_score = _match_rank(
            question=item["question"],
            expected_document_prefix=item["expected_document_prefix"],
            top_k=top_k,
        )
        top_score_sum += top_score

        if rank == 1:
            hits_at_1 += 1
        if rank is not None:
            hits_at_k += 1
            reciprocal_rank_sum += 1.0 / rank

        per_question.append(
            {
                "id": item["id"],
                "question": item["question"],
                "expected_document_prefix": item["expected_document_prefix"],
                "match_rank": rank,
                "top_score": round(top_score, 3),
                "hit_at_1": rank == 1,
                "hit_at_k": rank is not None,
            }
        )

    total_questions = len(dataset)
    return {
        "top_k": top_k,
        "total_questions": total_questions,
        "hit_rate_at_1": round(hits_at_1 / total_questions, 3),
        "recall_at_k": round(hits_at_k / total_questions, 3),
        "mrr": round(reciprocal_rank_sum / total_questions, 3),
        "average_top_score": round(top_score_sum / total_questions, 3),
        "questions": per_question,
    }


if __name__ == "__main__":
    report = evaluate_retrieval()
    print(json.dumps(report, indent=2, ensure_ascii=False))
