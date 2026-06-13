from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_retrieval import EVAL_REPORTS_DIR


METRICS = ("hit_rate_at_1", "recall_at_k", "mrr", "average_top_score")
METRIC_LABELS = {
    "hit_rate_at_1": "Hit@1",
    "recall_at_k": "Recall@K",
    "mrr": "MRR",
    "average_top_score": "AvgTopScore",
}


def _load_report(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def _mode_map(report: dict) -> dict[str, dict]:
    return {item["mode"]: item for item in report.get("modes", [])}


def _chunking_map(report: dict) -> dict[str, dict]:
    return {item["label"]: item for item in report.get("chunking_experiments", [])}


def _format_delta(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.3f}"


def _mode_summary_line(before: dict, after: dict) -> str:
    metric_parts = [
        f"{METRIC_LABELS[metric]}={before[metric]:.3f}->{after[metric]:.3f} ({_format_delta(after[metric] - before[metric])})"
        for metric in METRICS
    ]
    return ", ".join(metric_parts)


def _best_mode_name(report: dict) -> str:
    best = max(
        report.get("modes", []),
        key=lambda item: (item["mrr"], item["recall_at_k"], item["hit_rate_at_1"], item["average_top_score"]),
    )
    return best["mode"]


def _best_chunking_label(report: dict) -> tuple[str, str]:
    best_label = ""
    best_mode = ""
    best_key: tuple[float, float, float, float] | None = None

    for chunking in report.get("chunking_experiments", []):
        for mode_report in chunking.get("modes", []):
            score_key = (
                mode_report["mrr"],
                mode_report["recall_at_k"],
                mode_report["hit_rate_at_1"],
                mode_report["average_top_score"],
            )
            if best_key is None or score_key > best_key:
                best_key = score_key
                best_label = chunking["label"]
                best_mode = mode_report["mode"]

    return best_label, best_mode


def build_comparison_summary(before: dict, after: dict, before_path: Path, after_path: Path) -> str:
    before_modes = _mode_map(before)
    after_modes = _mode_map(after)
    before_chunking = _chunking_map(before)
    after_chunking = _chunking_map(after)

    lines: list[str] = []
    lines.append("Evaluation Report Comparison")
    lines.append(f"Before: {before_path}")
    lines.append(f"After:  {after_path}")
    lines.append("")
    lines.append(f"Top-K: {before.get('top_k')} -> {after.get('top_k')}")
    lines.append(f"Dataset: {before.get('dataset_path')} -> {after.get('dataset_path')}")
    lines.append("")

    lines.append("Base Retrieval Modes")
    common_modes = [mode for mode in before_modes if mode in after_modes]
    for mode in common_modes:
        lines.append(f"- {mode}: {_mode_summary_line(before_modes[mode], after_modes[mode])}")

    lines.append("")
    lines.append(f"Best Base Mode: { _best_mode_name(before) } -> { _best_mode_name(after) }")
    before_best_chunking_label, before_best_chunking_mode = _best_chunking_label(before)
    after_best_chunking_label, after_best_chunking_mode = _best_chunking_label(after)
    lines.append(
        "Best Chunking Setup: "
        f"{before_best_chunking_label}/{before_best_chunking_mode} -> "
        f"{after_best_chunking_label}/{after_best_chunking_mode}"
    )
    lines.append("")

    lines.append("Chunking Experiments")
    common_chunking = [label for label in before_chunking if label in after_chunking]
    for label in common_chunking:
        lines.append(f"- {label}")
        before_modes_by_name = {item["mode"]: item for item in before_chunking[label]["modes"]}
        after_modes_by_name = {item["mode"]: item for item in after_chunking[label]["modes"]}
        for mode in before_modes_by_name:
            if mode in after_modes_by_name:
                lines.append(
                    "  "
                    f"{mode}: {_mode_summary_line(before_modes_by_name[mode], after_modes_by_name[mode])}"
                )

    lines.append("")
    lines.append("How To Use This")
    lines.append("- Positive delta means the new report is better for that metric.")
    lines.append("- Focus first on MRR and Recall@K, then use Hit@1 as a stricter ranking signal.")
    lines.append("- AvgTopScore is a supporting metric, not the main decision driver.")
    return "\n".join(lines)


def _default_report_path(name: str) -> Path:
    return EVAL_REPORTS_DIR / name


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two saved retrieval evaluation reports.",
    )
    parser.add_argument(
        "--before",
        type=Path,
        default=_default_report_path("latest.json"),
        help="Path to the older evaluation JSON report.",
    )
    parser.add_argument(
        "--after",
        type=Path,
        default=_default_report_path("latest.json"),
        help="Path to the newer evaluation JSON report.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    before_path = args.before.resolve()
    after_path = args.after.resolve()
    before_report = _load_report(before_path)
    after_report = _load_report(after_path)
    print(build_comparison_summary(before_report, after_report, before_path, after_path))
