"""Encode landmark-guided hand crops from LIBRAS-EQT-UECE RGB videos."""

from __future__ import annotations

import argparse
import concurrent.futures
import io
import json
import zipfile
from pathlib import Path

import av
import numpy as np
import torch
from PIL import Image
from torchvision import transforms
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small
from tqdm import tqdm

from evaluate_eqt_fusion import sequence_key
from evaluate_eqt_rgb import (
    VideoItem,
    cache_path,
    choose_device,
    inventory,
    train_temporal,
)


HAND_ROOT = "Landmarks/Libras-EQT-UECE (Hand Landmarks)/"


def crop_hand(frame: Image.Image, points: np.ndarray) -> Image.Image:
    valid = np.abs(points).sum(axis=1) > 1e-6
    if valid.sum() < 5:
        return Image.new("RGB", (160, 160), "black")
    width, height = frame.size
    xy = points[valid, :2]
    x_min, y_min = xy.min(axis=0)
    x_max, y_max = xy.max(axis=0)
    center_x = float((x_min + x_max) * 0.5 * width)
    center_y = float((y_min + y_max) * 0.5 * height)
    side = max(
        float((x_max - x_min) * width),
        float((y_max - y_min) * height),
        min(width, height) * 0.16,
    ) * 1.8
    return frame.crop(
        (
            center_x - side / 2,
            center_y - side / 2,
            center_x + side / 2,
            center_y + side / 2,
        )
    )


def decode_crops(
    video_bytes: bytes,
    landmark_bytes: bytes,
    frame_count: int,
) -> list[Image.Image]:
    landmarks = np.load(io.BytesIO(landmark_bytes), allow_pickle=False).astype(
        np.float32
    )
    if landmarks.ndim != 2 or landmarks.shape[1] != 126:
        raise ValueError(f"Unexpected hand landmarks: {landmarks.shape}")
    hands = landmarks.reshape(len(landmarks), 2, 21, 3)
    indexes = np.linspace(0, len(hands) - 1, frame_count).round().astype(int)
    requested = set(indexes.tolist())
    frames: dict[int, Image.Image] = {}
    with av.open(io.BytesIO(video_bytes)) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        for index, frame in enumerate(container.decode(stream)):
            if index in requested:
                frames[index] = frame.to_image().convert("RGB")
            if index >= indexes[-1]:
                break
    if not frames:
        raise RuntimeError("Video contains no decodable frames.")
    available = sorted(frames)
    crops: list[Image.Image] = []
    for index in indexes:
        actual = min(available, key=lambda value: abs(value - index))
        frame = frames[actual]
        crops.append(crop_hand(frame, hands[actual, 0]))
        crops.append(crop_hand(frame, hands[actual, 1]))
    return crops


def hand_members(archive: zipfile.ZipFile) -> dict[tuple[int, int, str], str]:
    return {
        sequence_key(name): name
        for name in archive.namelist()
        if name.startswith(HAND_ROOT) and name.endswith(".npy")
    }


@torch.no_grad()
def build_cache(
    rgb_zip: Path,
    landmarks_zip: Path,
    items: list[VideoItem],
    cache_dir: Path,
    frame_count: int,
    encoder_batch_size: int,
    decode_workers: int,
    device: torch.device,
) -> None:
    model = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
    model.classifier = torch.nn.Identity()
    model.eval().to(device)
    transform = transforms.Compose(
        [
            transforms.Resize((160, 160), antialias=True),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=(0.485, 0.456, 0.406),
                std=(0.229, 0.224, 0.225),
            ),
        ]
    )
    pending = [
        item for item in items if not cache_path(cache_dir, item.member).exists()
    ]
    failures: list[dict[str, str]] = []
    group_size = max(1, decode_workers * 2)
    progress = tqdm(total=len(pending), desc="Encoding landmark-guided hand crops")
    cache_dir.mkdir(parents=True, exist_ok=True)
    with (
        zipfile.ZipFile(rgb_zip) as rgb_archive,
        zipfile.ZipFile(landmarks_zip) as landmark_archive,
        concurrent.futures.ThreadPoolExecutor(max_workers=decode_workers) as pool,
    ):
        landmark_index = hand_members(landmark_archive)
        for start in range(0, len(pending), group_size):
            group = pending[start : start + group_size]
            futures = {}
            for item in group:
                key = sequence_key(item.member)
                landmark_member = landmark_index.get(key)
                if landmark_member is None:
                    failures.append(
                        {"member": item.member, "error": "Missing landmark pair"}
                    )
                    progress.update(1)
                    continue
                future = pool.submit(
                    decode_crops,
                    rgb_archive.read(item.member),
                    landmark_archive.read(landmark_member),
                    frame_count,
                )
                futures[future] = item

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

            all_crops = [crop for _, crops in decoded for crop in crops]
            chunks = []
            for crop_start in range(0, len(all_crops), encoder_batch_size):
                tensor = torch.stack(
                    [
                        transform(crop)
                        for crop in all_crops[
                            crop_start : crop_start + encoder_batch_size
                        ]
                    ]
                ).to(device)
                chunks.append(model(tensor).detach().cpu())
            encoded = torch.cat(chunks)

            offset = 0
            for item, crops in decoded:
                crop_embeddings = encoded[offset : offset + len(crops)]
                offset += len(crops)
                embeddings = (
                    crop_embeddings.reshape(frame_count, 2, -1)
                    .reshape(frame_count, -1)
                    .float()
                    .numpy()
                )
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
        raise RuntimeError(
            f"{len(failures)} videos failed; inspect {cache_dir / 'failures.json'}"
        )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rgb-zip", type=Path, required=True)
    parser.add_argument("--landmarks-zip", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--encoder-batch-size", type=int, default=64)
    parser.add_argument("--decode-workers", type=int, default=4)
    parser.add_argument("--train-batch-size", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--holdout", type=int, default=5)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    device = choose_device(args.cpu)
    with zipfile.ZipFile(args.rgb_zip) as archive:
        items = inventory(archive)
    print(
        f"device={device} videos={len(items)} "
        f"classes={len({item.label for item in items})}"
    )
    build_cache(
        args.rgb_zip,
        args.landmarks_zip,
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
        3e-4,
        device,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
