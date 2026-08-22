import inspect

from impl_comparison.scoring import bench_score, index_score, research_index, task_score


def test_task_score_is_mean_of_three_binary_attempts():
    assert task_score([1, 0, 1]) == 2.0 / 3.0


def test_bench_score_weights_tasks_equally():
    assert bench_score([1.0, 0.0]) == 0.5


def test_index_is_equal_weight_mean_of_three_benches():
    assert index_score({"deepswe": 0.3, "terminal_bench_v2": 0.6, "swe_atlas_qna": 0.9}) == 0.6


def test_research_index_is_correctness_only():
    areas = {"se": 0.4, "terminal": 0.5, "qna": 0.6}
    assert research_index(areas) == (0.4 + 0.5 + 0.6) / 3.0
    names = set(inspect.signature(research_index).parameters)
    assert "time" not in names
    assert "cost" not in names
    assert "tokens" not in names
    assert "turns" not in names
