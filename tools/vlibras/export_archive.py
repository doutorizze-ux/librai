"""Resumable parallel export of a VLibras UnityFS collection to JSON.GZ."""

from __future__ import annotations

import argparse
import gzip
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from extract_animation import extract


def export_one(bundle: Path, output_dir: Path) -> tuple[str, str]:
    destination = output_dir / f"{bundle.name}.json.gz"
    if destination.is_file() and destination.stat().st_size > 0:
        return bundle.name, "skipped"

    payload = json.dumps(
        extract(bundle),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("wb") as raw_file:
        with gzip.GzipFile(fileobj=raw_file, mode="wb", mtime=0) as compressed:
            compressed.write(payload)
    temporary.replace(destination)
    return bundle.name, "exported"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    bundles = sorted(
        (
            bundle
            for bundle in args.source.resolve().iterdir()
            if bundle.is_file() and not bundle.name.startswith(".")
        ),
        key=lambda path: path.name,
    )
    if args.limit is not None:
        bundles = bundles[: args.limit]
    args.output.mkdir(parents=True, exist_ok=True)

    exported = 0
    skipped = 0
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(export_one, bundle, args.output): bundle
            for bundle in bundles
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            bundle = futures[future]
            try:
                _, status = future.result()
                if status == "exported":
                    exported += 1
                else:
                    skipped += 1
            except Exception as error:  # keep the long batch resumable
                failures.append({"label": bundle.name, "error": str(error)})
            if completed % 250 == 0 or completed == len(futures):
                print(
                    f"{completed}/{len(futures)} "
                    f"exported={exported} skipped={skipped} failed={len(failures)}",
                    flush=True,
                )

    manifest = {
        "schema_version": "1.0",
        "source": "VLibras Android UnityFS bundles",
        "license": "GPL-3.0; distribution approval pending",
        "requested": len(bundles),
        "exported": exported,
        "skipped": skipped,
        "failed": failures,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
