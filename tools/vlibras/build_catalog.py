"""Build a deterministic, license-attributed catalog from VLibras bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


PLATFORM_PATHS = {
    "android": Path("vlibras-translate/bundles/ANDROID"),
    "ios": Path("vlibras-translate/bundles/IOS"),
    "linux": Path("vlibras-commons/unityVideo/videoCreator_Data/Bundles"),
}


def search_key(label: str) -> str:
    normalized = unicodedata.normalize("NFKD", label)
    return "".join(char for char in normalized if not unicodedata.combining(char)).upper()


def stable_id(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()[:16]


def build_catalog(source_root: Path) -> list[dict]:
    by_label: dict[str, dict] = {}
    for platform, relative_path in PLATFORM_PATHS.items():
        bundle_dir = source_root / relative_path
        if not bundle_dir.is_dir():
            continue
        for bundle in bundle_dir.iterdir():
            if not bundle.is_file() or bundle.name.startswith("."):
                continue
            entry = by_label.setdefault(
                bundle.name,
                {
                    "id": stable_id(bundle.name),
                    "label": bundle.name,
                    "search_key": search_key(bundle.name),
                    "size_bytes": bundle.stat().st_size,
                    "platforms": [],
                    "is_compound": "_" in bundle.name,
                },
            )
            entry["platforms"].append(platform)
            entry["size_bytes"] = min(entry["size_bytes"], bundle.stat().st_size)

    return sorted(by_label.values(), key=lambda item: (item["search_key"], item["label"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    signs = build_catalog(args.source.resolve())
    payload = {
        "schema_version": "1.0",
        "source": "VLibras",
        "license": "GPL-3.0; verify VLibras content terms before distribution",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(signs),
        "signs": signs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {len(signs)} signs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
