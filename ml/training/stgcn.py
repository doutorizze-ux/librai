"""ST-GCN compacto para sequências de mãos e parte superior do corpo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from torch import nn


HAND_NODES = 21
POSE_NODES = 13
EXPRESSION_FEATURES = ("mouth_open", "mouth_width", "left_brow", "right_brow")
EXPRESSION_NODES = len(EXPRESSION_FEATURES)
TOTAL_NODES = HAND_NODES * 2 + POSE_NODES + EXPRESSION_NODES


def _edges():
    hand_edges = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (0, 9), (9, 10), (10, 11), (11, 12),
        (0, 13), (13, 14), (14, 15), (15, 16),
        (0, 17), (17, 18), (18, 19), (19, 20),
    ]
    result = []
    for offset in (0, HAND_NODES):
        result.extend((a + offset, b + offset) for a, b in hand_edges)
    pose_offset = HAND_NODES * 2
    # nariz, ombros, cotovelos, pulsos, quadris e pontos auxiliares superiores
    result.extend(
        (pose_offset + a, pose_offset + b)
        for a, b in [
            (0, 1), (0, 2), (1, 3), (3, 5), (2, 4), (4, 6),
            (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
            (5, 11), (6, 12), (11, 12),
        ]
    )
    # Conecta pulsos das mãos aos pulsos corporais.
    result.extend([(0, pose_offset + 9), (HAND_NODES, pose_offset + 10)])
    expression_offset = pose_offset + POSE_NODES
    result.extend(
        (pose_offset, expression_offset + index)
        for index in range(EXPRESSION_NODES)
    )
    return result


def adjacency_matrix() -> torch.Tensor:
    adjacency = torch.eye(TOTAL_NODES, dtype=torch.float32)
    for source, target in _edges():
        adjacency[source, target] = 1
        adjacency[target, source] = 1
    degree = adjacency.sum(dim=1).clamp_min(1).pow(-0.5)
    return degree[:, None] * adjacency * degree[None, :]


class STGCNBlock(nn.Module):
    def __init__(self, input_channels: int, output_channels: int, adjacency):
        super().__init__()
        self.register_buffer("adjacency", adjacency)
        self.spatial = nn.Conv2d(input_channels, output_channels, kernel_size=1)
        self.temporal = nn.Sequential(
            nn.BatchNorm2d(output_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(
                output_channels,
                output_channels,
                kernel_size=(5, 1),
                padding=(2, 0),
            ),
            nn.BatchNorm2d(output_channels),
        )
        self.residual = (
            nn.Identity()
            if input_channels == output_channels
            else nn.Conv2d(input_channels, output_channels, kernel_size=1)
        )
        self.activation = nn.ReLU(inplace=True)

    def forward(self, features):
        residual = self.residual(features)
        features = torch.einsum("nctv,vw->nctw", features, self.adjacency)
        return self.activation(self.temporal(self.spatial(features)) + residual)


class LibrasSTGCN(nn.Module):
    """Entrada N,C,T,V; C=(x,y,z,presença), V=59 articulações."""

    def __init__(self, num_classes: int):
        super().__init__()
        adjacency = adjacency_matrix()
        self.blocks = nn.Sequential(
            STGCNBlock(4, 64, adjacency),
            STGCNBlock(64, 96, adjacency),
            STGCNBlock(96, 128, adjacency),
        )
        self.dropout = nn.Dropout(0.25)
        self.classifier = nn.Linear(128, num_classes)

    def forward(self, features):
        features = self.blocks(features)
        features = features.mean(dim=(2, 3))
        return self.classifier(self.dropout(features))


@dataclass
class SequencePreprocessor:
    sequence_length: int = 48

    def __call__(self, payload: Any):
        if not isinstance(payload, dict) or payload.get("format_version") not in {2, 3, 4}:
            return None
        frames = payload.get("frames")
        if not isinstance(frames, list) or len(frames) < 12:
            return None
        indices = torch.linspace(
            0, len(frames) - 1, steps=self.sequence_length
        ).round().to(torch.int64)
        output = torch.zeros(4, self.sequence_length, TOTAL_NODES)
        for target_index, source_index in enumerate(indices.tolist()):
            frame = frames[source_index]
            if not isinstance(frame, dict):
                return None
            self._write_hands(output, target_index, frame.get("hands"))
            self._write_pose(output, target_index, frame.get("pose"))
            self._write_expression(
                output, target_index, frame.get("expression")
            )
        self._normalize(output)
        return output

    @staticmethod
    def _write_points(output, time_index, offset, points):
        if not isinstance(points, list):
            return
        for point_index, point in enumerate(points):
            if offset + point_index >= TOTAL_NODES or not isinstance(point, dict):
                break
            output[0, time_index, offset + point_index] = float(point.get("x", 0))
            output[1, time_index, offset + point_index] = float(point.get("y", 0))
            output[2, time_index, offset + point_index] = float(point.get("z", 0))
            output[3, time_index, offset + point_index] = 1

    def _write_hands(self, output, time_index, hands):
        if not isinstance(hands, list):
            return
        slots = [None, None]
        unknown = []
        for hand in hands[:2]:
            if not isinstance(hand, dict):
                continue
            side = hand.get("handedness")
            slot = 0 if side == "Left" else 1 if side == "Right" else None
            if slot is None or slots[slot] is not None:
                unknown.append(hand)
            else:
                slots[slot] = hand
        for hand in unknown:
            available = [
                index for index, value in enumerate(slots) if value is None
            ]
            if not available:
                break
            points = hand.get("landmarks")
            wrist_x = (
                float(points[0].get("x", 0.5))
                if isinstance(points, list)
                and points
                and isinstance(points[0], dict)
                else 0.5
            )
            preferred = 0 if wrist_x <= 0.5 else 1
            slots[preferred if preferred in available else available[0]] = hand
        for slot, hand in enumerate(slots):
            if hand is not None:
                self._write_points(
                    output,
                    time_index,
                    slot * HAND_NODES,
                    hand.get("landmarks"),
                )

    def _write_pose(self, output, time_index, pose):
        points = pose.get("landmarks") if isinstance(pose, dict) else None
        self._write_points(output, time_index, HAND_NODES * 2, points)

    @staticmethod
    def _write_expression(output, time_index, expression):
        if not isinstance(expression, dict):
            return
        offset = HAND_NODES * 2 + POSE_NODES
        for index, name in enumerate(EXPRESSION_FEATURES):
            value = expression.get(name)
            if not isinstance(value, (int, float)):
                continue
            output[0, time_index, offset + index] = float(value)
            output[3, time_index, offset + index] = 1

    @staticmethod
    def _normalize(output):
        presence = output[3] > 0
        kinematic_nodes = HAND_NODES * 2 + POSE_NODES
        for time_index in range(output.shape[1]):
            present = presence[time_index, :kinematic_nodes]
            if not present.any():
                continue
            coordinates = output[:3, time_index, :kinematic_nodes][:, present]
            center = coordinates[:2].mean(dim=1, keepdim=True)
            coordinates[:2] -= center
            scale = coordinates[:2].abs().max().clamp_min(1e-4)
            coordinates[:3] /= scale
            kinematics = output[:3, time_index, :kinematic_nodes]
            kinematics[:, present] = coordinates
