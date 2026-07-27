"""Exporta somente um candidato já validado para ONNX."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch

from stgcn import LibrasSTGCN, TOTAL_NODES


def export(candidate_dir: Path, output: Path):
    manifest_path = candidate_dir / "model_manifest.json"
    weights_path = candidate_dir / "librai_stgcn.pt"
    if not manifest_path.exists() or not weights_path.exists():
        raise FileNotFoundError("Candidato validado incompleto.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "validated_not_deployed":
        raise ValueError("O manifesto não representa um candidato validado.")
    actual_hash = hashlib.sha256(weights_path.read_bytes()).hexdigest()
    if actual_hash != manifest.get("weights_sha256"):
        raise ValueError("Hash dos pesos não corresponde ao manifesto.")

    labels = manifest.get("labels")
    if not isinstance(labels, dict) or len(labels) < 2:
        raise ValueError("Mapa de classes inválido.")
    model = LibrasSTGCN(num_classes=len(labels))
    model.load_state_dict(torch.load(weights_path, map_location="cpu", weights_only=True))
    model.eval()
    dummy = torch.zeros(
        1, 4, int(manifest["sequence_length"]), TOTAL_NODES
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        dummy,
        output,
        input_names=["landmarks"],
        output_names=["logits"],
        dynamic_axes={"landmarks": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )
    model_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    deploy_manifest = {
        **manifest,
        "onnx_sha256": model_hash,
        "onnx_file": output.name,
        "status": "validated_ready_for_review",
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(deploy_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"ONNX gerado: {output} ({model_hash[:12]})")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "candidate_dir", type=Path, help="Diretório criado por train.py"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("ml/models/review/librai_stgcn.onnx")
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    export(arguments.candidate_dir, arguments.output)
