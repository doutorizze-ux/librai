"""Promove um ONNX revisado sem permitir atalhos nos gates de produção."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


class PromotionError(ValueError):
    pass


def promote(
    review_manifest_path: Path,
    output_dir: Path,
    approved_by: str,
) -> dict:
    manifest = json.loads(review_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "validated_ready_for_review":
        raise PromotionError("O artefato ainda não está pronto para revisão.")
    if manifest.get("feature_schema") != "librai_holistic_v4":
        raise PromotionError("Somente o esquema holístico v4 pode ser promovido.")
    if manifest.get("validation_mode") != "global-trainer":
        raise PromotionError("A validação deve separar professores inteiros.")
    minimum = float(
        (manifest.get("quality_policy") or {}).get(
            "minimum_validation_accuracy", 0.70
        )
    )
    if float(manifest.get("validation_accuracy", 0)) < max(0.70, minimum):
        raise PromotionError("A acurácia está abaixo do gate registrado.")
    rejection = manifest.get("rejection") or {}
    if rejection.get("method") != "softmax_confidence_and_margin":
        raise PromotionError("A rejeição de sinais desconhecidos não foi calibrada.")
    if float(rejection.get("known_acceptance_rate", 0)) < 0.70:
        raise PromotionError("A aceitação de sinais conhecidos está abaixo do gate.")
    if float(rejection.get("ood_recall", 0)) < 0.90:
        raise PromotionError("A rejeição de sinais desconhecidos está abaixo do gate.")
    if int(rejection.get("ood_validation_samples", 0)) < 30:
        raise PromotionError("São necessários ao menos 30 exemplos OOD.")
    trainers_by_class = (
        (manifest.get("dataset_quality") or {}).get("trainers_by_class") or {}
    )
    if not trainers_by_class or any(
        len(set(trainers)) < 3 for trainers in trainers_by_class.values()
    ):
        raise PromotionError("Cada classe precisa de ao menos três professores.")
    approver = approved_by.strip()
    if len(approver) < 3:
        raise PromotionError("Informe o responsável pela aprovação.")

    source_model = review_manifest_path.parent / str(manifest.get("onnx_file", ""))
    if not source_model.is_file():
        raise PromotionError("O arquivo ONNX revisado não foi encontrado.")
    digest = hashlib.sha256(source_model.read_bytes()).hexdigest()
    if digest != manifest.get("onnx_sha256"):
        raise PromotionError("O hash do ONNX não corresponde ao manifesto.")

    output_dir.mkdir(parents=True, exist_ok=True)
    destination_model = output_dir / "librai_stgcn.onnx"
    shutil.copy2(source_model, destination_model)
    production_manifest = {
        **manifest,
        "onnx_file": destination_model.name,
        "status": "production",
        "approved_by": approver,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest_sha256": hashlib.sha256(
            review_manifest_path.read_bytes()
        ).hexdigest(),
    }
    (output_dir / "production.manifest.json").write_text(
        json.dumps(production_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return production_manifest


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("review_manifest", type=Path)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("ml/models/production")
    )
    parser.add_argument("--approved-by", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    promote(
        arguments.review_manifest,
        arguments.output_dir,
        arguments.approved_by,
    )
