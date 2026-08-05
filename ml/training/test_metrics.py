import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from metrics import (
    RejectionCalibrationError,
    calibrate_rejection,
    classification_report,
)


def test_classification_report_exposes_confusion_and_per_class_recall():
    report = classification_report(
        [0, 0, 1, 1],
        [0, 1, 1, 1],
        {"OLÁ": 0, "TUDO BEM?": 1},
    )

    assert report["confusion_matrix"] == [[1, 1], [0, 2]]
    assert report["per_class"]["OLÁ"]["recall"] == 0.5
    assert report["per_class"]["TUDO BEM?"]["recall"] == 1.0


def test_rejection_calibration_requires_real_unknown_examples():
    with pytest.raises(RejectionCalibrationError, match="OOD"):
        calibrate_rejection([[0.95, 0.05]], [0], [])


def test_rejection_calibration_finds_thresholds_without_sacrificing_knowns():
    result = calibrate_rejection(
        [[0.96, 0.04], [0.03, 0.97], [0.92, 0.08], [0.05, 0.95]],
        [0, 1, 0, 1],
        [[0.52, 0.48], [0.55, 0.45], [0.51, 0.49]],
        minimum_known_acceptance=0.75,
        minimum_ood_recall=1.0,
    )

    assert result["known_acceptance_rate"] == 1.0
    assert result["ood_recall"] == 1.0
    assert result["minimum_margin"] >= 0.05
