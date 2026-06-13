from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.ingestion import build_experiment_chunks, load_chunks
from api.vector_search import rank_chunks_by_similarity


EVAL_DATASET_PATH = PROJECT_ROOT / "data" / "eval" / "retrieval_eval.json"
EVAL_REPORTS_DIR = PROJECT_ROOT / "data" / "eval" / "reports"
DEFAULT_TOP_K = 3
EVAL_MODES = ("tfidf", "embeddings", "auto")
CHUNKING_CONFIGS = (
    {"label": "default_80_20", "chunk_size_words": 80, "chunk_overlap_words": 20},
    {"label": "small_50_10", "chunk_size_words": 50, "chunk_overlap_words": 10},
    {"label": "large_120_30", "chunk_size_words": 120, "chunk_overlap_words": 30},
)


def _load_eval_dataset(dataset_path: Path) -> list[dict[str, str]]:
    with dataset_path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def _match_rank(
    question: str,
    expected_document_prefix: str,
    top_k: int,
    mode: str,
    chunks,
) -> tuple[int | None, float]:
    ranked_hits = rank_chunks_by_similarity(
        question=question,
        chunks=chunks,
        mode=mode,
    )[:top_k]

    for index, (chunk, score) in enumerate(ranked_hits, start=1):
        if chunk.document_id.startswith(expected_document_prefix):
            return index, score

    if ranked_hits:
        _, top_score = ranked_hits[0]
        return None, float(top_score)

    return None, 0.0


def _evaluate_mode(top_k: int, mode: str, chunks) -> dict:
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
            mode=mode,
            chunks=chunks,
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
        "mode": mode,
        "top_k": top_k,
        "total_questions": total_questions,
        "hit_rate_at_1": round(hits_at_1 / total_questions, 3),
        "recall_at_k": round(hits_at_k / total_questions, 3),
        "mrr": round(reciprocal_rank_sum / total_questions, 3),
        "average_top_score": round(top_score_sum / total_questions, 3),
        "questions": per_question,
    }


def _score_key(report: dict) -> tuple[float, float, float, float]:
    return (
        report["mrr"],
        report["recall_at_k"],
        report["hit_rate_at_1"],
        report["average_top_score"],
    )


def _best_mode_report(mode_reports: list[dict]) -> dict:
    return max(mode_reports, key=_score_key)


def _best_chunking_report(chunking_reports: list[dict]) -> tuple[dict, dict]:
    best_experiment: dict | None = None
    best_mode: dict | None = None

    for experiment in chunking_reports:
        experiment_best_mode = _best_mode_report(experiment["modes"])
        if best_mode is None or _score_key(experiment_best_mode) > _score_key(best_mode):
            best_experiment = experiment
            best_mode = experiment_best_mode

    if best_experiment is None or best_mode is None:
        raise ValueError("Chunking experiments are empty.")

    return best_experiment, best_mode


def _format_mode_line(report: dict) -> str:
    return (
        f"- {report['mode']}: "
        f"Hit@1={report['hit_rate_at_1']:.3f}, "
        f"Recall@{report['top_k']}={report['recall_at_k']:.3f}, "
        f"MRR={report['mrr']:.3f}, "
        f"AvgTopScore={report['average_top_score']:.3f}"
    )


def _build_text_summary(report: dict) -> str:
    lines: list[str] = []
    lines.append("Retrieval Evaluation Summary")
    lines.append(f"Top-K: {report['top_k']}")
    lines.append("")
    lines.append("Base Retrieval Modes")
    for mode_report in report["modes"]:
        lines.append(_format_mode_line(mode_report))

    best_mode = _best_mode_report(report["modes"])
    lines.append("")
    lines.append(
        "Best Base Mode: "
        f"{best_mode['mode']} "
        f"(MRR={best_mode['mrr']:.3f}, Recall@{best_mode['top_k']}={best_mode['recall_at_k']:.3f})"
    )

    lines.append("")
    lines.append("Chunking Experiments")
    for experiment in report["chunking_experiments"]:
        lines.append(
            f"- {experiment['label']} "
            f"(chunk_size={experiment['chunk_size_words']}, overlap={experiment['chunk_overlap_words']})"
        )
        for mode_report in experiment["modes"]:
            lines.append(f"  {_format_mode_line(mode_report)}")

    best_experiment, best_experiment_mode = _best_chunking_report(report["chunking_experiments"])
    lines.append("")
    lines.append(
        "Best Chunking Setup: "
        f"{best_experiment['label']} "
        f"(chunk_size={best_experiment['chunk_size_words']}, "
        f"overlap={best_experiment['chunk_overlap_words']}, "
        f"mode={best_experiment_mode['mode']}, "
        f"MRR={best_experiment_mode['mrr']:.3f})"
    )

    lines.append("")
    lines.append("How To Read Metrics")
    lines.append("- Hit@1: how often the correct document is ranked first.")
    lines.append(f"- Recall@{report['top_k']}: how often the correct document appears in the top-k results.")
    lines.append("- MRR: rewards higher ranking of the correct document; higher is better.")
    lines.append("- AvgTopScore: average confidence score of the first result; useful as a supporting signal.")
    return "\n".join(lines)


def evaluate_retrieval(top_k: int = DEFAULT_TOP_K) -> dict:
    default_chunks = load_chunks()
    reports = [
        _evaluate_mode(top_k=top_k, mode=mode, chunks=default_chunks)
        for mode in EVAL_MODES
    ]

    chunking_reports = []
    for config in CHUNKING_CONFIGS:
        experiment_chunks = build_experiment_chunks(
            chunk_size_words=config["chunk_size_words"],
            chunk_overlap_words=config["chunk_overlap_words"],
        )
        chunking_reports.append(
            {
                "label": config["label"],
                "chunk_size_words": config["chunk_size_words"],
                "chunk_overlap_words": config["chunk_overlap_words"],
                "modes": [
                    _evaluate_mode(top_k=top_k, mode=mode, chunks=experiment_chunks)
                    for mode in EVAL_MODES
                ],
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(EVAL_DATASET_PATH),
        "top_k": top_k,
        "modes": reports,
        "chunking_experiments": chunking_reports,
    }


def _write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def save_report_artifacts(report: dict, reports_dir: Path = EVAL_REPORTS_DIR) -> dict[str, str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_report_path = reports_dir / f"retrieval_eval_{timestamp}.json"
    text_report_path = reports_dir / f"retrieval_eval_{timestamp}.txt"
    latest_json_path = reports_dir / "latest.json"
    latest_text_path = reports_dir / "latest.txt"

    text_summary = _build_text_summary(report)
    _write_json_file(json_report_path, report)
    _write_text_file(text_report_path, text_summary)
    _write_json_file(latest_json_path, report)
    _write_text_file(latest_text_path, text_summary)

    return {
        "json_report": str(json_report_path),
        "text_report": str(text_report_path),
        "latest_json": str(latest_json_path),
        "latest_text": str(latest_text_path),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval quality across retrieval modes and chunking configurations.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Top-K value used for Recall@K and ranking checks.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the evaluation report.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save timestamped and latest evaluation artifacts to disk.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    report = evaluate_retrieval(top_k=args.top_k)
    saved_paths: dict[str, str] | None = None
    if not args.no_save:
        saved_paths = save_report_artifacts(report)

    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_build_text_summary(report))

    if saved_paths:
        print("")
        print("Saved evaluation artifacts:")
        print(f"- JSON report: {saved_paths['json_report']}")
        print(f"- Text report: {saved_paths['text_report']}")
        print(f"- Latest JSON: {saved_paths['latest_json']}")
        print(f"- Latest text: {saved_paths['latest_text']}")
