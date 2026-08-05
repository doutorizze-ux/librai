"""Métricas reproduzíveis e calibração da rejeição de sinais desconhecidos."""

from __future__ import annotations

from typing import Sequence


class RejectionCalibrationError(ValueError):
    pass


def classification_report(
    targets: Sequence[int],
    predictions: Sequence[int],
    labels: dict[str, int],
) -> dict:
    if len(targets) != len(predictions):
        raise ValueError("targets and predictions must have the same length")
    size = len(labels)
    matrix = [[0 for _ in range(size)] for _ in range(size)]
    for target, prediction in zip(targets, predictions):
        if not (0 <= target < size and 0 <= prediction < size):
            raise ValueError("class index outside label map")
        matrix[target][prediction] += 1

    names = {index: name for name, index in labels.items()}
    per_class = {}
    f1_values = []
    for index in range(size):
        true_positive = matrix[index][index]
        support = sum(matrix[index])
        predicted = sum(row[index] for row in matrix)
        recall = true_positive / support if support else 0.0
        precision = true_positive / predicted if predicted else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        f1_values.append(f1)
        per_class[names[index]] = {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "support": support,
        }
    return {
        "confusion_matrix": matrix,
        "per_class": per_class,
        "macro_f1": round(sum(f1_values) / max(1, size), 6),
    }


def _confidence_and_margin(probabilities: Sequence[float]) -> tuple[float, float, int]:
    if len(probabilities) < 2:
        raise ValueError("at least two class probabilities are required")
    order = sorted(
        range(len(probabilities)),
        key=lambda index: probabilities[index],
        reverse=True,
    )
    best, runner_up = order[:2]
    return (
        float(probabilities[best]),
        float(probabilities[best] - probabilities[runner_up]),
        best,
    )


def calibrate_rejection(
    known_probabilities: Sequence[Sequence[float]],
    known_targets: Sequence[int],
    ood_probabilities: Sequence[Sequence[float]],
    *,
    minimum_known_acceptance: float = 0.70,
    minimum_ood_recall: float = 0.90,
) -> dict:
    """Escolhe limites somente se conhecidos e OOD cumprirem os dois gates."""
    if len(known_probabilities) != len(known_targets) or not known_targets:
        raise RejectionCalibrationError("known validation set is invalid")
    if not ood_probabilities:
        raise RejectionCalibrationError("an explicit OOD validation set is required")

    known = [
        (*_confidence_and_margin(row), int(target))
        for row, target in zip(known_probabilities, known_targets)
    ]
    unknown = [_confidence_and_margin(row) for row in ood_probabilities]
    confidence_grid = [value / 100 for value in range(50, 100, 3)]
    margin_grid = [value / 100 for value in range(5, 51, 3)]
    candidates = []
    for confidence_threshold in confidence_grid:
        for margin_threshold in margin_grid:
            accepted_known = sum(
                predicted == target
                and confidence >= confidence_threshold
                and margin >= margin_threshold
                for confidence, margin, predicted, target in known
            )
            rejected_ood = sum(
                confidence < confidence_threshold or margin < margin_threshold
                for confidence, margin, _ in unknown
            )
            known_acceptance = accepted_known / len(known)
            ood_recall = rejected_ood / len(unknown)
            if (
                known_acceptance >= minimum_known_acceptance
                and ood_recall >= minimum_ood_recall
            ):
                candidates.append((
                    known_acceptance,
                    ood_recall,
                    confidence_threshold,
                    margin_threshold,
                ))
    if not candidates:
        raise RejectionCalibrationError(
            "no rejection thresholds satisfy known and OOD validation gates"
        )
    known_acceptance, ood_recall, confidence, margin = max(candidates)
    return {
        "method": "softmax_confidence_and_margin",
        "minimum_confidence": round(confidence, 4),
        "minimum_margin": round(margin, 4),
        "known_acceptance_rate": round(known_acceptance, 6),
        "ood_recall": round(ood_recall, 6),
        "minimum_known_acceptance": minimum_known_acceptance,
        "minimum_ood_recall": minimum_ood_recall,
        "known_validation_samples": len(known),
        "ood_validation_samples": len(unknown),
    }
