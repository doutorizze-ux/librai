"""Convert one VLibras Unity AnimationClip into portable JSON curves."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import UnityPy


CURVE_GROUPS = (
    "m_RotationCurves",
    "m_PositionCurves",
    "m_ScaleCurves",
    "m_EulerCurves",
)


def compact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: compact_value(item)
            for key, item in value.items()
            if key in {"x", "y", "z", "w"}
        }
    if isinstance(value, float):
        return round(value, 7)
    return value


def compact_curve(curve: dict) -> dict:
    keys = curve.get("curve", {}).get("m_Curve", [])
    return {
        "bone": curve.get("path", ""),
        "keys": [
            {
                "time": round(key["time"], 7),
                "value": compact_value(key["value"]),
            }
            for key in keys
        ],
    }


def extract(bundle_path: Path) -> dict:
    environment = UnityPy.load(str(bundle_path))
    clips = [
        obj.read_typetree()
        for obj in environment.objects
        if obj.type.name == "AnimationClip"
    ]
    if len(clips) != 1:
        raise ValueError(
            f"Expected exactly one AnimationClip in {bundle_path}, found {len(clips)}"
        )

    clip = clips[0]
    groups = {
        group.removeprefix("m_"): [
            compact_curve(curve) for curve in clip.get(group, [])
        ]
        for group in CURVE_GROUPS
        if clip.get(group)
    }
    key_times = [
        key["time"]
        for curves in groups.values()
        for curve in curves
        for key in curve["keys"]
    ]
    return {
        "schema_version": "1.0",
        "source": "VLibras",
        "license": "GPL-3.0; verify VLibras content terms before distribution",
        "label": clip.get("m_Name") or bundle_path.name,
        "sample_rate": clip.get("m_SampleRate", 30.0),
        "duration_seconds": round(max(key_times, default=0.0), 7),
        "curves": groups,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = extract(args.bundle.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"Wrote {payload['label']} ({payload['duration_seconds']}s) to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
