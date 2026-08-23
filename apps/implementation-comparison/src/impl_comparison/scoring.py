"""Artificial Analysis Coding Agent–style aggregation (not LLM model Index)."""

from typing import Dict, Iterable, List, Mapping

REQUIRED_AREAS = ("se", "terminal", "qna")


def task_score(attempts: Iterable[int]) -> float:
    values = list(attempts)
    if not values:
        raise ValueError("task_score requires at least one attempt")
    return sum(float(item) for item in values) / len(values)


def bench_score(task_scores: Iterable[float]) -> float:
    values = list(task_scores)
    if not values:
        raise ValueError("bench_score requires at least one task")
    return sum(values) / len(values)


def area_score(task_scores: Iterable[float]) -> float:
    return bench_score(task_scores)


def as_points(rate: float) -> float:
    """Display pass@1 as 0–100, matching Artificial Analysis Coding Agent Index."""
    return round(float(rate) * 100.0, 1)


def index_score(benchmarks: Mapping[str, float]) -> float:
    required = ("deepswe", "terminal_bench_v2", "swe_atlas_qna")
    missing = [name for name in required if name not in benchmarks]
    if missing:
        raise ValueError("index requires {}".format(", ".join(required)))
    return sum(float(benchmarks[name]) for name in required) / 3.0


def research_index(areas: Mapping[str, float]) -> float:
    if not areas:
        raise ValueError("research index requires se, terminal, and qna")
    extra = sorted(name for name in areas if name not in REQUIRED_AREAS)
    if extra:
        raise ValueError("mixed or unknown areas: {}".format(", ".join(extra)))
    missing = [name for name in REQUIRED_AREAS if name not in areas]
    if missing:
        raise ValueError(
            "index requires se, terminal, and qna; missing {}".format(
                ", ".join(missing)
            )
        )
    return sum(float(areas[name]) for name in REQUIRED_AREAS) / 3.0


def area_scores_from_records(
    task_records: Mapping[str, Mapping],
) -> Dict[str, float]:
    if not task_records:
        raise ValueError("research index requires task records")
    by_area: Dict[str, List[float]] = {name: [] for name in REQUIRED_AREAS}
    for record in task_records.values():
        area = ""
        if isinstance(record, Mapping):
            area = str(record.get("area") or "")
        if not area:
            raise ValueError("every task must have an area")
        if area not in REQUIRED_AREAS:
            raise ValueError("mixed or unknown areas: {}".format(area))
        by_area[area].append(float(record["task_score"]))
    for name in REQUIRED_AREAS:
        if not by_area[name]:
            raise ValueError("missing or empty area: {}".format(name))
    return {name: area_score(by_area[name]) for name in REQUIRED_AREAS}
