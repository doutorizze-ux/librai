"""Exporta landmarks ativos diretamente do PostgreSQL/SQLite para treinamento.

Execute com DATABASE_URL configurada. O arquivo não contém imagens, áudio,
vídeo, e-mail ou senha; somente identificador da amostra, rótulo, professor e
landmarks consentidos.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, text


QUERY = text(
    """
    SELECT id, sign_name, landmarks, trainer_name, frame_count, created_at
    FROM training_samples
    WHERE deleted_at IS NULL
    ORDER BY created_at, id
    """
)


def export_dataset(database_url: str, output: Path):
    engine = create_engine(database_url)
    samples = []
    with engine.connect() as connection:
        for row in connection.execute(QUERY).mappings():
            landmarks = row["landmarks"]
            if isinstance(landmarks, str):
                landmarks = json.loads(landmarks)
            samples.append(
                {
                    "id": row["id"],
                    "sign_name": row["sign_name"],
                    "trainer_name": row["trainer_name"],
                    "frame_count": row["frame_count"],
                    "created_at": row["created_at"].isoformat(),
                    "landmarks": landmarks,
                }
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {"format_version": 1, "sample_count": len(samples), "samples": samples},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"{len(samples)} amostras exportadas para {output}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url", default=os.getenv("DATABASE_URL"), dest="database_url"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("ml/dataset/private/training.json")
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("Informe --database-url ou configure DATABASE_URL.")
    return args


if __name__ == "__main__":
    arguments = parse_args()
    export_dataset(arguments.database_url, arguments.output)
