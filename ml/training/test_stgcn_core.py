import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent))

from stgcn import HAND_NODES, POSE_NODES, SequencePreprocessor, _edges


def _undirected_edges():
    return {tuple(sorted(edge)) for edge in _edges()}


def test_graph_connects_anatomical_arms_and_hand_wrists():
    pose = HAND_NODES * 2
    edges = _undirected_edges()

    assert tuple(sorted((pose + 5, pose + 7))) in edges
    assert tuple(sorted((pose + 7, pose + 9))) in edges
    assert tuple(sorted((pose + 6, pose + 8))) in edges
    assert tuple(sorted((pose + 8, pose + 10))) in edges
    assert tuple(sorted((0, pose + 9))) in edges
    assert tuple(sorted((HAND_NODES, pose + 10))) in edges

    assert tuple(sorted((pose + 1, pose + 7))) not in edges
    assert tuple(sorted((0, pose + 5))) not in edges


def test_unknown_hands_are_assigned_by_screen_position_like_runtime():
    def hand(wrist_x):
        return {
            "handedness": "Unknown",
            "landmarks": [
                {"x": wrist_x + index * 0.001, "y": 0.4, "z": 0.0}
                for index in range(HAND_NODES)
            ],
        }

    output = torch.zeros(4, 1, (HAND_NODES * 2) + POSE_NODES + 4)
    SequencePreprocessor._write_hands(
        SequencePreprocessor(), output, 0, [hand(0.8), hand(0.2)]
    )

    assert output[0, 0, 0].item() == torch.tensor(0.2).item()
    assert output[0, 0, HAND_NODES].item() == torch.tensor(0.8).item()
