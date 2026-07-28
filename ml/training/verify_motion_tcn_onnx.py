"""Confere paridade do ONNX e repete a avaliação signer-independent.

Os modos são separados porque torch-directml e onnxruntime carregam DLLs
incompatíveis no mesmo processo Windows.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["prepare", "verify"], required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--normalization", type=Path)
    parser.add_argument("--onnx", type=Path)
    return parser.parse_args()


def metrics(logits: np.ndarray, targets: np.ndarray) -> tuple[float, float]:
    ranked = np.argsort(logits, axis=1)[:, -3:][:, ::-1]
    top1 = float(np.mean(ranked[:, 0] == targets))
    top3 = float(np.mean(np.any(ranked == targets[:, None], axis=1)))
    return top1, top3


def prepare(args: argparse.Namespace) -> None:
    if args.zip is None or args.checkpoint is None or args.normalization is None:
        raise SystemExit("prepare exige --zip, --checkpoint e --normalization.")
    import torch

    from evaluate_eqt_dataset import load_dataset
    from evaluate_eqt_motion_tcn import MotionTCN, motion_features

    checkpoint = torch.load(
        args.checkpoint,
        map_location="cpu",
        weights_only=False,
    )
    frames = int(checkpoint["frames"])
    _, _, test_x, test_y, labels = load_dataset(
        args.zip,
        len(checkpoint["labels"]),
        frames,
        "INFORMANTE 5",
        "hands",
        "global",
        True,
    )
    normalization = np.load(args.normalization)
    normalized = (
        test_x - normalization["mean"]
    ) / normalization["std"]
    features = motion_features(normalized).astype(np.float32)

    model = MotionTCN(features.shape[2], len(labels))
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    with torch.no_grad():
        torch_logits = model(torch.from_numpy(features)).numpy()
    np.savez_compressed(
        args.data,
        features=features,
        targets=test_y,
        torch_logits=torch_logits,
    )
    top1, top3 = metrics(torch_logits, test_y)
    print(
        f"prepared={args.data} samples={len(test_y)} "
        f"torch_top1={top1:.6%} torch_top3={top3:.6%}"
    )


def verify(args: argparse.Namespace) -> None:
    if args.onnx is None:
        raise SystemExit("verify exige --onnx.")
    import onnxruntime as ort

    data = np.load(args.data)
    features = data["features"]
    targets = data["targets"]
    torch_logits = data["torch_logits"]
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(
        str(args.onnx),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    onnx_logits = np.concatenate(
        [
            session.run(
                ["logits"],
                {"features": features[start : start + 128]},
            )[0]
            for start in range(0, len(features), 128)
        ]
    )
    maximum_difference = float(np.max(np.abs(torch_logits - onnx_logits)))
    torch_metrics = metrics(torch_logits, targets)
    onnx_metrics = metrics(onnx_logits, targets)
    print(
        f"max_abs_difference={maximum_difference:.8f} "
        f"torch_top1={torch_metrics[0]:.6%} "
        f"torch_top3={torch_metrics[1]:.6%} "
        f"onnx_top1={onnx_metrics[0]:.6%} "
        f"onnx_top3={onnx_metrics[1]:.6%}"
    )
    if maximum_difference > 1e-4:
        raise SystemExit("ONNX divergiu do checkpoint PyTorch.")
    if torch_metrics != onnx_metrics:
        raise SystemExit("ONNX alterou o ranking das previsões.")


def main() -> None:
    args = parse_args()
    if args.mode == "prepare":
        prepare(args)
    else:
        verify(args)


if __name__ == "__main__":
    main()
