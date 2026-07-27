"""Recorta mosaicos rotulados e extrai landmarks v3 de cada célula."""

from __future__ import annotations

import argparse
import json
import uuid
from collections import Counter, defaultdict
from pathlib import Path

import cv2

from extract_holistic_dataset import (
    HolisticExtractor,
    clean_label,
    creator_for,
)


def cluster_axis(values: list[float], tolerance: float = 65.0) -> list[float]:
    clusters: list[list[float]] = []
    for value in sorted(values):
        if not clusters or value - sum(clusters[-1]) / len(clusters[-1]) > tolerance:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return [sum(cluster) / len(cluster) for cluster in clusters]


def nearest_index(value: float, centers: list[float]) -> int:
    return min(range(len(centers)), key=lambda index: abs(centers[index] - value))


def build_layouts(candidates: list[dict]) -> dict[str, dict[str, list[float]]]:
    grouped = defaultdict(list)
    for candidate in candidates:
        grouped[candidate["video"]].append(candidate)
    return {
        video: {
            "x": cluster_axis([
                (item["box"][0] + item["box"][2]) / 2 for item in items
            ]),
            "y": cluster_axis([
                (item["box"][1] + item["box"][3]) / 2 for item in items
            ]),
        }
        for video, items in grouped.items()
    }


def crop_cell(frame, candidate, x_centers, y_centers):
    height, width = frame.shape[:2]
    box = candidate["box"]
    center_x = (box[0] + box[2]) / 2
    center_y = (box[1] + box[3]) / 2
    column = nearest_index(center_x, x_centers)
    row = nearest_index(center_y, y_centers)
    x0 = round(column * width / len(x_centers))
    x1 = round((column + 1) * width / len(x_centers))
    y0 = round(row * height / len(y_centers))
    y1 = round((row + 1) * height / len(y_centers))
    return frame[y0:y1, x0:x1], {
        "columns": len(x_centers),
        "rows": len(y_centers),
        "column": column,
        "row": row,
    }


def extract_candidate(video_path, candidate, extractor, layout, target_fps=3):
    capture = cv2.VideoCapture(str(video_path))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    start = max(0.0, float(candidate["start_seconds"]))
    duration = min(float(candidate["end_seconds"]), start + 8.0)
    if fps <= 0:
        capture.release()
        return None, "fps_invalid"
    timestamps = []
    timestamp = start
    while timestamp <= duration and len(timestamps) < 144:
        timestamps.append(timestamp)
        timestamp += 1 / target_fps
    frames = []
    hand_frames = 0
    pose_frames = 0
    crop_metadata = None
    for timestamp in timestamps:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        success, frame = capture.read()
        if not success:
            continue
        cropped, crop_metadata = crop_cell(
            frame, candidate, layout["x"], layout["y"]
        )
        if cropped.size == 0:
            continue
        if cropped.shape[1] < 640:
            scale = 640 / cropped.shape[1]
            cropped = cv2.resize(
                cropped, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
            )
        extracted = extractor.frame(
            cropped, round((timestamp - timestamps[0]) * 1000)
        )
        if extracted["hands"]:
            hand_frames += 1
        if any(item["x"] or item["y"] for item in extracted["pose"]["landmarks"]):
            pose_frames += 1
        frames.append(extracted)
    capture.release()
    if len(frames) < 12:
        return None, "too_few_frames"
    hand_ratio = hand_frames / len(frames)
    pose_ratio = pose_frames / len(frames)
    if hand_frames < 4 or hand_ratio < 0.20:
        return None, f"hands_low:{hand_ratio:.2f}"
    if pose_ratio < 0.65:
        return None, f"pose_low:{pose_ratio:.2f}"
    return {
        "format_version": 3,
        "frames": frames,
        "quality": {
            "hand_frame_ratio": round(hand_ratio, 4),
            "pose_frame_ratio": round(pose_ratio, 4),
            "spatial_crop": crop_metadata,
        },
    }, None


def build(
    segments_path,
    video_dir,
    model_dir,
    output_path,
    rejected_path,
    limit=None,
    shard_index=0,
    shard_count=1,
):
    source = json.loads(segments_path.read_text(encoding="utf-8"))
    all_candidates = [
        item for item in source["segments"] if item["mode"] == "spatial_grid"
    ]
    layouts = build_layouts(all_candidates)
    # A geometria precisa ser calculada com todas as células. Só então o
    # processamento pesado pode ser dividido em shards independentes.
    candidates = [
        item for index, item in enumerate(all_candidates)
        if index % shard_count == shard_index
    ]
    if limit is not None:
        candidates = candidates[:limit]
    videos = {path.name: path for path in video_dir.iterdir() if path.is_file()}
    extractor = HolisticExtractor(model_dir)
    samples, rejected = [], []
    try:
        for index, candidate in enumerate(candidates, start=1):
            print(f"[{index}/{len(candidates)}] {candidate['id']}", flush=True)
            payload, reason = extract_candidate(
                videos[candidate["video"]],
                candidate,
                extractor,
                layouts[candidate["video"]],
            )
            if payload is None:
                rejected.append({**candidate, "rejection_reason": reason})
                continue
            samples.append(
                {
                    "id": str(uuid.uuid4()),
                    "sign_name": clean_label(candidate["label"]),
                    "trainer_name": creator_for(candidate["video"]),
                    "source_segment_id": candidate["id"],
                    "source_video": candidate["video"],
                    "frame_count": len(payload["frames"]),
                    "landmarks": payload,
                }
            )
    finally:
        extractor.close()
    output_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "sample_count": len(samples),
                "class_counts": dict(sorted(Counter(
                    sample["sign_name"] for sample in samples
                ).items())),
                "samples": samples,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rejected_path.write_text(
        json.dumps({"segments": rejected}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Extraídos={len(samples)} rejeitados={len(rejected)}", flush=True)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("segments", type=Path)
    parser.add_argument("video_dir", type=Path)
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("rejected", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build(
        args.segments,
        args.video_dir,
        args.model_dir,
        args.output,
        args.rejected,
        args.limit,
        args.shard_index,
        args.shard_count,
    )
