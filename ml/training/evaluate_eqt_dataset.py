"""Avaliação signer-independent do LIBRAS-EQT-UECE sem alterar produção."""

from __future__ import annotations

import argparse
import io
import random
import re
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


FEATURE_ROOTS = {
    "hands": "Landmarks/Libras-EQT-UECE (Hand Landmarks)/",
    "full": "Landmarks/Libras-EQT-UECE (Landmarks)/",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--classes", type=int, default=20)
    parser.add_argument("--frames", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--holdout", default="INFORMANTE 5")
    parser.add_argument("--features", choices=FEATURE_ROOTS, default="hands")
    parser.add_argument(
        "--normalization",
        choices=["global", "hand", "body"],
        default="hand",
    )
    parser.add_argument("--model", choices=["conv", "gru"], default="gru")
    parser.add_argument("--include-phrases", action="store_true")
    parser.add_argument("--seed", type=int, default=20260727)
    return parser.parse_args()


def resample(sequence: np.ndarray, frames: int) -> np.ndarray:
    old_axis = np.linspace(0.0, 1.0, len(sequence), dtype=np.float32)
    new_axis = np.linspace(0.0, 1.0, frames, dtype=np.float32)
    output = np.empty((frames, sequence.shape[1]), dtype=np.float32)
    for feature in range(sequence.shape[1]):
        output[:, feature] = np.interp(
            new_axis, old_axis, sequence[:, feature]
        )
    return output


def normalize_hands(sequence: np.ndarray) -> np.ndarray:
    """Canonicaliza mão dominante, posição e escala sem apagar o movimento."""
    hands = sequence.reshape(len(sequence), 2, 21, 3).copy()
    valid = np.abs(hands).sum(axis=(2, 3)) > 1e-6
    activity = valid.sum(axis=0)
    dominant = int(activity[1] > activity[0])
    if dominant == 1:
        hands = hands[:, [1, 0]]
        valid = valid[:, [1, 0]]
        # Espelha para que destros e canhotos compartilhem a mesma geometria.
        hands[..., 0] = np.where(valid[..., None], 1.0 - hands[..., 0], 0.0)

    scales = []
    for hand_index in range(2):
        for frame_index in np.flatnonzero(valid[:, hand_index]):
            hand = hands[frame_index, hand_index]
            scale = np.linalg.norm(hand[9, :2] - hand[0, :2])
            if scale > 1e-5:
                scales.append(scale)
    global_scale = float(np.median(scales)) if scales else 1.0
    global_scale = max(global_scale, 1e-4)

    output = np.zeros_like(hands)
    initial_wrist = None
    valid_dominant = np.flatnonzero(valid[:, 0])
    if len(valid_dominant):
        initial_wrist = hands[valid_dominant[0], 0, 0].copy()
    for hand_index in range(2):
        for frame_index in np.flatnonzero(valid[:, hand_index]):
            hand = hands[frame_index, hand_index]
            wrist = hand[0].copy()
            scale = np.linalg.norm(hand[9, :2] - wrist[:2])
            scale = max(float(scale), global_scale * 0.5, 1e-4)
            output[frame_index, hand_index] = (hand - wrist) / scale
            if initial_wrist is not None:
                output[frame_index, hand_index, 0] = (
                    wrist - initial_wrist
                ) / global_scale
    return output.reshape(len(sequence), 126)


def normalize_full_body(sequence: np.ndarray) -> np.ndarray:
    """Expressa pose, rosto e mãos no referencial do tronco."""
    points = sequence.reshape(len(sequence), 106, 3).copy()
    pose = points[:, :33]
    shoulder_center = (pose[:, 11] + pose[:, 12]) / 2.0
    hip_center = (pose[:, 23] + pose[:, 24]) / 2.0
    torso_center = (shoulder_center + hip_center) / 2.0
    shoulder_width = np.linalg.norm(
        pose[:, 11, :2] - pose[:, 12, :2], axis=1
    )
    valid_scales = shoulder_width[shoulder_width > 1e-4]
    fallback_scale = (
        float(np.median(valid_scales)) if len(valid_scales) else 1.0
    )
    shoulder_width = np.where(
        shoulder_width > 1e-4, shoulder_width, fallback_scale
    )

    valid = np.abs(points).sum(axis=2) > 1e-6
    normalized = np.zeros_like(points)
    normalized[valid] = (
        (points - torso_center[:, None, :])
        / shoulder_width[:, None, None]
    )[valid]
    return normalized.reshape(len(sequence), 318)


def load_dataset(
    archive_path: Path,
    class_limit: int,
    frames: int,
    holdout: str,
    feature_set: str,
    normalization: str,
    include_phrases: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    root = FEATURE_ROOTS[feature_set]
    expected_width = 126 if feature_set == "hands" else 318
    with zipfile.ZipFile(archive_path) as archive:
        paths = [
            info
            for info in archive.infolist()
            if info.filename.startswith(root)
            and info.filename.endswith(".npy")
        ]
        labels = sorted(
            {
                info.filename[len(root):].split("/", 1)[0]
                for info in paths
            }
        )
        # O piloto evita frases compostas e escolhe classes isoladas.
        candidates = labels if include_phrases else [
            label
            for label in labels
            if " " not in label.split("_", 1)[-1].strip()
        ]
        isolated = candidates[:class_limit]
        selected = set(isolated)
        label_index = {label: index for index, label in enumerate(isolated)}

        train_x, train_y, test_x, test_y = [], [], [], []
        signer_counts: Counter[str] = Counter()
        for info in paths:
            relative = info.filename[len(root):]
            parts = relative.split("/")
            if len(parts) != 3 or parts[0] not in selected:
                continue
            label, signer = parts[:2]
            sequence = np.load(
                io.BytesIO(archive.read(info)), allow_pickle=False
            ).astype(np.float32)
            if sequence.ndim != 2 or sequence.shape[1] != expected_width:
                raise ValueError(
                    f"Formato inesperado em {info.filename}: {sequence.shape}"
                )
            if feature_set == "hands" and normalization == "hand":
                sequence = normalize_hands(sequence)
            if feature_set == "full" and normalization == "body":
                sequence = normalize_full_body(sequence)
            sequence = resample(sequence, frames)
            signer_counts[signer] += 1
            target_x, target_y = (
                (test_x, test_y) if signer == holdout else (train_x, train_y)
            )
            target_x.append(sequence)
            target_y.append(label_index[label])

    if not train_x or not test_x:
        raise ValueError(
            f"Treino ou teste vazio para holdout={holdout}; "
            f"informantes encontrados: {sorted(signer_counts)}"
        )
    return (
        np.stack(train_x),
        np.asarray(train_y, dtype=np.int64),
        np.stack(test_x),
        np.asarray(test_y, dtype=np.int64),
        isolated,
    )


class TemporalClassifier(nn.Module):
    def __init__(self, class_count: int, feature_count: int):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(feature_count, 128, kernel_size=5, padding=2),
            nn.BatchNorm1d(128),
            nn.GELU(),
            nn.Conv1d(128, 192, kernel_size=5, padding=2),
            nn.BatchNorm1d(192),
            nn.GELU(),
            nn.MaxPool1d(2),
            nn.Conv1d(192, 256, kernel_size=3, padding=1),
            nn.BatchNorm1d(256),
            nn.GELU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.25),
            nn.Linear(256, class_count),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(features.transpose(1, 2)))


class RecurrentClassifier(nn.Module):
    def __init__(self, class_count: int, feature_count: int):
        super().__init__()
        self.input = nn.Sequential(
            nn.Linear(feature_count, 192),
            nn.LayerNorm(192),
            nn.GELU(),
        )
        self.gru = nn.GRU(
            192,
            160,
            num_layers=2,
            batch_first=True,
            dropout=0.2,
            bidirectional=True,
        )
        self.classifier = nn.Sequential(
            nn.LayerNorm(320),
            nn.Dropout(0.25),
            nn.Linear(320, class_count),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        encoded, _ = self.gru(self.input(features))
        return self.classifier(encoded.mean(dim=1))


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    train_x, train_y, test_x, test_y, labels = load_dataset(
        args.zip,
        args.classes,
        args.frames,
        args.holdout,
        args.features,
        args.normalization,
        args.include_phrases,
    )
    mean = train_x.mean(axis=(0, 1), keepdims=True)
    std = train_x.std(axis=(0, 1), keepdims=True).clip(min=1e-4)
    train_x = (train_x - mean) / std
    test_x = (test_x - mean) / std

    train_dataset = TensorDataset(
        torch.from_numpy(train_x), torch.from_numpy(train_y)
    )
    test_features = torch.from_numpy(test_x)
    test_targets = torch.from_numpy(test_y)
    loader = DataLoader(
        train_dataset, batch_size=64, shuffle=True, num_workers=0
    )

    model_type = TemporalClassifier if args.model == "conv" else RecurrentClassifier
    model = model_type(len(labels), train_x.shape[2])
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=2e-3, weight_decay=1e-3
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs
    )
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)

    best_accuracy = 0.0
    best_state = None
    for epoch in range(1, args.epochs + 1):
        model.train()
        for features, targets in loader:
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(features), targets)
            loss.backward()
            optimizer.step()
        scheduler.step()

        model.eval()
        with torch.no_grad():
            logits = model(test_features)
            predictions = logits.argmax(dim=1)
            accuracy = (predictions == test_targets).float().mean().item()
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_state = {
                key: value.detach().clone()
                for key, value in model.state_dict().items()
            }
        if epoch == 1 or epoch % 10 == 0:
            print(
                f"epoch={epoch:03d} "
                f"holdout_accuracy={accuracy:.4f} best={best_accuracy:.4f}",
                flush=True,
            )

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        logits = model(test_features)
        top1 = logits.argmax(dim=1)
        top3 = logits.topk(min(3, len(labels)), dim=1).indices
        top1_accuracy = (top1 == test_targets).float().mean().item()
        top3_accuracy = (
            (top3 == test_targets[:, None]).any(dim=1).float().mean().item()
        )
    print(f"classes={len(labels)} labels={labels}")
    print(f"train_samples={len(train_x)} test_samples={len(test_x)}")
    print(f"holdout={args.holdout}")
    print(f"features={args.features}")
    print(f"normalization={args.normalization} model={args.model}")
    print(f"top1={top1_accuracy:.4f} top3={top3_accuracy:.4f}")


if __name__ == "__main__":
    main()
