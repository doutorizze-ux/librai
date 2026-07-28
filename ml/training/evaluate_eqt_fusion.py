"""Signer-independent fusion of RGB embeddings and official hand landmarks."""

from __future__ import annotations

import argparse
import io
import json
import random
import re
import zipfile
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm


INFORMANT_RE = re.compile(r"INFORMANTE\s*(\d+)", re.IGNORECASE)
CLASS_RE = re.compile(r"^(\d+)_")
HAND_ROOT = "Landmarks/Libras-EQT-UECE (Hand Landmarks)/"


def sequence_key(member: str) -> tuple[int, int, str]:
    parts = Path(member).parts
    informant_index = next(
        index for index, part in enumerate(parts) if INFORMANT_RE.search(part)
    )
    class_match = CLASS_RE.search(parts[informant_index - 1])
    informant_match = INFORMANT_RE.search(parts[informant_index])
    if class_match is None or informant_match is None:
        raise ValueError(f"Unrecognized dataset path: {member}")
    return (
        int(class_match.group(1)),
        int(informant_match.group(1)),
        Path(member).stem.casefold(),
    )


def resample(sequence: np.ndarray, frame_count: int) -> np.ndarray:
    positions = np.linspace(0, len(sequence) - 1, frame_count, dtype=np.float32)
    left = np.floor(positions).astype(np.int64)
    right = np.minimum(left + 1, len(sequence) - 1)
    alpha = (positions - left)[:, None]
    return (
        sequence[left] * (1.0 - alpha) + sequence[right] * alpha
    ).astype(np.float32)


def load_dataset(
    landmarks_zip: Path,
    rgb_cache: Path,
    frame_count: int,
    holdout: int,
):
    cache_records: dict[tuple[int, int, str], tuple[np.ndarray, str]] = {}
    for path in tqdm(list(rgb_cache.rglob("*.npz")), desc="Loading RGB cache"):
        with np.load(path) as data:
            member = str(data["member"].item())
            cache_records[sequence_key(member)] = (
                data["embeddings"].astype(np.float32),
                str(data["label"].item()),
            )

    samples: list[tuple[np.ndarray, np.ndarray, int, int]] = []
    labels: dict[int, str] = {}
    with zipfile.ZipFile(landmarks_zip) as archive:
        members = [
            name
            for name in archive.namelist()
            if name.startswith(HAND_ROOT) and name.endswith(".npy")
        ]
        for member in tqdm(members, desc="Pairing hand landmarks"):
            key = sequence_key(member)
            rgb_record = cache_records.get(key)
            if rgb_record is None:
                raise RuntimeError(f"Missing RGB pair for {member}")
            rgb, rgb_label = rgb_record
            hands = np.load(
                io.BytesIO(archive.read(member)), allow_pickle=False
            ).astype(np.float32)
            if hands.ndim != 2 or hands.shape[1] != 126:
                raise ValueError(f"Unexpected hand shape {hands.shape}: {member}")
            class_number, informant, _ = key
            labels[class_number] = rgb_label
            samples.append(
                (
                    resample(hands, frame_count),
                    resample(rgb, frame_count),
                    class_number,
                    informant,
                )
            )

    class_numbers = sorted(labels)
    class_index = {number: index for index, number in enumerate(class_numbers)}
    train = [sample for sample in samples if sample[3] != holdout]
    test = [sample for sample in samples if sample[3] == holdout]

    def stack(split):
        return (
            np.stack([item[0] for item in split]),
            np.stack([item[1] for item in split]),
            np.asarray([class_index[item[2]] for item in split], dtype=np.int64),
        )

    return (*stack(train), *stack(test), [labels[number] for number in class_numbers])


class FusionClassifier(nn.Module):
    def __init__(self, class_count: int, rgb_feature_count: int) -> None:
        super().__init__()
        self.hands = nn.Sequential(
            nn.Conv1d(126, 128, kernel_size=5, padding=2),
            nn.BatchNorm1d(128),
            nn.GELU(),
            nn.Conv1d(128, 192, kernel_size=5, padding=2),
            nn.BatchNorm1d(192),
            nn.GELU(),
            nn.Conv1d(192, 256, kernel_size=3, padding=1),
            nn.BatchNorm1d(256),
            nn.GELU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.rgb = nn.Sequential(
            nn.Conv1d(rgb_feature_count, 192, kernel_size=3, padding=1),
            nn.BatchNorm1d(192),
            nn.GELU(),
            nn.Conv1d(192, 256, kernel_size=3, padding=1),
            nn.BatchNorm1d(256),
            nn.GELU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.GELU(),
            nn.Dropout(0.25),
            nn.Linear(256, class_count),
        )

    def forward(self, hands: torch.Tensor, rgb: torch.Tensor) -> torch.Tensor:
        hands = self.hands(hands.transpose(1, 2))
        rgb = self.rgb(rgb.transpose(1, 2))
        return self.classifier(torch.cat([hands, rgb], dim=1))


@torch.no_grad()
def accuracy(model, hands, rgb, targets, device):
    model.eval()
    predictions = model(hands.to(device), rgb.to(device)).topk(3, dim=1).indices
    targets = targets.to(device)
    return (
        (predictions[:, 0] == targets).float().mean().item(),
        (predictions == targets[:, None]).any(dim=1).float().mean().item(),
    )


def standardize(train: np.ndarray, test: np.ndarray):
    mean = train.mean(axis=(0, 1), keepdims=True)
    std = train.std(axis=(0, 1), keepdims=True).clip(min=1e-4)
    return (train - mean) / std, (test - mean) / std


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--landmarks-zip", type=Path, required=True)
    parser.add_argument("--rgb-cache", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=64)
    parser.add_argument("--holdout", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument("--cpu", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if args.cpu:
        device = torch.device("cpu")
    else:
        import torch_directml

        device = torch_directml.device()
    (
        train_hands,
        train_rgb,
        train_y,
        test_hands,
        test_rgb,
        test_y,
        labels,
    ) = load_dataset(
        args.landmarks_zip, args.rgb_cache, args.frames, args.holdout
    )
    train_hands, test_hands = standardize(train_hands, test_hands)
    train_rgb, test_rgb = standardize(train_rgb, test_rgb)
    loader = DataLoader(
        TensorDataset(
            torch.from_numpy(train_hands),
            torch.from_numpy(train_rgb),
            torch.from_numpy(train_y),
        ),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
    )
    test_tensors = (
        torch.from_numpy(test_hands),
        torch.from_numpy(test_rgb),
        torch.from_numpy(test_y),
    )
    model = FusionClassifier(len(labels), train_rgb.shape[2]).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=1e-3, weight_decay=1e-3
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs
    )
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    best = {"top1": 0.0, "top3": 0.0, "epoch": 0}
    for epoch in range(1, args.epochs + 1):
        model.train()
        for hands, rgb, targets in loader:
            hands, rgb, targets = hands.to(device), rgb.to(device), targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(hands, rgb), targets)
            loss.backward()
            optimizer.step()
        scheduler.step()
        top1, top3 = accuracy(model, *test_tensors, device)
        if top1 > best["top1"]:
            best = {"top1": top1, "top3": top3, "epoch": epoch}
        print(
            f"epoch={epoch:03d} top1={top1:.4%} top3={top3:.4%}",
            flush=True,
        )
    result = {
        **best,
        "holdout": args.holdout,
        "train_samples": len(train_y),
        "test_samples": len(test_y),
        "classes": len(labels),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
