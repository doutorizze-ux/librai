"""Registra proveniência dos vídeos autorizados em manifesto privado."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from inventory_videos import SUPPORTED_SUFFIXES


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def register(input_dir: Path, output: Path):
    records = []
    for path in sorted(input_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        records.append(
            {
                "file": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "authorization_status": "declared_authorized_by_project_owner",
            }
        )
    manifest = {
        "schema_version": 1,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "Uso no desenvolvimento e treinamento privado do reconhecedor Librai, "
            "conforme autorização informada pelo responsável do projeto."
        ),
        "sources": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(records)} fontes registradas em {output}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    register(args.input_dir, args.output)
