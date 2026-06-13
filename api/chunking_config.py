from __future__ import annotations

from threading import Lock
from typing import Literal

from api.settings import CHUNK_OVERLAP_WORDS, CHUNK_SIZE_WORDS

ChunkingPreset = Literal["baseline_120_30", "legacy_80_20", "small_50_10"]

CHUNKING_PRESETS: dict[ChunkingPreset, dict[str, int]] = {
    "baseline_120_30": {"chunk_size_words": 120, "chunk_overlap_words": 30},
    "legacy_80_20": {"chunk_size_words": 80, "chunk_overlap_words": 20},
    "small_50_10": {"chunk_size_words": 50, "chunk_overlap_words": 10},
}

_config_lock = Lock()


def _initial_preset() -> ChunkingPreset:
    for preset, config in CHUNKING_PRESETS.items():
        if (
            config["chunk_size_words"] == CHUNK_SIZE_WORDS
            and config["chunk_overlap_words"] == CHUNK_OVERLAP_WORDS
        ):
            return preset
    return "baseline_120_30"


_current_preset: ChunkingPreset = _initial_preset()


def get_chunking_config() -> dict[str, object]:
    config = CHUNKING_PRESETS[_current_preset]
    return {
        "current_preset": _current_preset,
        "chunk_size_words": config["chunk_size_words"],
        "chunk_overlap_words": config["chunk_overlap_words"],
        "available_presets": list(CHUNKING_PRESETS.keys()),
    }


def set_chunking_preset(preset: ChunkingPreset) -> dict[str, object]:
    global _current_preset
    with _config_lock:
        _current_preset = preset
        return get_chunking_config()
