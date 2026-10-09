"""Справочники: специализации, грейды, навыки, отрасли и т. п. Публичные, без авторизации."""
import json
from functools import lru_cache

from fastapi import APIRouter, Response

from app.services.reference.skills import SKILLS
from app.services.reference.taxonomy import (
    DECLINE_REASONS,
    DOMAINS,
    FSP_DISCIPLINES,
    FSP_LEVELS,
    GRADES,
    INDUSTRIES,
    LANGUAGES,
    SOFT_SKILLS,
    SPECIALIZATIONS,
    TEAM_ROLES,
    THETA_CUTS,
    WORK_FORMATS,
    resolve_blueprint,
)

router = APIRouter(prefix="/reference", tags=["Справочники"])


@router.get("", summary="Все справочники одним запросом")
def all_reference():
    """Справочники не меняются во время работы — сериализуются один раз (их запрашивает каждая страница)."""
    return Response(_reference_json(), media_type="application/json", headers={"Cache-Control": "public, max-age=300"})


@lru_cache(maxsize=1)
def _reference_json() -> bytes:
    return json.dumps(_reference(), ensure_ascii=False).encode("utf-8")


def _reference() -> dict:
    return {
        "specializations": [
            {**{k: v for k, v in s.items() if k != "blueprint"},
             "blueprints": {lang: resolve_blueprint(s["code"], lang) for lang in s["languages"]}}
            for s in SPECIALIZATIONS
        ],
        "grades": GRADES,
        "theta_cuts": THETA_CUTS,
        "domains": DOMAINS,
        "languages": LANGUAGES,
        "industries": INDUSTRIES,
        "work_formats": WORK_FORMATS,
        "team_roles": TEAM_ROLES,
        "soft_skills": {k: v[0] for k, v in SOFT_SKILLS.items()},
        "decline_reasons": DECLINE_REASONS,
        "fsp_disciplines": FSP_DISCIPLINES,
        "fsp_levels": FSP_LEVELS,
        "skills": [{"id": s.id, "name": s.name, "group": s.group, "domains": list(s.domains), "specs": list(s.specs)}
                   for s in SKILLS],
    }


@router.get("/skills", summary="Онтология навыков")
def skills():
    return [{"id": s.id, "name": s.name, "group": s.group, "synonyms": list(s.synonyms), "domains": list(s.domains),
             "specs": list(s.specs)} for s in SKILLS]
