"""Descobre rótulos visíveis nos vídeos sem criar exemplos de treino ainda."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import cv2
import easyocr

from inventory_videos import SUPPORTED_SUFFIXES


LABEL_PATTERN = re.compile(
    r"(?:^|\d{1,3}\s*[\.,:\-]\s*)"
    r"([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ ]{1,35})"
)
IGNORED = {
    "LIBRAS", "INICIANTES", "APRENDA", "SINAIS", "SINAL", "PARA",
    "YOUTUBE", "DÉBORA LIBRAS", "NETO LIBRAS", "ACADEMIA DE LIBRAS",
}


def normalize_label(value: str) -> str | None:
    value = unicodedata.normalize("NFC", value.upper())
    value = re.sub(r"[^A-ZÁÀÂÃÉÊÍÓÔÕÚÇ0-9 .,:-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    match = LABEL_PATTERN.search(value)
    if not match:
        return None
    label = match.group(1).strip()
    if label in IGNORED or len(label) < 2:
        return None
    return label


def sample_interval(duration: float) -> float:
    if duration > 600:
        return 4.0
    if duration > 120:
        return 3.0
    if duration > 15:
        return 5.0
    return 2.0


def scan_video(path: Path, reader) -> dict:
    capture = cv2.VideoCapture(str(path))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if fps else 0
    interval = sample_interval(duration)
    observations = []
    timestamp = 0.0
    while timestamp < duration:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        success, frame = capture.read()
        if not success:
            timestamp += interval
            continue
        height, width = frame.shape[:2]
        # Aulas horizontais mantêm o rótulo na faixa superior. Shorts em grade
        # podem conter rótulos por toda a imagem e são analisados integralmente.
        landscape = width > height
        if landscape:
            y_offset = round(height * 0.12)
            x_offset = round(width * 0.07)
            roi = frame[
                y_offset:round(height * 0.27),
                x_offset:round(width * 0.50),
            ]
        else:
            x_offset = 0
            y_offset = round(height * 0.24) if duration > 15 else 0
            roi = frame[y_offset:round(height * 0.82)] if duration > 15 else frame
        original_roi_width = roi.shape[1]
        if roi.shape[1] > 540:
            resize_scale = 540 / roi.shape[1]
            roi = cv2.resize(
                roi, None, fx=resize_scale, fy=resize_scale
            )
        ocr_options = {
            "detail": 1,
            "allowlist": (
                "ABCDEFGHIJKLMNOPQRSTUVWXYZÁÀÂÃÉÊÍÓÔÕÚÇ"
                "abcdefghijklmnopqrstuvwxyzáàâãéêíóôõúç0123456789 .,-:"
            ),
        }
        # Nas aulas horizontais o título tem posição estável; reconhecer a
        # região diretamente evita executar o detector de texto centenas de vezes.
        detections = (
            reader.recognize(roi, **ocr_options)
            if landscape
            else reader.readtext(roi, paragraph=False, **ocr_options)
        )
        for box, text, confidence in detections:
            label = normalize_label(text)
            minimum_confidence = 0.08 if landscape else 0.35
            if label is None or float(confidence) < minimum_confidence:
                continue
            # EasyOCR devolve coordenadas relativas ao ROI redimensionado.
            # Convertemos novamente para o frame original antes de salvar.
            inverse_scale = original_roi_width / roi.shape[1]
            xs = [
                float(point[0]) * inverse_scale + x_offset for point in box
            ]
            ys = [
                float(point[1]) * inverse_scale + y_offset for point in box
            ]
            observations.append(
                {
                    "timestamp_seconds": round(timestamp, 3),
                    "label": label,
                    "ocr_text": text,
                    "confidence": round(float(confidence), 4),
                    "box": [
                        round(min(xs), 1), round(min(ys), 1),
                        round(max(xs), 1), round(max(ys), 1),
                    ],
                }
            )
        timestamp += interval
    capture.release()
    grouped = defaultdict(list)
    for item in observations:
        grouped[item["label"]].append(item["timestamp_seconds"])
    return {
        "file": path.name,
        "duration_seconds": round(duration, 3),
        "sample_interval_seconds": interval,
        "observations": observations,
        "candidate_labels": {
            label: {"count": len(times), "first": min(times), "last": max(times)}
            for label, times in sorted(grouped.items())
        },
    }


def excluded_videos(dataset_paths: list[Path]) -> set[str]:
    excluded: set[str] = set()
    for path in dataset_paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        excluded.update(
            str(sample["source_video"])
            for sample in payload.get("samples", [])
            if sample.get("source_video")
        )
        excluded.update(
            str(video["file"])
            for video in payload.get("videos", [])
            if video.get("file")
        )
    return excluded


def discover(
    input_dir: Path,
    output: Path,
    exclude_datasets: list[Path] | None = None,
    include_segment_reports: list[Path] | None = None,
):
    excluded = excluded_videos(exclude_datasets or [])
    included: set[str] = set()
    for path in include_segment_reports or []:
        payload = json.loads(path.read_text(encoding="utf-8"))
        included.update(
            str(segment["video"])
            for segment in payload.get("segments", [])
            if segment.get("mode") == "spatial_grid" and segment.get("video")
        )
    videos = [
        path for path in sorted(input_dir.iterdir())
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED_SUFFIXES
            and path.name not in excluded
            and (not included or path.name in included)
        )
    ]
    reader = easyocr.Reader(["pt"], gpu=False, verbose=False)
    results = []
    for index, path in enumerate(videos, start=1):
        print(f"[{index}/{len(videos)}] analisando video", flush=True)
        results.append(scan_video(path, reader))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"video_count": len(results), "videos": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Relatório: {output}", flush=True)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--exclude-dataset",
        action="append",
        default=[],
        type=Path,
        help="Ignora vídeos já referenciados em um dataset extraído.",
    )
    parser.add_argument(
        "--include-spatial-from",
        action="append",
        default=[],
        type=Path,
        help="Inclui somente vídeos marcados como spatial_grid no relatório.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    discover(
        args.input_dir,
        args.output,
        args.exclude_dataset,
        args.include_spatial_from,
    )
