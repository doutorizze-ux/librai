import json
import os
import unicodedata
import re
from functools import lru_cache
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


router = APIRouter(prefix="/v1/vlibras-reference", tags=["vlibras-reference"])


class ReferenceSign(BaseModel):
    id: str
    label: str
    search_key: str
    size_bytes: int
    platforms: List[str]
    is_compound: bool


class ReferenceCatalog(BaseModel):
    schema_version: str
    source: str
    license: str
    generated_at: str
    total: int
    signs: List[ReferenceSign]


class ComposeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


def _default_catalog_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "vlibras" / "catalog-v1.json"


def _default_motion_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "vlibras" / "reference-motions"


def _normalize_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip())
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    ).upper().replace(" ", "_")


@lru_cache(maxsize=1)
def _load_catalog() -> dict:
    path = Path(os.getenv("VLIBRAS_CATALOG_PATH", str(_default_catalog_path())))
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as catalog_file:
        return json.load(catalog_file)


@router.get("/catalog", response_model=ReferenceCatalog)
def get_reference_catalog(
    query: str = Query(default="", max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    try:
        catalog = _load_catalog()
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Catálogo de referência VLibras indisponível",
        ) from error

    normalized_query = _normalize_query(query)
    signs = catalog["signs"]
    if normalized_query:
        signs = [
            sign for sign in signs if normalized_query in sign["search_key"]
        ]

    return {
        **{key: value for key, value in catalog.items() if key != "signs"},
        "total": len(signs),
        "signs": signs[offset : offset + limit],
    }


@router.get("/catalog/{sign_id}", response_model=ReferenceSign)
def get_reference_sign(sign_id: str):
    try:
        catalog = _load_catalog()
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Catálogo de referência VLibras indisponível",
        ) from error

    sign = next((item for item in catalog["signs"] if item["id"] == sign_id), None)
    if sign is None:
        raise HTTPException(status_code=404, detail="Sinal de referência não encontrado")
    return sign


@router.get("/motions/{label}")
def get_reference_motion(label: str):
    normalized_label = _normalize_query(label)
    if not normalized_label or any(
        character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-%"
        for character in normalized_label
    ):
        raise HTTPException(status_code=400, detail="Nome de sinal inválido")

    motion_directory = Path(
        os.getenv("VLIBRAS_MOTION_PATH", str(_default_motion_path()))
    )
    motion_path = motion_directory / f"{normalized_label}.json"
    if not motion_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Animação de referência ainda não preparada",
        )
    try:
        with motion_path.open("r", encoding="utf-8") as motion_file:
            return json.load(motion_file)
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Animação de referência indisponível",
        ) from error


@router.post("/compose")
def compose_reference_sequence(payload: ComposeRequest):
    try:
        catalog = _load_catalog()
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Catálogo de referência VLibras indisponível",
        ) from error

    normalized_text = _normalize_query(
        re.sub(r"[^0-9A-Za-zÀ-ÿ% -]+", " ", payload.text)
    )
    tokens = [token for token in normalized_text.split("_") if token]
    aliases = {"BOA": "BOM", "BONS": "BOM", "BOAS": "BOM"}
    tokens = [aliases.get(token, token) for token in tokens]
    available = {sign["label"] for sign in catalog["signs"]}
    motion_directory = Path(
        os.getenv("VLIBRAS_MOTION_PATH", str(_default_motion_path()))
    )

    signs = []
    unresolved = []
    index = 0
    while index < len(tokens):
        match = None
        consumed = 0
        for width in range(min(5, len(tokens) - index), 0, -1):
            candidate = "_".join(tokens[index : index + width])
            if candidate in available:
                match = candidate
                consumed = width
                break
        if match is None:
            unresolved.append(tokens[index])
            index += 1
            continue
        signs.append(
            {
                "label": match,
                "motion_ready": (motion_directory / f"{match}.json").is_file(),
            }
        )
        index += consumed

    return {
        "schema_version": "1.0",
        "source_text": payload.text,
        "signs": signs,
        "unresolved": unresolved,
    }
