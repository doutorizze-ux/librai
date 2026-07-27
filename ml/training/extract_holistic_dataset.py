"""Extrai dataset v3 de segmentos aprováveis sem armazenar malha facial bruta."""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
import uuid
from collections import Counter
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


POSE_INDICES = (0, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 23, 24)
CREATORS = {
    "DÉBORA LIBRAS": "Débora Libras",
    "NETO LIBRAS": "Neto Libras",
    "JHON LIBRAS": "Jhon Libras",
    "ACADEMIA DE LIBRAS": "Academia de Libras",
}


def creator_for(filename: str) -> str:
    normalized = unicodedata.normalize("NFKD", filename.upper())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    for key, creator in CREATORS.items():
        plain_key = unicodedata.normalize("NFKD", key)
        plain_key = "".join(c for c in plain_key if not unicodedata.combining(c))
        if plain_key in normalized:
            return creator
    return "Fonte autorizada"


def clean_label(label: str) -> str:
    label = re.sub(r"\s+[A-Z]$", "", label.strip().upper())
    replacements = {
        "BOA NOIE": "BOA NOITE",
        "TUDO BEMP": "TUDO BEM",
        "TUDO BEMZ": "TUDO BEM",
        "SEU NOMER": "SEU NOME",
        "SEU NOMEZ": "SEU NOME",
        "PROV": "PROVA",
        "ATIVIDADEI": "ATIVIDADE",
        "OBRIGADOCAJ": "OBRIGADO",
        "OBRIGADAI": "OBRIGADO",
        "AJUDAR SOS": "AJUDAR",
        "GHATO": "CHATO",
        "ENADO": "ERRADO",
        "JAONDE": "AONDE",
    }
    return replacements.get(label, label)


def point(landmark):
    return {
        "x": round(float(landmark.x), 6),
        "y": round(float(landmark.y), 6),
        "z": round(float(landmark.z), 6),
    }


def distance(first, second):
    return math.sqrt(
        (first.x - second.x) ** 2
        + (first.y - second.y) ** 2
        + (first.z - second.z) ** 2
    )


def expression_features(face):
    if not face or len(face) < 455:
        return {
            "mouth_open": 0.0,
            "mouth_width": 0.0,
            "left_brow": 0.0,
            "right_brow": 0.0,
        }
    width = max(distance(face[234], face[454]), 1e-6)
    return {
        "mouth_open": round(min(distance(face[13], face[14]) / width, 2), 6),
        "mouth_width": round(min(distance(face[61], face[291]) / width, 2), 6),
        "left_brow": round(
            max(-1, min(distance(face[105], face[159]) / width, 1)), 6
        ),
        "right_brow": round(
            max(-1, min(distance(face[334], face[386]) / width, 1)), 6
        ),
    }


class HolisticExtractor:
    def __init__(self, model_dir: Path):
        base = python.BaseOptions
        self.hand = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=base(
                    model_asset_path=str(model_dir / "hand_landmarker.task")
                ),
                running_mode=vision.RunningMode.IMAGE,
                num_hands=2,
                min_hand_detection_confidence=0.45,
                min_hand_presence_confidence=0.45,
            )
        )
        self.pose = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(
                base_options=base(
                    model_asset_path=str(model_dir / "pose_landmarker_lite.task")
                ),
                running_mode=vision.RunningMode.IMAGE,
                num_poses=1,
                min_pose_detection_confidence=0.45,
                min_pose_presence_confidence=0.45,
            )
        )
        self.face = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=base(
                    model_asset_path=str(model_dir / "face_landmarker.task")
                ),
                running_mode=vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.45,
                min_face_presence_confidence=0.45,
            )
        )

    def close(self):
        self.hand.close()
        self.pose.close()
        self.face.close()

    def frame(self, bgr, timestamp_ms: int):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        hands_result = self.hand.detect(image)
        pose_result = self.pose.detect(image)
        face_result = self.face.detect(image)
        hands = []
        for index, landmarks in enumerate(hands_result.hand_landmarks):
            category = (
                hands_result.handedness[index][0]
                if index < len(hands_result.handedness)
                and hands_result.handedness[index]
                else None
            )
            hands.append(
                {
                    "handedness": (
                        category.category_name
                        if category and category.category_name in {"Left", "Right"}
                        else "Unknown"
                    ),
                    "score": round(float(category.score), 6) if category else 0.0,
                    "landmarks": [point(item) for item in landmarks],
                }
            )
        pose_landmarks = (
            pose_result.pose_landmarks[0] if pose_result.pose_landmarks else []
        )
        pose = {
            "landmarks": [
                point(pose_landmarks[index])
                if len(pose_landmarks) > index
                else {"x": 0.0, "y": 0.0, "z": 0.0}
                for index in POSE_INDICES
            ]
        }
        face = face_result.face_landmarks[0] if face_result.face_landmarks else []
        return {
            "timestamp_ms": timestamp_ms,
            "hands": hands,
            "pose": pose,
            "expression": expression_features(face),
        }


def extract_segment(video_path, segment, extractor, target_fps):
    capture = cv2.VideoCapture(str(video_path))
    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    if source_fps <= 0:
        capture.release()
        return None, "fps_invalid"
    start = float(segment["start_seconds"])
    end = min(float(segment["end_seconds"]), start + 12.0)
    timestamps = []
    timestamp = start
    while timestamp <= end and len(timestamps) < 144:
        timestamps.append(timestamp)
        timestamp += 1.0 / target_fps
    frames = []
    hand_frames = 0
    pose_frames = 0
    for timestamp in timestamps:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        success, bgr = capture.read()
        if not success:
            continue
        frame = extractor.frame(bgr, round((timestamp - start) * 1000))
        if frame["hands"]:
            hand_frames += 1
        if any(item["x"] or item["y"] for item in frame["pose"]["landmarks"]):
            pose_frames += 1
        frames.append(frame)
    capture.release()
    if len(frames) < 12:
        return None, "too_few_frames"
    hand_ratio = hand_frames / len(frames)
    pose_ratio = pose_frames / len(frames)
    if hand_ratio < 0.55:
        return None, f"hands_low:{hand_ratio:.2f}"
    if pose_ratio < 0.75:
        return None, f"pose_low:{pose_ratio:.2f}"
    return {
        "format_version": 3,
        "frames": frames,
        "quality": {
            "hand_frame_ratio": round(hand_ratio, 4),
            "pose_frame_ratio": round(pose_ratio, 4),
        },
    }, None


def build(
    segments_path, video_dir, model_dir, output_path, rejected_path, limit=None
):
    source = json.loads(segments_path.read_text(encoding="utf-8"))
    candidates = [
        item for item in source["segments"] if item["mode"] == "temporal"
    ]
    if limit is not None:
        candidates = candidates[:limit]
    videos = {path.name: path for path in video_dir.iterdir() if path.is_file()}
    extractor = HolisticExtractor(model_dir)
    samples = []
    rejected = []
    try:
        for index, segment in enumerate(candidates, start=1):
            print(f"[{index}/{len(candidates)}] {segment['id']}", flush=True)
            payload, reason = extract_segment(
                videos[segment["video"]], segment, extractor, target_fps=6
            )
            if payload is None:
                rejected.append({**segment, "rejection_reason": reason})
                continue
            samples.append(
                {
                    "id": str(uuid.uuid4()),
                    "sign_name": clean_label(segment["label"]),
                    "trainer_name": creator_for(segment["video"]),
                    "source_segment_id": segment["id"],
                    "source_video": segment["video"],
                    "frame_count": len(payload["frames"]),
                    "landmarks": payload,
                }
            )
    finally:
        extractor.close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
    print(
        f"Extraídos={len(samples)} rejeitados={len(rejected)} arquivo={output_path}",
        flush=True,
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("segments", type=Path)
    parser.add_argument("video_dir", type=Path)
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("rejected", type=Path)
    parser.add_argument("--limit", type=int)
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
    )
