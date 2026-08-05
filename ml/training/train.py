"""Treinamento real do classificador temporal de Libras.

Este comando nunca gera pesos a partir de dados sintéticos. Ele recebe um
arquivo JSON exportado do banco, separa professores inteiros entre treino e
validação e só publica um artefato quando os critérios mínimos forem atendidos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from stgcn import LibrasSTGCN, SequencePreprocessor
from quality import (
    DatasetQualityError,
    QualityPolicy,
    load_records,
    split_by_class_trainer,
    split_by_trainer,
    validate_dataset,
)
from metrics import calibrate_rejection, classification_report


class LibrasSequenceDataset(Dataset):
    def __init__(
        self,
        records: list[dict[str, Any]],
        labels: dict[str, int],
        preprocessor: SequencePreprocessor,
    ):
        self.examples = []
        for record in records:
            label = str(record.get("sign_name", ""))
            if label not in labels:
                continue
            tensor = preprocessor(record.get("landmarks"))
            if tensor is not None:
                self.examples.append((tensor, labels[label]))
        if not self.examples:
            raise DatasetQualityError("Nenhuma sequência pôde ser convertida.")

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int):
        return self.examples[index]


class LibrasUnlabeledDataset(Dataset):
    def __init__(self, records, preprocessor):
        self.examples = [
            tensor
            for record in records
            if (tensor := preprocessor(record.get("landmarks"))) is not None
        ]
        if not self.examples:
            raise DatasetQualityError(
                "Nenhuma sequência OOD pôde ser convertida."
            )

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int):
        return self.examples[index]


def run_epoch(model, loader, criterion, device, optimizer=None):
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    correct = 0
    total = 0
    for features, targets in loader:
        features, targets = features.to(device), targets.to(device)
        if training:
            optimizer.zero_grad(set_to_none=True)
        logits = model(features)
        loss = criterion(logits, targets)
        if training:
            loss.backward()
            optimizer.step()
        total_loss += float(loss.item()) * targets.size(0)
        correct += int((logits.argmax(dim=1) == targets).sum().item())
        total += targets.size(0)
    return total_loss / max(total, 1), correct / max(total, 1)


def collect_probabilities(model, loader, device, *, labeled: bool):
    probabilities = []
    targets = []
    predictions = []
    model.eval()
    with torch.inference_mode():
        for batch in loader:
            if labeled:
                features, batch_targets = batch
                targets.extend(int(value) for value in batch_targets.tolist())
            else:
                features = batch
            rows = torch.softmax(model(features.to(device)), dim=1).cpu()
            probabilities.extend(rows.tolist())
            predictions.extend(
                int(value) for value in rows.argmax(dim=1).tolist()
            )
    return probabilities, targets, predictions


def train(args) -> dict[str, Any]:
    policy = QualityPolicy(
        min_classes=args.min_classes,
        min_trainers_per_class=args.min_trainers_per_class,
        min_samples_per_class=args.min_samples_per_class,
        minimum_validation_accuracy=args.minimum_validation_accuracy,
    )
    records = [
        record
        for record in load_records(args.dataset)
        if isinstance(record.get("landmarks"), dict)
        and record["landmarks"].get("format_version")
        == args.required_format_version
        and record["landmarks"].get("dataset_state")
        == "validated_capture"
    ]
    if not records:
        raise DatasetQualityError(
            "Nenhuma amostra do formato holístico exigido foi encontrada."
        )
    quality = validate_dataset(records, policy)
    split = (
        split_by_class_trainer
        if args.validation_mode == "per-class-trainer"
        else split_by_trainer
    )
    training_records, validation_records, validation_trainers = split(
        records, args.seed
    )
    labels = {
        label: index for index, label in enumerate(sorted(quality["classes"]))
    }
    preprocessor = SequencePreprocessor(sequence_length=args.sequence_length)
    training_data = LibrasSequenceDataset(training_records, labels, preprocessor)
    validation_data = LibrasSequenceDataset(
        validation_records, labels, preprocessor
    )

    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LibrasSTGCN(num_classes=len(labels)).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=1e-4
    )
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    train_loader = DataLoader(
        training_data, batch_size=args.batch_size, shuffle=True
    )
    validation_loader = DataLoader(
        validation_data, batch_size=args.batch_size, shuffle=False
    )

    best_accuracy = -1.0
    best_state = None
    history = []
    for epoch in range(1, args.epochs + 1):
        train_loss, train_accuracy = run_epoch(
            model, train_loader, criterion, device, optimizer
        )
        with torch.inference_mode():
            validation_loss, validation_accuracy = run_epoch(
                model, validation_loader, criterion, device
            )
        history.append(
            {
                "epoch": epoch,
                "train_loss": round(train_loss, 6),
                "train_accuracy": round(train_accuracy, 6),
                "validation_loss": round(validation_loss, 6),
                "validation_accuracy": round(validation_accuracy, 6),
            }
        )
        print(
            f"epoch={epoch} treino={train_accuracy:.1%} "
            f"validacao={validation_accuracy:.1%}"
        )
        if validation_accuracy > best_accuracy:
            best_accuracy = validation_accuracy
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }

    if best_state is None or best_accuracy < policy.minimum_validation_accuracy:
        raise DatasetQualityError(
            f"Modelo reprovado: validação {best_accuracy:.1%}; mínimo "
            f"{policy.minimum_validation_accuracy:.1%}."
        )

    model.load_state_dict(best_state)
    known_probabilities, known_targets, known_predictions = collect_probabilities(
        model, validation_loader, device, labeled=True
    )
    metrics = classification_report(known_targets, known_predictions, labels)

    ood_records = [
        record
        for record in load_records(args.ood_dataset)
        if isinstance(record.get("landmarks"), dict)
        and record["landmarks"].get("format_version")
        == args.required_format_version
    ]
    ood_data = LibrasUnlabeledDataset(ood_records, preprocessor)
    if len(ood_data) < args.min_ood_samples:
        raise DatasetQualityError(
            f"Somente {len(ood_data)} exemplos OOD; mínimo "
            f"{args.min_ood_samples}."
        )
    ood_loader = DataLoader(
        ood_data, batch_size=args.batch_size, shuffle=False
    )
    ood_probabilities, _, _ = collect_probabilities(
        model, ood_loader, device, labeled=False
    )
    rejection = calibrate_rejection(
        known_probabilities,
        known_targets,
        ood_probabilities,
        minimum_known_acceptance=args.minimum_known_acceptance,
        minimum_ood_recall=args.minimum_ood_recall,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    weights_path = args.output_dir / "librai_stgcn.pt"
    torch.save(best_state, weights_path)
    digest = hashlib.sha256(weights_path.read_bytes()).hexdigest()
    manifest = {
        "model_id": f"librai-stgcn-{digest[:12]}",
        "architecture": "ST-GCN",
        "feature_schema": "librai_holistic_v4",
        "training_format_version": args.required_format_version,
        "sequence_length": args.sequence_length,
        "labels": labels,
        "validation_trainers": validation_trainers,
        "validation_mode": args.validation_mode,
        "validation_accuracy": round(best_accuracy, 6),
        "validation_metrics": metrics,
        "rejection": rejection,
        "dataset_quality": quality,
        "quality_policy": asdict(policy),
        "weights_sha256": digest,
        "history": history,
        "status": "validated_not_deployed",
    }
    (args.output_dir / "model_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Modelo validado salvo em {weights_path}")
    return manifest


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument(
        "--ood-dataset",
        type=Path,
        required=True,
        help="Sequências v4 de sinais fora do vocabulário e movimentos não-sinais.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("ml/models/candidate"))
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--sequence-length", type=int, default=48)
    parser.add_argument("--required-format-version", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument("--min-classes", type=int, default=2)
    parser.add_argument("--min-trainers-per-class", type=int, default=3)
    parser.add_argument("--min-samples-per-class", type=int, default=15)
    parser.add_argument("--minimum-validation-accuracy", type=float, default=0.70)
    parser.add_argument("--min-ood-samples", type=int, default=30)
    parser.add_argument("--minimum-known-acceptance", type=float, default=0.70)
    parser.add_argument("--minimum-ood-recall", type=float, default=0.90)
    parser.add_argument(
        "--validation-mode",
        choices=("global-trainer", "per-class-trainer"),
        default="global-trainer",
        help=(
            "global-trainer é obrigatório para produção; per-class-trainer "
            "existe somente para pilotos experimentais."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())
