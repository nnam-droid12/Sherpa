import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "bench"))

import detection  # noqa: E402


def test_detection_benchmark_finds_exactly_the_planted_flaws():
    r = detection.run()
    assert r["base_findings"] == []
    assert r["variants_with_false_alarms"] == 0
    assert r["exact_match"] == r["variants"] == 126
    assert r["recall"] == 1.0


def test_every_flaw_operator_changes_the_base():
    for flaw in detection.FLAWS:
        assert detection.plant([flaw]) != detection.BASE, flaw.code
