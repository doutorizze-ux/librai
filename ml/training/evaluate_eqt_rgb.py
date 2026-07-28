"""Evaluate LIBRAS-EQT-UECE RGB videos with signer-independent splits.

The ImageNet-pretrained MobileNetV3 encoder runs once per video and stores
temporal embeddings in a private cache. A lightweight temporal classifier is
then trained without ever mixing the held-out informant into the training set.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import io
import json
import random
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import av
import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small
from tqdm import tqdm


INFORMANT_RE = re.compile(r"INFORMANTE\s*(\d+)", re.IGNORECASE)
VIDEO_SUFFIXES = (".mp4", ".mov", ".avi", ".mkv")


@dataclass(frozen=True)
class VideoItem:
    member: str
    label: str
    informant: int


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def inventory(archive: zipfile.ZipFile) -> list[VideoItem]:
    items: list[VideoItem] = []
    for member in archive.namelist():
        if not member.lower().endswith(VIDEO_SUFFIXES):
            continue
        parts = Path(member).parts
        informant_index = next(
            (index for index, part in enumerate(parts) if INFORMANT_RE.search(part)),
            None,
        )
        if informant_index is None or informant_index == 0:
            continue
        match = INFORMANT_RE.search(parts[informant_index])
        assert match is not None
        items.append(
            VideoItem(
                member=member,
                label=parts[informant_index - 1].strip(),
                informant=int(match.group(1)),
            )
        )
    if not items:
        raise RuntimeError("No videos with an INFORMANTE folder were found.")
    return items


def decode_sampled_frames(video_bytes: bytes, frame_count: int) -> list[Image.Image]:
    with av.open(io.BytesIO(video_bytes)) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        if stream.frames:
            indexes = np.linspace(0, stream.frames - 1, frame_count).round().astype(int)
            requested = set(indexes.tolist())
            selected: dict[int, Image.Image] = {}
            for index, frame in enumerate(container.decode(stream)):
                if index in requested:
                    selected[index] = frame.to_image().convert("RGB")
                if index >= indexes[-1]:
                    break
            if selected:
                available = sorted(selected)
                return [
                    selected[min(available, key=lambda value: abs(value - index))]
                    for index in indexes
                ]

        # Some containers do not report a frame count. Keep the safe fallback.
        container.seek(0)
        frames = [frame.to_image().convert("RGB") for frame in container.decode(stream)]
        if not frames:
            raise RuntimeError("Video contains no decodable frames.")
        indexes = np.linspace(0, len(frames) - 1, frame_count).round().astype(int)
        return [frames[index] for index in indexes]


def get_encoder(device: torch.device):
    weights = MobileNet_V3_Small_Weights.DEFAULT
    model = mobilenet_v3_small(weights=weights)
    model.classifier = nn.Identity()
    model.eval().to(device)
    return model, weights.transforms()


def cache_path(cache_dir: Path, member: str) -> Path:
    digest = hashlib.sha256(member.encode("utf-8")).hexdigest()
    return cache_dir / digest[:2] / f"{digest}.npz"


@torch.no_grad()
def build_cache(
    zip_path: Path,
    items: list[VideoItem],
    cache_dir: Path,
    frame_count: int,
    batch_size: int,
    decode_workers: int,
    device: torch.device,
) -> None:
    encoder, transform = get_encoder(device)
    cache_dir.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, str]] = []

    pending = [item for item in items if not cache_path(cache_dir, item.member).exists()]
    group_size = max(1, decode_workers * 2)
    progress = tqdm(total=len(pending), desc="Encoding RGB videos")
    with (
        zipfile.ZipFile(zip_path) as archive,
        concurrent.futures.ThreadPoolExecutor(max_workers=decode_workers) as pool,
    ):
        for group_start in range(0, len(pending), group_size):
            group = pending[group_start : group_start + group_size]
            futures = {
                pool.submit(
                    decode_sampled_frames, archive.read(item.member), frame_count
                ): item
                for item in group
            }
            decoded: list[tuple[VideoItem, list[Image.Image]]] = []
            for future in concurrent.futures.as_completed(futures):
                item = futures[future]
                try:
                    decoded.append((item, future.result()))
                except Exception as exc:
                    failures.append({"member": item.member, "error": str(exc)})
                    progress.update(1)

            if not decoded:
                continue
            all_frames = [frame for _, frames in decoded for frame in frames]
            chunks: list[torch.Tensor] = []
            for start in range(0, len(all_frames), batch_size):
                tensor = torch.stack(
                    [transform(frame) for frame in all_frames[start : start + batch_size]]
                ).to(device)
                chunks.append(encoder(tensor).detach().cpu())
            all_embeddings = torch.cat(chunks)

            offset = 0
            for item, frames in decoded:
                embeddings = all_embeddings[offset : offset + len(frames)].float().numpy()
                offset += len(frames)
                target = cache_path(cache_dir, item.member)
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(".tmp.npz")
                np.savez_compressed(
                    temporary,
                    embeddings=embeddings,
                    label=item.label,
                    informant=item.informant,
                    member=item.member,
                )
                temporary.replace(target)
                progress.update(1)
    progress.close()

    (cache_dir / "failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if failures:
        print(f"WARNING: {len(failures)} videos failed; see failures.json")


class EmbeddingDataset(Dataset):
    def __init__(
        self,
        records: list[tuple[Path, int]],
    ) -> None:
        self.records = records

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int):
        path, label = self.records[index]
        with np.load(path) as data:
            embeddings = data["embeddings"].astype(np.float32)
        return torch.from_numpy(embeddings), label


class TemporalClassifier(nn.Module):
    def __init__(self, feature_dim: int, class_count: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv1d(feature_dim, 384, kernel_size=3, padding=1),
            nn.BatchNorm1d(384),
            nn.GELU(),
            nn.Dropout(0.25),
            nn.Conv1d(384, 256, kernel_size=3, padding=1),
            nn.BatchNorm1d(256),
            nn.GELU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Dropout(0.25),
            nn.Linear(256, class_count),
        )

    def forward(self, embeddings: torch.Tensor) -> torch.Tensor:
        return self.network(embeddings.transpose(1, 2))


def load_records(
    items: list[VideoItem],
    cache_dir: Path,
    holdout: int,
) -> tuple[list[tuple[Path, int]], list[tuple[Path, int]], list[str]]:
    labels = sorted({item.label for item in items})
    label_to_index = {label: index for index, label in enumerate(labels)}
    train: list[tuple[Path, int]] = []
    test: list[tuple[Path, int]] = []
    for item in items:
        path = cache_path(cache_dir, item.member)
        if not path.exists():
            continue
        record = (path, label_to_index[item.label])
        (test if item.informant == holdout else train).append(record)
    return train, test, labels


@torch.no_grad()
def evaluate(model, loader, device) -> tuple[float, float]:
    model.eval()
    total = top1 = top3 = 0
    for embeddings, labels in loader:
        logits = model(embeddings.to(device))
        labels = labels.to(device)
        predictions = logits.topk(min(3, logits.shape[1]), dim=1).indices
        top1 += (predictions[:, 0] == labels).sum().item()
        top3 += (predictions == labels[:, None]).any(dim=1).sum().item()
        total += labels.numel()
    return top1 / total, top3 / total


def train_temporal(
    items: list[VideoItem],
    cache_dir: Path,
    holdout: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    device: torch.device,
) -> dict[str, float | int]:
    train_records, test_records, labels = load_records(items, cache_dir, holdout)
    if not train_records or not test_records:
        raise RuntimeError("Empty train/test split after loading the embedding cache.")
    sample, _ = EmbeddingDataset(train_records)[0]
    model = TemporalClassifier(sample.shape[-1], len(labels)).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=1e-3
    )
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    train_loader = DataLoader(
        EmbeddingDataset(train_records),
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
    )
    test_loader = DataLoader(
        EmbeddingDataset(test_records),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )

    best = {"top1": 0.0, "top3": 0.0, "epoch": 0}
    for epoch in range(1, epochs + 1):
        model.train()
        for embeddings, targets in train_loader:
            embeddings, targets = embeddings.to(device), targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(embeddings), targets)
            loss.backward()
            optimizer.step()
        top1, top3 = evaluate(model, test_loader, device)
        if top1 > best["top1"]:
            best = {"top1": top1, "top3": top3, "epoch": epoch}
        print(
            f"epoch={epoch:03d} holdout={holdout} "
            f"top1={top1:.4%} top3={top3:.4%}"
        )
    return {
        **best,
        "holdout": holdout,
        "train_samples": len(train_records),
        "test_samples": len(test_records),
        "classes": len(labels),
    }


def choose_device(force_cpu: bool) -> torch.device:
    if force_cpu:
        return torch.device("cpu")
    try:
        import torch_directml

        return torch_directml.device()
    except Exception as exc:
        print(f"DirectML unavailable ({exc}); falling back to CPU.")
        return torch.device("cpu")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--encoder-batch-size", type=int, default=32)
    parser.add_argument("--decode-workers", type=int, default=4)
    parser.add_argument("--train-batch-size", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--holdout", type=int, default=5)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)
    device = choose_device(args.cpu)
    print(f"device={device}")
    with zipfile.ZipFile(args.zip) as archive:
        items = inventory(archive)
    print(
        f"videos={len(items)} classes={len({item.label for item in items})} "
        f"informants={sorted({item.informant for item in items})}"
    )
    build_cache(
        args.zip,
        items,
        args.cache_dir,
        args.frames,
        args.encoder_batch_size,
        args.decode_workers,
        device,
    )
    if args.cache_only:
        return
    result = train_temporal(
        items,
        args.cache_dir,
        args.holdout,
        args.epochs,
        args.train_batch_size,
        args.learning_rate,
        device,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
