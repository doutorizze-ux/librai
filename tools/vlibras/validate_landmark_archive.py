"""Validate every compressed VLibras landmark motion."""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import json
from pathlib import Path


def validate(path_value: str) -> tuple[str, int, int, str | None]:
    path = Path(path_value)
    try:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            payload = json.load(source)
        frames = payload.get("frames", [])
        if not frames:
            raise ValueError("motion has no frames")
        for frame in frames:
            if len(frame.get("left_hand", [])) != 21:
                raise ValueError("frame does not contain 21 left-hand landmarks")
            if len(frame.get("right_hand", [])) != 21:
                raise ValueError("frame does not contain 21 right-hand landmarks")
        return path.name, len(frames), path.stat().st_size, None
    except Exception as error:
        return path.name, 0, path.stat().st_size, str(error)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    files = sorted(args.archive.glob("*.json.gz"))
    invalid = []
    frame_count = 0
    byte_count = 0
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max(1, args.workers)
    ) as executor:
        for name, frames, size, error in executor.map(
            validate, map(str, files), chunksize=16
        ):
            frame_count += frames
            byte_count += size
            if error is not None:
                invalid.append({"file": name, "error": error})
    print(
        json.dumps(
            {
                "files": len(files),
                "frames": frame_count,
                "bytes": byte_count,
                "invalid": invalid,
            },
            ensure_ascii=False,
        )
    )
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
