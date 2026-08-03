"""Política de qualidade do dataset, independente do framework de IA."""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QualityPolicy:
    min_classes: int = 2
    min_trainers_per_class: int = 3
    min_samples_per_class: int = 15
    min_validation_trainers: int = 1
    minimum_validation_accuracy: float = 0.70


class DatasetQualityError(ValueError):
    pass


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("samples") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise DatasetQualityError("O arquivo precisa conter uma lista 'samples'.")
    active = [
        record
        for record in records
        if isinstance(record, dict) and not record.get("deleted_at")
    ]
    if not active:
        raise DatasetQualityError("Nenhuma amostra ativa foi encontrada.")
    return active


def validate_dataset(
    records: list[dict[str, Any]], policy: QualityPolicy
) -> dict[str, Any]:
    by_class: Counter[str] = Counter()
    trainers_by_class: dict[str, set[str]] = defaultdict(set)
    invalid = 0
    for record in records:
        label = str(record.get("sign_name", "")).strip()
        trainer = str(record.get("trainer_name", "")).strip()
        sequence = record.get("landmarks")
        if not label or not trainer or not isinstance(sequence, dict):
            invalid += 1
            continue
        if sequence.get("format_version") not in {2, 3, 4}:
            invalid += 1
            continue
        by_class[label] += 1
        trainers_by_class[label].add(trainer)

    errors = []
    if len(by_class) < policy.min_classes:
        errors.append(
            f"somente {len(by_class)} classes válidas; mínimo {policy.min_classes}"
        )
    for label, count in sorted(by_class.items()):
        if count < policy.min_samples_per_class:
            errors.append(
                f"{label}: {count} amostras; mínimo {policy.min_samples_per_class}"
            )
        trainer_count = len(trainers_by_class[label])
        if trainer_count < policy.min_trainers_per_class:
            errors.append(
                f"{label}: {trainer_count} professor(es); mínimo "
                f"{policy.min_trainers_per_class}"
            )
    if errors:
        raise DatasetQualityError("; ".join(errors))
    return {
        "valid_samples": sum(by_class.values()),
        "invalid_samples": invalid,
        "classes": dict(sorted(by_class.items())),
        "trainers_by_class": {
            label: sorted(trainers) for label, trainers in trainers_by_class.items()
        },
    }


def split_by_trainer(
    records: list[dict[str, Any]], seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    trainers = sorted(
        {
            str(record.get("trainer_name", "")).strip()
            for record in records
            if record.get("trainer_name")
        }
    )
    if len(trainers) < 2:
        raise DatasetQualityError(
            "São necessários ao menos dois professores para separar validação."
        )
    rng = random.Random(seed)
    rng.shuffle(trainers)
    validation_count = max(1, round(len(trainers) * 0.2))
    validation_trainers = set(trainers[:validation_count])
    training = [
        record
        for record in records
        if str(record.get("trainer_name", "")).strip() not in validation_trainers
    ]
    validation = [
        record
        for record in records
        if str(record.get("trainer_name", "")).strip() in validation_trainers
    ]
    train_labels = {str(record["sign_name"]) for record in training}
    validation_labels = {str(record["sign_name"]) for record in validation}
    missing = sorted(train_labels - validation_labels)
    if missing:
        raise DatasetQualityError(
            "A validação por professor não contém todas as classes: "
            + ", ".join(missing)
        )
    return training, validation, sorted(validation_trainers)


def split_by_class_trainer(
    records: list[dict[str, Any]], seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Segura uma fonte diferente por classe para protótipos experimentais.

    Diferente do split de produção, um professor pode aparecer no treino de
    outra classe. Isso é explicitamente menos rigoroso, mas cada sinal continua
    sendo validado em uma pessoa que não ensinou aquela mesma classe.
    """
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_class[str(record["sign_name"])].append(record)
    rng = random.Random(seed)
    training: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    held_out: list[str] = []
    for label, class_records in sorted(by_class.items()):
        trainers = sorted({
            str(record["trainer_name"]).strip() for record in class_records
        })
        if len(trainers) < 2:
            raise DatasetQualityError(
                f"{label}: são necessárias duas fontes para o piloto."
            )
        validation_trainer = trainers[rng.randrange(len(trainers))]
        held_out.append(f"{label}:{validation_trainer}")
        for record in class_records:
            if str(record["trainer_name"]).strip() == validation_trainer:
                validation.append(record)
            else:
                training.append(record)
    return training, validation, held_out
