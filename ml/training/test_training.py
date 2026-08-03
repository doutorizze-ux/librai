import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from quality import (
    DatasetQualityError,
    QualityPolicy,
    split_by_class_trainer,
    split_by_trainer,
    validate_dataset,
)
from merge_extracted_datasets import normalize_label
from extract_spatial_grid_dataset import build_layouts
from stgcn import LibrasSTGCN, SequencePreprocessor, TOTAL_NODES
from promote import PromotionError, promote


def sequence():
    hand = [
        {"x": index / 100, "y": index / 100, "z": 0.0}
        for index in range(21)
    ]
    return {
        "format_version": 2,
        "frames": [
            {
                "timestamp_ms": frame * 33,
                "hands": [
                    {"handedness": "Left", "score": 0.99, "landmarks": hand}
                ],
            }
            for frame in range(12)
        ],
    }


def records():
    return [
        {
            "sign_name": label,
            "trainer_name": trainer,
            "landmarks": sequence(),
        }
        for label in ("BOM", "DIA")
        for trainer in ("Prof A", "Prof B", "Prof C")
        for _ in range(5)
    ]


def test_quality_accepts_balanced_real_records():
    report = validate_dataset(records(), QualityPolicy())
    assert report["classes"] == {"BOM": 15, "DIA": 15}


def test_quality_rejects_single_trainer():
    data = [record for record in records() if record["trainer_name"] == "Prof A"]
    with pytest.raises(DatasetQualityError, match="professor"):
        validate_dataset(data, QualityPolicy(min_samples_per_class=5))


def test_split_never_leaks_trainer_between_sets():
    training, validation, held_out = split_by_trainer(records(), seed=7)
    assert {item["trainer_name"] for item in validation} == set(held_out)
    assert not (
        {item["trainer_name"] for item in training}
        & {item["trainer_name"] for item in validation}
    )


def test_experimental_split_holds_out_a_trainer_inside_each_class():
    training, validation, held_out = split_by_class_trainer(records(), seed=7)
    for label in ("BOM", "DIA"):
        train_trainers = {
            item["trainer_name"] for item in training if item["sign_name"] == label
        }
        validation_trainers = {
            item["trainer_name"]
            for item in validation
            if item["sign_name"] == label
        }
        assert train_trainers
        assert validation_trainers
        assert not (train_trainers & validation_trainers)
    assert len(held_out) == 2


def test_preprocessor_and_stgcn_use_temporal_two_hand_shape():
    import torch

    features = SequencePreprocessor(sequence_length=24)(sequence())
    assert features.shape == (4, 24, TOTAL_NODES)
    assert features[3].sum() > 0
    logits = LibrasSTGCN(num_classes=2)(features.unsqueeze(0))
    assert logits.shape == (1, 2)
    assert torch.isfinite(logits).all()


def test_preprocessor_accepts_version_four_semantic_units():
    payload = sequence()
    payload["format_version"] = 4
    payload["dataset_state"] = "pending_validation"
    features = SequencePreprocessor(sequence_length=24)(payload)
    assert features.shape == (4, 24, TOTAL_NODES)


def test_merge_normalizes_accents_and_known_equivalent_labels():
    assert normalize_label("  Olá  ") == "OLA"
    assert normalize_label("obrigada") == "OBRIGADO"
    assert normalize_label("ajuda") == "AJUDAR"


def test_spatial_layout_uses_every_cell_before_sharding():
    candidates = [
        {
            "video": "grid.mp4",
            "box": [column * 300, row * 300, column * 300 + 80, row * 300 + 40],
        }
        for row in range(3)
        for column in range(3)
    ]
    layout = build_layouts(candidates)["grid.mp4"]
    assert len(layout["x"]) == 3
    assert len(layout["y"]) == 3


def test_promotion_keeps_multiword_labels_and_requires_real_gates(tmp_path):
    review = tmp_path / "review"
    production = tmp_path / "production"
    review.mkdir()
    model = review / "candidate.onnx"
    model.write_bytes(b"validated-onnx-test")
    digest = __import__("hashlib").sha256(model.read_bytes()).hexdigest()
    manifest = {
        "model_id": "librai-stgcn-test",
        "architecture": "ST-GCN",
        "feature_schema": "librai_holistic_v4",
        "sequence_length": 48,
        "labels": {"OLA": 0, "TUDO BEM?": 1},
        "validation_mode": "global-trainer",
        "validation_accuracy": 0.9,
        "quality_policy": {"minimum_validation_accuracy": 0.7},
        "dataset_quality": {
            "trainers_by_class": {
                "OLA": ["A", "B", "C"],
                "TUDO BEM?": ["A", "B", "C"],
            }
        },
        "onnx_file": model.name,
        "onnx_sha256": digest,
        "status": "validated_ready_for_review",
    }
    manifest_path = review / "candidate.manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    promoted = promote(manifest_path, production, "Comitê Librai")
    assert promoted["status"] == "production"
    assert promoted["labels"]["TUDO BEM?"] == 1
    assert (production / "production.manifest.json").is_file()
    assert (production / "librai_stgcn.onnx").read_bytes() == model.read_bytes()


def test_promotion_rejects_two_professors_per_class(tmp_path):
    manifest = tmp_path / "candidate.manifest.json"
    manifest.write_text(json.dumps({
        "status": "validated_ready_for_review",
        "feature_schema": "librai_holistic_v4",
        "validation_mode": "global-trainer",
        "validation_accuracy": 0.99,
        "dataset_quality": {"trainers_by_class": {"OLA": ["A", "B"]}},
    }), encoding="utf-8")
    with pytest.raises(PromotionError, match="três professores"):
        promote(manifest, tmp_path / "production", "Comitê Librai")
