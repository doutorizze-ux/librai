"""Seleciona classes minimamente comparáveis para um modelo piloto.

Não duplica nem sintetiza amostras. Uma classe só entra quando aparece em ao
menos duas fontes/professores reais, permitindo uma validação independente,
ainda que experimental.
"""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path


def select(
    source: Path,
    output: Path,
    min_trainers: int,
    hands_only: bool = False,
) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    trainers_by_class: dict[str, set[str]] = defaultdict(set)
    for sample in payload["samples"]:
        trainers_by_class[sample["sign_name"]].add(sample["trainer_name"])

    selected_classes = {
        label
        for label, trainers in trainers_by_class.items()
        if len(trainers) >= min_trainers
    }
    samples = [
        copy.deepcopy(sample)
        for sample in payload["samples"]
        if sample["sign_name"] in selected_classes
    ]
    if hands_only:
        for sample in samples:
            for frame in sample.get("landmarks", {}).get("frames", []):
                frame.pop("pose", None)
                frame.pop("expression", None)
    class_counts = Counter(sample["sign_name"] for sample in samples)
    result = {
        "format_version": payload.get("format_version", 1),
        "profile": "experimental_pilot",
        "input_profile": "hands_only" if hands_only else "holistic",
        "sample_count": len(samples),
        "class_counts": dict(sorted(class_counts.items())),
        "samples": samples,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "sample_count": len(samples),
                "class_count": len(selected_classes),
                "classes": sorted(selected_classes),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--min-trainers", type=int, default=2)
    parser.add_argument("--hands-only", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    select(args.source, args.output, args.min_trainers, args.hands_only)
