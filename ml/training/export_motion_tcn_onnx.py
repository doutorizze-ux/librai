"""Exporta o checkpoint MotionTCN validado para inferência ONNX em CPU."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from evaluate_eqt_motion_tcn import MotionTCN


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checkpoint = torch.load(
        args.checkpoint,
        map_location="cpu",
        weights_only=False,
    )
    frames = int(checkpoint["frames"])
    feature_count = int(checkpoint["motion_feature_count"])
    labels = list(checkpoint["labels"])
    model = MotionTCN(feature_count, len(labels))
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    example = torch.zeros((1, frames, feature_count), dtype=torch.float32)
    torch.onnx.export(
        model,
        example,
        args.output,
        input_names=["features"],
        output_names=["logits"],
        dynamic_axes={
            "features": {0: "batch"},
            "logits": {0: "batch"},
        },
        opset_version=17,
        do_constant_folding=True,
    )
    print(
        f"exported={args.output} frames={frames} "
        f"features={feature_count} classes={len(labels)}"
    )


if __name__ == "__main__":
    main()
