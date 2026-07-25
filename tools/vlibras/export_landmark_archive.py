"""Export every VLibras Unity bundle as a compressed landmark motion."""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import json
import sys
from pathlib import Path

from extract_landmark_motion import extract_motion_with_skeleton, load_skeleton

_SKELETON = None
_OUTPUT = None
_FPS = 15


def _initialize_worker(scene: str, output: str, fps: int) -> None:
    global _SKELETON, _OUTPUT, _FPS
    _SKELETON = load_skeleton(Path(scene))
    _OUTPUT = Path(output)
    _FPS = fps


def _export_bundle(bundle_value: str) -> tuple[str, str | None]:
    bundle = Path(bundle_value)
    destination = _OUTPUT / f"{bundle.name}.json.gz"
    try:
        payload = extract_motion_with_skeleton(_SKELETON, bundle, _FPS)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        with gzip.open(temporary, "wt", encoding="utf-8") as output_file:
            json.dump(
                payload,
                output_file,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        temporary.replace(destination)
        return bundle.name, None
    except Exception as error:
        return bundle.name, str(error)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--bundles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    bundles = sorted(path for path in args.bundles.iterdir() if path.is_file())
    args.output.mkdir(parents=True, exist_ok=True)
    completed = 0
    failed: list[tuple[str, str]] = []
    pending = [
        bundle
        for bundle in bundles
        if args.overwrite
        or not (args.output / f"{bundle.name}.json.gz").is_file()
    ]
    completed = len(bundles) - len(pending)

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max(1, args.workers),
        initializer=_initialize_worker,
        initargs=(str(args.scene), str(args.output), args.fps),
    ) as executor:
        results = executor.map(_export_bundle, map(str, pending), chunksize=8)
        for index, (name, error) in enumerate(results, start=1):
            if error is None:
                completed += 1
            else:
                failed.append((name, error))
            processed = completed + len(failed)
            if index % 100 == 0 or index == len(pending):
                print(
                    f"{processed}/{len(bundles)} processed; "
                    f"{completed} ready; {len(failed)} failed",
                    flush=True,
                )

    if failed:
        failure_path = args.output / "failures.json"
        failure_path.write_text(
            json.dumps(failed, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Failures written to {failure_path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
