"""Inventaria vídeos privados e gera folhas de contato para revisão visual."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


SUPPORTED_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def inspect_video(path: Path, preview_dir: Path) -> dict:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return {"file": path.name, "status": "unreadable"}

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = frame_count / fps if fps > 0 else 0
    sample_count = min(9, max(3, round(duration / 30) + 2))
    frames = []
    for timestamp in np.linspace(0, max(duration - 0.1, 0), sample_count):
        capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp) * 1000)
        success, frame = capture.read()
        if not success:
            continue
        frame = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
        cv2.putText(
            frame,
            f"{timestamp:.1f}s",
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        frames.append(frame)
    capture.release()

    preview_path = None
    if frames:
        columns = 3
        rows = (len(frames) + columns - 1) // columns
        empty = np.zeros_like(frames[0])
        frames.extend([empty] * (rows * columns - len(frames)))
        sheet = np.vstack(
            [
                np.hstack(frames[row * columns:(row + 1) * columns])
                for row in range(rows)
            ]
        )
        preview_path = preview_dir / f"{path.stem[:80]}.jpg"
        cv2.imwrite(str(preview_path), sheet)

    return {
        "file": path.name,
        "status": "readable",
        "size_bytes": path.stat().st_size,
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "frame_count": frame_count,
        "duration_seconds": round(duration, 3),
        "preview": str(preview_path) if preview_path else None,
    }


def inventory(input_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_dir = output_dir / "previews"
    preview_dir.mkdir(exist_ok=True)
    videos = [
        path
        for path in sorted(input_dir.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    records = [inspect_video(path, preview_dir) for path in videos]
    report_path = output_dir / "video_inventory.json"
    report_path.write_text(
        json.dumps({"video_count": len(records), "videos": records}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"report": str(report_path), "videos": records}, indent=2))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    inventory(args.input_dir, args.output_dir)
