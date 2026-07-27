"""Merge reviewed landmark extractions without inflating dataset quality.

The script keeps one record per real source segment, applies only corrections
that were visually verified against the source preview, and quarantines
ambiguous OCR labels instead of silently training on them.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


VERIFIED_LABEL_OVERRIDES = {
    "candidate-0017": "BEBER",
    "candidate-0023": "ABANDONAR",
    "candidate-0052": "DAR / ENTREGAR",
    "candidate-0053": "NAO TER",
    "candidate-0059": "FUNDAR / CRIAR",
    "batch1-fixed-0018": "SEU NOME",
    "batch1-fixed-0020": "TE PERGUNTAR",
    "batch1-fixed-0021": "ME PERGUNTAR",
    "batch1-fixed-0022": "AONDE MORAR",
    "batch1-fixed-0044": "TUDO BEM",
    "batch2-candidate-0038": "MAE",
    "batch2-candidate-0052": "FEIO",
}

# Intros, clipped OCR fragments and crops whose displayed label cannot be
# associated safely with the gesture are not training data.
QUARANTINED_SEGMENTS = {
    "candidate-0009": "intro/chamada do vídeo, não é um sinal rotulado",
    "candidate-0123": "rótulo OCR cortado ('ME')",
    "candidate-0129": "rótulo OCR cortado ('TE')",
    "candidate-0141": "rótulo OCR ambíguo ('BRAS')",
    "batch2-candidate-0001": "abertura do vídeo, não é sinal rotulado",
    "batch2-candidate-0010": "encerramento do vídeo, não é classe do tradutor",
}

CANONICAL_LABELS = {
    "AJUDA": "AJUDAR",
    "OBRIGADA": "OBRIGADO",
}


def normalize_label(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"\s+", " ", value.upper()).strip()
    return CANONICAL_LABELS.get(value, value)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit-output", required=True, type=Path)
    args = parser.parse_args()

    merged: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    seen_segments: set[str] = set()

    for input_path in args.inputs:
        for sample in load_json(input_path).get("samples", []):
            segment_id = str(sample["source_segment_id"])
            if segment_id in seen_segments:
                continue
            seen_segments.add(segment_id)

            if segment_id in QUARANTINED_SEGMENTS:
                quarantined.append(
                    {
                        "source_segment_id": segment_id,
                        "original_label": sample["sign_name"],
                        "reason": QUARANTINED_SEGMENTS[segment_id],
                    }
                )
                continue

            corrected = VERIFIED_LABEL_OVERRIDES.get(
                segment_id, normalize_label(str(sample["sign_name"]))
            )
            normalized = dict(sample)
            normalized["sign_name"] = corrected
            merged.append(normalized)

    class_counts = Counter(sample["sign_name"] for sample in merged)
    trainers_by_class: dict[str, set[str]] = defaultdict(set)
    for sample in merged:
        trainers_by_class[sample["sign_name"]].add(sample["trainer_name"])

    dataset = {
        "format_version": 1,
        "sample_count": len(merged),
        "class_counts": dict(sorted(class_counts.items())),
        "samples": merged,
    }
    audit = {
        "sample_count": len(merged),
        "class_count": len(class_counts),
        "trainer_count": len({sample["trainer_name"] for sample in merged}),
        "trainers": sorted({sample["trainer_name"] for sample in merged}),
        "quarantined": quarantined,
        "classes_with_multiple_trainers": {
            label: sorted(trainers)
            for label, trainers in sorted(trainers_by_class.items())
            if len(trainers) > 1
        },
        "classes_with_multiple_samples": {
            label: count
            for label, count in sorted(class_counts.items())
            if count > 1
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(dataset, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    args.audit_output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
