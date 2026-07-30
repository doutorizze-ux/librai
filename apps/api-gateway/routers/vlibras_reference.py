import gzip
import json
import os
import unicodedata
import re
from functools import lru_cache
from pathlib import Path
from typing import List

import httpx
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
    motion_ready: bool


class ReferenceCatalog(BaseModel):
    schema_version: str
    source: str
    license: str
    generated_at: str
    total: int
    signs: List[ReferenceSign]


class ComposeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class OfficialTranslation(BaseModel):
    schema_version: str
    source: str
    source_text: str
    gloss: str


VLIBRAS_TRANSLATOR_URL = os.getenv(
    "VLIBRAS_TRANSLATOR_URL",
    "https://traducao2.vlibras.gov.br/translate",
)


def _request_official_translation(text: str) -> str:
    headers = {
        "Accept": "text/plain",
        "Content-Type": "application/json",
        "Origin": "https://doutorizze-ux.github.io",
        "Referer": "https://doutorizze-ux.github.io/librai/",
        "User-Agent": "Librai/1.0",
    }
    with httpx.Client(timeout=12.0, follow_redirects=True) as client:
        response = client.post(
            VLIBRAS_TRANSLATOR_URL,
            headers=headers,
            json={"text": text},
        )
        response.raise_for_status()
        return response.text


def _normalize_official_gloss(value: str) -> str:
    return " ".join(value.strip().split())


def _default_catalog_path() -> Path:
    production_path = Path("/data/vlibras/catalog-v1.json")
    if production_path.is_file():
        return production_path
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data" / "vlibras" / "catalog-v1.json"
        if candidate.is_file():
            return candidate
    return production_path


def _default_motion_path() -> Path:
    production_path = Path("/data/vlibras/reference-motions")
    if production_path.is_dir():
        return production_path
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data" / "vlibras" / "reference-motions"
        if candidate.is_dir():
            return candidate
    return production_path


def _configured_path(variable: str, fallback: Path) -> Path:
    configured = os.getenv(variable)
    return Path(configured) if configured else fallback


@lru_cache(maxsize=1)
def _motion_index() -> dict[str, Path]:
    directory = _configured_path("VLIBRAS_MOTION_PATH", _default_motion_path())
    motions: dict[str, Path] = {}
    if not directory.is_dir():
        return motions
    for path in directory.iterdir():
        if path.name.endswith(".json.gz"):
            label = path.name[: -len(".json.gz")]
        elif path.suffix == ".json":
            label = path.stem
        else:
            continue
        motions.setdefault(_normalize_query(label), path)
    return motions


def _normalize_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip())
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    ).upper().replace(" ", "_")


@lru_cache(maxsize=1)
def _load_catalog() -> dict:
    path = _configured_path("VLIBRAS_CATALOG_PATH", _default_catalog_path())
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
    motions = _motion_index()
    signs = catalog["signs"]
    if normalized_query:
        signs = [
            sign for sign in signs if normalized_query in sign["search_key"]
        ]

    paginated_signs = [
        {
            **sign,
            "motion_ready": _normalize_query(sign["label"]) in motions,
        }
        for sign in signs[offset : offset + limit]
    ]
    return {
        **{key: value for key, value in catalog.items() if key != "signs"},
        "total": len(signs),
        "signs": paginated_signs,
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
    return {
        **sign,
        "motion_ready": _normalize_query(sign["label"]) in _motion_index(),
    }


@router.get("/motions/{label}")
def get_reference_motion(label: str):
    normalized_label = _normalize_query(label)
    if not normalized_label or any(
        character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-%"
        for character in normalized_label
    ):
        raise HTTPException(status_code=400, detail="Nome de sinal inválido")

    motion_path = _motion_index().get(normalized_label)
    if motion_path is None:
        raise HTTPException(
            status_code=404,
            detail="Animação de referência ainda não preparada",
        )
    try:
        opener = gzip.open if motion_path.name.endswith(".gz") else open
        with opener(motion_path, "rt", encoding="utf-8") as motion_file:
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
    motions = _motion_index()

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
                "motion_ready": _normalize_query(match) in motions,
            }
        )
        index += consumed

    return {
        "schema_version": "1.0",
        "source_text": payload.text,
        "signs": signs,
        "unresolved": unresolved,
    }


@router.post("/translate", response_model=OfficialTranslation)
def translate_portuguese_to_libras(payload: ComposeRequest):
    try:
        gloss = _normalize_official_gloss(
            _request_official_translation(payload.text)
        )
    except (httpx.HTTPError, OSError) as error:
        raise HTTPException(
            status_code=503,
            detail="Serviço oficial de tradução para Libras indisponível",
        ) from error

    if not gloss or len(gloss) > 5000:
        raise HTTPException(
            status_code=502,
            detail="O serviço oficial retornou uma tradução inválida",
        )

    return {
        "schema_version": "1.0",
        "source": "VLibras Translator",
        "source_text": payload.text,
        "gloss": gloss,
    }
