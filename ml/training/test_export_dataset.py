import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent))

from export_dataset import export_dataset


def test_export_includes_only_validated_v4_captures(tmp_path):
    database = tmp_path / "dataset.db"
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE training_samples (
                id TEXT PRIMARY KEY,
                sign_name TEXT,
                landmarks JSON,
                trainer_name TEXT,
                frame_count INTEGER,
                created_at DATETIME,
                deleted_at DATETIME
            )
        """))
        for sample_id, payload in [
            ("validated", {"format_version": 4, "dataset_state": "validated_capture"}),
            ("pending", {"format_version": 4, "dataset_state": "pending_validation"}),
            ("legacy", {"format_version": 3, "dataset_state": "validated_capture"}),
        ]:
            connection.execute(
                text("""
                    INSERT INTO training_samples
                        (id, sign_name, landmarks, trainer_name, frame_count, created_at)
                    VALUES
                        (:id, 'OLÁ', :landmarks, 'Professora', 24, '2026-08-05 12:00:00')
                """),
                {"id": sample_id, "landmarks": json.dumps(payload)},
            )

    output = tmp_path / "training.json"
    export_dataset(f"sqlite:///{database}", output)
    exported = json.loads(output.read_text(encoding="utf-8"))

    assert exported["sample_count"] == 1
    assert [sample["id"] for sample in exported["samples"]] == ["validated"]
