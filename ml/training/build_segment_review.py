"""Consolida OCR temporal e cria relatório visual de segmentos candidatos."""

from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import cv2


def comparable(label: str) -> str:
    value = unicodedata.normalize("NFKD", label)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^A-Z ]", "", value.upper())
    value = re.sub(r"\s+[A-Z]$", "", value)
    return re.sub(r"\s+", " ", value).strip()


def similar(first: str, second: str) -> bool:
    first, second = comparable(first), comparable(second)
    if first in second or second in first:
        return True
    return SequenceMatcher(None, first, second).ratio() >= 0.68


@dataclass
class Run:
    observations: list[dict] = field(default_factory=list)

    @property
    def start(self):
        return min(item["timestamp_seconds"] for item in self.observations)

    @property
    def end(self):
        return max(item["timestamp_seconds"] for item in self.observations)

    @property
    def label(self):
        best = max(self.observations, key=lambda item: item["confidence"])
        return comparable(best["label"])

    @property
    def confidence(self):
        return max(item["confidence"] for item in self.observations)


def consolidate(video: dict) -> list[dict]:
    interval = float(video["sample_interval_seconds"])
    observations = sorted(
        video["observations"], key=lambda item: item["timestamp_seconds"]
    )
    by_timestamp = {}
    for item in observations:
        by_timestamp.setdefault(item["timestamp_seconds"], []).append(item)
    # Aulas sequenciais mostram um rótulo por vez. Nos mosaicos, conserva cada
    # rótulo espacial como candidato independente para recorte posterior.
    is_grid = any(len(items) >= 3 for items in by_timestamp.values())
    if is_grid:
        # O mesmo texto é lido em vários frames e às vezes com pequenas
        # variações ("INTELIGENTE"/"TELIGENTE"). Agrupar primeiro pela posição
        # impede duplicar a mesma célula como duas classes distintas.
        spatial_clusters: list[list[dict]] = []
        for item in observations:
            box = item["box"]
            center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            matching = None
            for cluster in spatial_clusters:
                other = cluster[0]["box"]
                other_center = (
                    (other[0] + other[2]) / 2,
                    (other[1] + other[3]) / 2,
                )
                if (
                    abs(center[0] - other_center[0]) <= 120
                    and abs(center[1] - other_center[1]) <= 120
                ):
                    matching = cluster
                    break
            if matching is None:
                spatial_clusters.append([item])
            else:
                matching.append(item)
        best_items = [
            max(cluster, key=lambda item: item["confidence"])
            for cluster in spatial_clusters
        ]
        x_centers = [
            (item["box"][0] + item["box"][2]) / 2 for item in best_items
        ]
        # Uma lista vertical ao lado de uma única pessoa não é mosaico: os
        # rótulos ficam todos na mesma coluna e não indicam qual gesto está
        # ativo em cada instante. Sem alinhamento temporal, esses itens devem
        # ser descartados, não tratados como células independentes.
        if len(x_centers) >= 3 and max(x_centers) - min(x_centers) < 140:
            return []
        return [
            {
                "label": comparable(item["label"]),
                "start_seconds": 0.0,
                "end_seconds": video["duration_seconds"],
                "confidence": item["confidence"],
                "mode": "spatial_grid",
                "box": item["box"],
            }
            for item in sorted(
                best_items,
                key=lambda candidate: (
                    candidate["box"][1],
                    candidate["box"][0],
                ),
            )
            if comparable(item["label"])
        ]

    runs: list[Run] = []
    for timestamp, items in sorted(by_timestamp.items()):
        item = max(items, key=lambda candidate: candidate["confidence"])
        if (
            runs
            and timestamp - runs[-1].end <= interval * 2.2
            and similar(item["label"], runs[-1].label)
        ):
            runs[-1].observations.append(item)
        else:
            runs.append(Run([item]))
    result = []
    for run in runs:
        start = max(0.0, run.start - interval * 0.65)
        end = min(video["duration_seconds"], run.end + interval * 0.65)
        if end - start < 1.0:
            continue
        result.append(
            {
                "label": run.label,
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "confidence": round(run.confidence, 4),
                "mode": "temporal",
            }
        )
    return result


def preview(video_path: Path, segment: dict, output: Path):
    capture = cv2.VideoCapture(str(video_path))
    timestamp = (segment["start_seconds"] + segment["end_seconds"]) / 2
    capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
    success, frame = capture.read()
    capture.release()
    if not success:
        return None
    height, width = frame.shape[:2]
    scale = min(640 / width, 420 / height, 1.0)
    if scale < 1:
        frame = cv2.resize(frame, None, fx=scale, fy=scale)
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 42), (0, 0, 0), -1)
    cv2.putText(
        frame,
        f"{segment['label']}  {timestamp:.1f}s",
        (10, 29),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.imwrite(str(output), frame)
    return output.name


def build(
    report_path: Path,
    video_dir: Path,
    output_dir: Path,
    id_prefix: str = "candidate",
):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    previews = output_dir / "segment_previews"
    previews.mkdir(exist_ok=True)
    videos = {path.name: path for path in video_dir.iterdir() if path.is_file()}
    records = []
    rows = []
    sequence = 0
    for video in report["videos"]:
        for segment in consolidate(video):
            sequence += 1
            segment_id = f"{id_prefix}-{sequence:04d}"
            record = {"id": segment_id, "video": video["file"], **segment}
            filename = f"{segment_id}.jpg"
            record["preview"] = preview(
                videos[video["file"]], record, previews / filename
            )
            record["review_status"] = "pending"
            records.append(record)
            rows.append(
                "<tr>"
                f"<td><img src='segment_previews/{html.escape(filename)}'></td>"
                f"<td>{html.escape(record['label'])}</td>"
                f"<td>{record['start_seconds']:.1f}–{record['end_seconds']:.1f}s</td>"
                f"<td>{html.escape(record['mode'])}</td>"
                f"<td>{html.escape(record['video'])}</td>"
                "</tr>"
            )
    (output_dir / "segment_candidates.json").write_text(
        json.dumps({"segments": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    document = """<!doctype html><meta charset="utf-8">
<title>Revisão de segmentos Librai</title>
<style>
body{font:14px system-ui;margin:24px;background:#f7f4fa;color:#211b27}
table{border-collapse:collapse;width:100%}td,th{padding:8px;border:1px solid #ccc}
img{width:240px;max-height:180px;object-fit:contain;background:#111}
th{position:sticky;top:0;background:#6d559a;color:white}
</style><h1>Segmentos candidatos — não treinados</h1>
<p>Todo item permanece pendente até revisão do rótulo e do recorte.</p>
<table><tr><th>Imagem</th><th>Rótulo OCR</th><th>Intervalo</th>
<th>Modo</th><th>Fonte</th></tr>""" + "".join(rows) + "</table>"
    review_path = output_dir / "segment_review.html"
    review_path.write_text(document, encoding="utf-8")
    print(f"{len(records)} segmentos candidatos; revisão: {review_path}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("video_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--id-prefix",
        default="candidate",
        help="Prefixo estável para evitar colisões entre lotes.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build(args.report, args.video_dir, args.output_dir, args.id_prefix)
