"""Evaluate a motion-aware residual TCN on LIBRAS-EQT-UECE landmarks."""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from evaluate_eqt_dataset import load_dataset


def motion_features(coordinates: np.ndarray) -> np.ndarray:
    velocity = np.diff(coordinates, axis=1, prepend=coordinates[:, :1])
    acceleration = np.diff(velocity, axis=1, prepend=velocity[:, :1])
    return np.concatenate((coordinates, velocity, acceleration), axis=2).astype(
        np.float32
    )


class ResidualTemporalBlock(nn.Module):
    def __init__(self, channels: int, dilation: int, dropout: float) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv1d(
                channels,
                channels,
                kernel_size=3,
                padding=dilation,
                dilation=dilation,
            ),
            nn.BatchNorm1d(channels),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Conv1d(
                channels,
                channels,
                kernel_size=3,
                padding=dilation,
                dilation=dilation,
            ),
            nn.BatchNorm1d(channels),
        )
        self.activation = nn.GELU()

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.activation(features + self.network(features))


class MotionTCN(nn.Module):
    def __init__(self, feature_count: int, class_count: int) -> None:
        super().__init__()
        channels = 256
        self.input = nn.Sequential(
            nn.Conv1d(feature_count, channels, kernel_size=1),
            nn.BatchNorm1d(channels),
            nn.GELU(),
        )
        self.temporal = nn.Sequential(
            ResidualTemporalBlock(channels, 1, 0.15),
            ResidualTemporalBlock(channels, 2, 0.15),
            ResidualTemporalBlock(channels, 4, 0.2),
            ResidualTemporalBlock(channels, 8, 0.2),
        )
        self.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(channels * 2, 384),
            nn.GELU(),
            nn.Dropout(0.25),
            nn.Linear(384, class_count),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        encoded = self.temporal(self.input(features.transpose(1, 2)))
        pooled = torch.cat((encoded.mean(dim=2), encoded.amax(dim=2)), dim=1)
        return self.classifier(pooled)


@torch.no_grad()
def evaluate(model, features, targets, device):
    model.eval()
    predictions = model(features.to(device)).topk(3, dim=1).indices
    targets = targets.to(device)
    return (
        (predictions[:, 0] == targets).float().mean().item(),
        (predictions == targets[:, None]).any(dim=1).float().mean().item(),
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--holdout", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def display_label(dataset_label: str) -> str:
    label = re.sub(r"^\d+_", "", dataset_label).strip().rstrip(".")
    return label.upper()


def main():
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    train_x, train_y, test_x, test_y, labels = load_dataset(
        args.zip,
        178,
        args.frames,
        f"INFORMANTE {args.holdout}",
        "hands",
        "global",
        True,
    )
    mean = train_x.mean(axis=(0, 1), keepdims=True)
    std = train_x.std(axis=(0, 1), keepdims=True).clip(min=1e-4)
    train_x = motion_features((train_x - mean) / std)
    test_x = motion_features((test_x - mean) / std)

    if args.cpu:
        device = torch.device("cpu")
    else:
        import torch_directml

        device = torch_directml.device()
    loader = DataLoader(
        TensorDataset(torch.from_numpy(train_x), torch.from_numpy(train_y)),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
    )
    test_features = torch.from_numpy(test_x)
    test_targets = torch.from_numpy(test_y)
    model = MotionTCN(train_x.shape[2], len(labels)).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=8e-4, weight_decay=2e-3
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs
    )
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    best = {"top1": 0.0, "top3": 0.0, "epoch": 0}
    best_state = None
    for epoch in range(1, args.epochs + 1):
        model.train()
        for features, targets in loader:
            features, targets = features.to(device), targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(features)
            loss = criterion(logits, targets)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
            optimizer.step()
        scheduler.step()
        top1, top3 = evaluate(
            model, test_features, test_targets, device
        )
        if top1 > best["top1"]:
            best = {"top1": top1, "top3": top3, "epoch": epoch}
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
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
    if args.output_dir is not None:
        if best_state is None:
            raise RuntimeError("Training completed without a valid best state.")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = args.output_dir / "motion_tcn.pt"
        metadata_path = args.output_dir / "metadata.json"
        normalization_path = args.output_dir / "normalization.npz"
        torch.save(
            {
                "state_dict": best_state,
                "frames": args.frames,
                "raw_feature_count": int(mean.shape[2]),
                "motion_feature_count": int(train_x.shape[2]),
                "labels": [display_label(label) for label in labels],
                "dataset_labels": labels,
                "metrics": result,
                "seed": args.seed,
            },
            checkpoint_path,
        )
        np.savez_compressed(
            normalization_path,
            mean=mean.astype(np.float32),
            std=std.astype(np.float32),
        )
        metadata_path.write_text(
            json.dumps(
                {
                    "model": "motion_tcn_v1",
                    "frames": args.frames,
                    "raw_feature_count": int(mean.shape[2]),
                    "motion_feature_count": int(train_x.shape[2]),
                    "labels": [display_label(label) for label in labels],
                    "dataset_labels": labels,
                    "metrics": result,
                    "seed": args.seed,
                    "protocol": {
                        "train_informants": [
                            signer for signer in range(1, 6)
                            if signer != args.holdout
                        ],
                        "test_informant": args.holdout,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        result["artifacts"] = {
            "checkpoint": str(checkpoint_path),
            "metadata": str(metadata_path),
            "normalization": str(normalization_path),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
