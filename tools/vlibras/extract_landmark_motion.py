"""Convert a VLibras clip into lightweight body/hand landmark frames."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import UnityPy


Vector = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]

FINGER_CHAINS = {
    "thumb": ("004", "014", "013"),
    "index": ("003", "012", "011"),
    "middle": ("002", "010", "009"),
    "ring": ("001", "008", "007"),
    "pinky": ("", "006", "005"),
}


def vector(value: dict[str, float]) -> Vector:
    return (float(value["x"]), float(value["y"]), float(value["z"]))


def quaternion(value: dict[str, float]) -> Quaternion:
    return (
        float(value["x"]),
        float(value["y"]),
        float(value["z"]),
        float(value["w"]),
    )


def add(left: Vector, right: Vector) -> Vector:
    return tuple(left[index] + right[index] for index in range(3))  # type: ignore[return-value]


def subtract(left: Vector, right: Vector) -> Vector:
    return tuple(left[index] - right[index] for index in range(3))  # type: ignore[return-value]


def multiply_quaternion(left: Quaternion, right: Quaternion) -> Quaternion:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


def normalize_quaternion(value: Quaternion) -> Quaternion:
    magnitude = math.sqrt(sum(component * component for component in value))
    if magnitude == 0:
        return (0.0, 0.0, 0.0, 1.0)
    return tuple(component / magnitude for component in value)  # type: ignore[return-value]


def rotate(value: Vector, rotation: Quaternion) -> Vector:
    qx, qy, qz, qw = normalize_quaternion(rotation)
    point = (value[0], value[1], value[2], 0.0)
    inverse = (-qx, -qy, -qz, qw)
    rotated = multiply_quaternion(
        multiply_quaternion((qx, qy, qz, qw), point),
        inverse,
    )
    return rotated[:3]


def interpolate(keys: list[dict], time: float, fallback: tuple) -> tuple:
    if not keys:
        return fallback
    if time <= keys[0]["time"]:
        return tuple(keys[0]["value"].values())
    if time >= keys[-1]["time"]:
        return tuple(keys[-1]["value"].values())
    for left, right in zip(keys, keys[1:]):
        if left["time"] <= time <= right["time"]:
            span = right["time"] - left["time"]
            ratio = 0.0 if span == 0 else (time - left["time"]) / span
            left_value = tuple(left["value"].values())
            right_value = tuple(right["value"].values())
            mixed = tuple(
                left_value[index]
                + (right_value[index] - left_value[index]) * ratio
                for index in range(len(left_value))
            )
            return (
                normalize_quaternion(mixed) if len(mixed) == 4 else mixed
            )
    return fallback


def load_skeleton(scene_path: Path) -> dict[str, dict[str, Any]]:
    environment = UnityPy.load(str(scene_path))
    objects = {obj.path_id: obj for obj in environment.objects}
    skeleton: dict[str, dict[str, Any]] = {}
    transform_names: dict[int, str] = {}

    for obj in environment.objects:
        if obj.type.name != "Transform":
            continue
        data = obj.read_typetree()
        game_object_id = data["m_GameObject"]["m_PathID"]
        transform_names[obj.path_id] = objects[game_object_id].read().m_Name

    for obj in environment.objects:
        if obj.type.name != "Transform":
            continue
        data = obj.read_typetree()
        name = transform_names[obj.path_id]
        parent_id = data["m_Father"]["m_PathID"]
        skeleton[name] = {
            "parent": transform_names.get(parent_id),
            "position": vector(data["m_LocalPosition"]),
            "rotation": quaternion(data["m_LocalRotation"]),
        }
    return skeleton


def load_clip(bundle_path: Path) -> tuple[dict, dict[str, list], dict[str, list]]:
    environment = UnityPy.load(str(bundle_path))
    clips = [
        obj.read_typetree()
        for obj in environment.objects
        if obj.type.name == "AnimationClip"
    ]
    if len(clips) != 1:
        raise ValueError(f"Expected one AnimationClip, found {len(clips)}")
    clip = clips[0]

    def curves(group: str) -> dict[str, list]:
        return {
            item["path"].split("/")[-1]: item["curve"]["m_Curve"]
            for item in clip.get(group, [])
        }

    return clip, curves("m_PositionCurves"), curves("m_RotationCurves")


def evaluate_frame(
    skeleton: dict[str, dict[str, Any]],
    position_curves: dict[str, list],
    rotation_curves: dict[str, list],
    time: float,
) -> dict[str, tuple[Vector, Quaternion]]:
    world: dict[str, tuple[Vector, Quaternion]] = {}

    def evaluate(name: str) -> tuple[Vector, Quaternion]:
        if name in world:
            return world[name]
        bone = skeleton[name]
        local_position = interpolate(
            position_curves.get(name, []), time, bone["position"]
        )
        local_rotation = interpolate(
            rotation_curves.get(name, []), time, bone["rotation"]
        )
        parent_name = bone["parent"]
        if parent_name is None or parent_name not in skeleton:
            result = (local_position, local_rotation)
        else:
            parent_position, parent_rotation = evaluate(parent_name)
            result = (
                add(parent_position, rotate(local_position, parent_rotation)),
                normalize_quaternion(
                    multiply_quaternion(parent_rotation, local_rotation)
                ),
            )
        world[name] = result
        return result

    for bone_name in skeleton:
        evaluate(bone_name)
    return world


def rounded(point: Vector) -> list[float]:
    return [round(component, 5) for component in point]


def hand_landmarks(world: dict, side: str) -> list[list[float]]:
    hand_name = f"BnMao_{side}"
    points = [world[hand_name][0]]
    for suffixes in FINGER_CHAINS.values():
        names = [
            f"BnDedo_1_{side}{'_' + suffix if suffix else ''}"
            for suffix in suffixes
        ]
        joints = [world[name][0] for name in names]
        tip = add(joints[-1], subtract(joints[-1], joints[-2]))
        points.extend((*joints, tip))
    return [rounded(point) for point in points]


def extract_motion(scene_path: Path, bundle_path: Path, fps: int = 15) -> dict:
    skeleton = load_skeleton(scene_path)
    clip, positions, rotations = load_clip(bundle_path)
    key_times = [
        key["time"]
        for curve_group in (positions, rotations)
        for keys in curve_group.values()
        for key in keys
    ]
    duration = max(key_times, default=0.0)
    frame_count = max(1, math.ceil(duration * fps) + 1)
    frames = []
    for frame_index in range(frame_count):
        time = min(duration, frame_index / fps)
        world = evaluate_frame(skeleton, positions, rotations, time)
        frames.append(
            {
                "time": round(time, 4),
                "body": {
                    name: rounded(world[name][0])
                    for name in (
                        "BnCabeca",
                        "BnOmbro_L",
                        "BnAntBraco_L",
                        "BnMao_L",
                        "BnOmbro_R",
                        "BnAntBraco_R",
                        "BnMao_R",
                    )
                },
                "left_hand": hand_landmarks(world, "L"),
                "right_hand": hand_landmarks(world, "R"),
            }
        )
    return {
        "schema_version": "1.0",
        "source": "VLibras",
        "license": "GPL-3.0; distribution approval pending",
        "label": clip.get("m_Name") or bundle_path.name,
        "fps": fps,
        "duration_seconds": round(duration, 4),
        "frames": frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=15)
    args = parser.parse_args()
    payload = extract_motion(args.scene, args.bundle, args.fps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(payload['frames'])} frames for {payload['label']} "
        f"to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
