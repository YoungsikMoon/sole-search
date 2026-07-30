#!/usr/bin/env python3
"""Resolve an explicit, auditable sole-search source scope.

This standard-library-only planner performs no network or LLM calls.  It keeps
credential gaps, regional applicability, manual checks, and candidate sources
visible so a narrow search is never misreported as a whole-market survey.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
PRESETS = (
    "quick",
    "focused",
    "recommended",
    "all_registered",
    "all_known",
    "custom",
)

SOURCE_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "id": "sbiz24",
        "label": "소상공인24(소진공+통합조회)",
        "availability": "registered",
        "execution_mode": "automated",
        "triggers": (),
        "requests": (15, 50),
        "seconds": (30, 150),
    },
    {
        "id": "bizinfo",
        "label": "기업마당",
        "availability": "registered",
        "execution_mode": "automated",
        "triggers": (),
        "requests": (20, 120),
        "seconds": (60, 240),
    },
    {
        "id": "fanfandaero",
        "label": "판판대로",
        "availability": "registered",
        "execution_mode": "automated",
        "triggers": ("online_sales", "marketing"),
        "requests": (5, 60),
        "seconds": (20, 180),
    },
    {
        "id": "seoulshinbo",
        "label": "서울신용보증재단",
        "availability": "registered",
        "execution_mode": "automated",
        "triggers": (),
        "province": "서울",
        "requests": (5, 80),
        "seconds": (20, 240),
    },
    {
        "id": "gov24",
        "label": "보조금24 오픈 API",
        "availability": "registered",
        "execution_mode": "credentialed",
        "credential": "gov24",
        "triggers": ("grant", "facility", "recovery"),
        "requests": (22, 40),
        "seconds": (20, 90),
    },
    {
        "id": "semas_loan_status",
        "label": "소진공 정책자금 회차·소진 상태",
        "availability": "manual",
        "execution_mode": "manual",
        "triggers": ("loan",),
        "requests": (0, 0),
        "seconds": (60, 300),
    },
    {
        "id": "koreg",
        "label": "신용보증재단중앙회·지역신보",
        "availability": "manual",
        "execution_mode": "manual",
        "triggers": ("loan",),
        "requests": (0, 0),
        "seconds": (120, 480),
    },
    {
        "id": "regional_portal",
        "label": "프로필 지역 지자체·경제진흥원 포털",
        "availability": "manual",
        "execution_mode": "manual",
        "triggers": ("grant", "loan", "facility", "marketing", "recovery"),
        "requires_province": True,
        "requests": (0, 0),
        "seconds": (180, 900),
    },
    {
        "id": "work24",
        "label": "고용24",
        "availability": "candidate",
        "execution_mode": "manual",
        "triggers": ("education", "employment"),
        "requests": (0, 0),
        "seconds": (120, 480),
    },
    {
        "id": "wbiz",
        "label": "여성기업종합정보포털(WBiz)",
        "availability": "candidate",
        "execution_mode": "manual",
        "triggers": ("female_owner",),
        "requests": (0, 0),
        "seconds": (120, 480),
    },
    {
        "id": "debc",
        "label": "장애인기업종합지원센터",
        "availability": "candidate",
        "execution_mode": "manual",
        "triggers": ("disabled_owner",),
        "requests": (0, 0),
        "seconds": (120, 480),
    },
    {
        "id": "seis",
        "label": "사회적기업 통합사업관리시스템",
        "availability": "candidate",
        "execution_mode": "manual",
        "triggers": ("social_enterprise",),
        "requests": (0, 0),
        "seconds": (120, 480),
    },
    {
        "id": "exportvoucher",
        "label": "수출바우처",
        "availability": "candidate",
        "execution_mode": "manual",
        "triggers": ("export", "online_sales"),
        "requests": (0, 0),
        "seconds": (120, 480),
    },
    {
        "id": "astartup",
        "label": "농식품창업정보망(A-Startup)",
        "availability": "candidate",
        "execution_mode": "manual",
        "triggers": ("agriculture", "food"),
        "requests": (0, 0),
        "seconds": (120, 480),
    },
    {
        "id": "touraz",
        "label": "관광기업지원센터·Touraz",
        "availability": "candidate",
        "execution_mode": "manual",
        "triggers": ("tourism",),
        "requests": (0, 0),
        "seconds": (120, 480),
    },
    {
        "id": "kosme",
        "label": "중소벤처기업진흥공단",
        "availability": "candidate",
        "execution_mode": "manual",
        "triggers": ("loan", "export"),
        "requests": (0, 0),
        "seconds": (120, 480),
    },
    {
        "id": "kibo",
        "label": "기술보증기금",
        "availability": "candidate",
        "execution_mode": "manual",
        "triggers": ("loan", "technology"),
        "requests": (0, 0),
        "seconds": (120, 480),
    },
)

REGISTRY_BY_ID = {source["id"]: source for source in SOURCE_REGISTRY}
REGISTERED_IDS = tuple(
    source["id"]
    for source in SOURCE_REGISTRY
    if source["availability"] in {"registered", "manual"}
)


class ScopePlanError(ValueError):
    """Raised when a requested source scope is ambiguous or invalid."""


def _split_values(values: Iterable[str] | None) -> tuple[str, ...]:
    result: list[str] = []
    for raw in values or ():
        for value in raw.split(","):
            normalized = value.strip().lower()
            if normalized and normalized not in result:
                result.append(normalized)
    return tuple(result)


def _is_seoul(province: str | None) -> bool:
    return bool(province and ("서울" in province or province.lower() == "seoul"))


def _profile_applies(
    source: dict[str, Any], tags: set[str], province: str | None
) -> bool:
    if source.get("requires_province") and not province:
        return False
    if source.get("province") == "서울" and not _is_seoul(province):
        return False
    triggers = set(source.get("triggers", ()))
    return not triggers or bool(triggers & tags)


def _geography_applies(source: dict[str, Any], province: str | None) -> bool:
    if source.get("requires_province") and not province:
        return False
    if source.get("province") == "서울" and not _is_seoul(province):
        return False
    return True


def _selected_ids(
    preset: str,
    requested_ids: tuple[str, ...],
    tags: set[str],
    province: str | None,
    credentials: set[str],
) -> set[str]:
    if preset == "quick":
        return {"sbiz24"}
    if preset in {"focused", "custom"}:
        return set(requested_ids)
    if preset == "all_registered":
        return {
            source_id
            for source_id in REGISTERED_IDS
            if _geography_applies(REGISTRY_BY_ID[source_id], province)
            and (
                _profile_applies(REGISTRY_BY_ID[source_id], tags, province)
                or not tags
            )
        }
    if preset == "all_known":
        return {
            source["id"]
            for source in SOURCE_REGISTRY
            if _geography_applies(source, province)
        }

    selected = {"sbiz24", "bizinfo"}
    for source in SOURCE_REGISTRY:
        if source["availability"] not in {"registered", "manual"}:
            continue
        if not _profile_applies(source, tags, province):
            continue
        if source["execution_mode"] == "credentialed" and source["credential"] not in credentials:
            continue
        selected.add(source["id"])
    return selected


def resolve_scope(
    preset: str = "recommended",
    source_ids: Iterable[str] | None = None,
    *,
    needs: Iterable[str] | None = None,
    profile_tags: Iterable[str] | None = None,
    province: str | None = None,
    credentials: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return the canonical source-scope plan used by CLI and tests."""

    if preset not in PRESETS:
        raise ScopePlanError(f"unknown preset: {preset}")

    requested_ids = _split_values(source_ids)
    unknown = sorted(set(requested_ids) - set(REGISTRY_BY_ID))
    if unknown:
        raise ScopePlanError("unknown source id(s): " + ", ".join(unknown))
    if preset == "focused" and len(requested_ids) != 1:
        raise ScopePlanError("focused requires exactly one --source")
    if preset == "custom" and not requested_ids:
        raise ScopePlanError("custom requires at least one --source")
    if preset not in {"focused", "custom"} and requested_ids:
        raise ScopePlanError(f"{preset} does not accept --source; use focused or custom")

    tags = set(_split_values(needs)) | set(_split_values(profile_tags))
    normalized_province = province.strip() if province and province.strip() else None
    credential_set = set(_split_values(credentials))
    selected = _selected_ids(
        preset, requested_ids, tags, normalized_province, credential_set
    )

    source_states: list[dict[str, Any]] = []
    for source in SOURCE_REGISTRY:
        source_id = source["id"]
        applicable = _profile_applies(source, tags, normalized_province)
        credential_missing = (
            source["execution_mode"] == "credentialed"
            and source["credential"] not in credential_set
        )

        if source_id in selected:
            selection_status = "selected"
            if source["availability"] == "candidate":
                execution_status = "manual_only"
                reason = "명시 선택됨; 검증된 자동 어댑터가 없어 수동 확인"
            elif credential_missing:
                execution_status = "unavailable_credential"
                reason = f"{source['credential']} credential 미등록"
            elif source["execution_mode"] == "manual":
                execution_status = "manual_only"
                reason = "선택됨; 로그인·실시간 상태는 수동 확인"
            else:
                execution_status = "ready"
                reason = "선택 범위에 포함"
        elif not applicable:
            selection_status = "not_applicable"
            execution_status = "not_selected"
            reason = "현재 프로필·지역 트리거와 일치하지 않음"
        else:
            selection_status = "omitted_by_user"
            execution_status = (
                "unavailable_credential" if credential_missing else "not_selected"
            )
            reason = (
                f"{source['credential']} credential 미등록"
                if credential_missing
                else "현재 선택 범위에서 제외"
            )

        estimated = selection_status == "selected" and execution_status in {
            "ready",
            "manual_only",
        }
        source_states.append(
            {
                "source_id": source_id,
                "label": source["label"],
                "selection_status": selection_status,
                "execution_mode": source["execution_mode"],
                "execution_status": execution_status,
                "availability_status": source["availability"],
                "reason": reason,
                "estimated_requests": {
                    "min": source["requests"][0] if estimated else 0,
                    "max": source["requests"][1] if estimated else 0,
                },
                "estimated_duration_seconds": {
                    "min": source["seconds"][0] if estimated else 0,
                    "max": source["seconds"][1] if estimated else 0,
                },
            }
        )

    selected_states = [
        state for state in source_states if state["selection_status"] == "selected"
    ]
    manual_count = sum(
        state["execution_status"] == "manual_only" for state in selected_states
    )
    unavailable_count = sum(
        state["execution_status"] == "unavailable_credential"
        for state in selected_states
    )
    estimate = {
        "requests": {
            "min": sum(state["estimated_requests"]["min"] for state in selected_states),
            "max": sum(state["estimated_requests"]["max"] for state in selected_states),
        },
        "duration_seconds": {
            "min": sum(
                state["estimated_duration_seconds"]["min"] for state in selected_states
            ),
            "max": sum(
                state["estimated_duration_seconds"]["max"] for state in selected_states
            ),
        },
        "model_tokens": 0,
    }

    fingerprint_payload = {
        "schema_version": SCHEMA_VERSION,
        "domain": "sole-search",
        "preset": preset,
        "selected_source_ids": [
            state["source_id"] for state in selected_states
        ],
        "profile_tags": sorted(tags),
        "province": normalized_province,
        "available_credentials": sorted(credential_set),
        "execution_statuses": {
            state["source_id"]: state["execution_status"] for state in selected_states
        },
    }
    canonical = json.dumps(
        fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    if unavailable_count:
        coverage_claim = "selected_scope_partial"
    elif manual_count:
        coverage_claim = "manual_required"
    else:
        coverage_claim = "selected_scope_ready"

    return {
        "schema_version": SCHEMA_VERSION,
        "domain": "sole-search",
        "requested": {
            "preset": preset,
            "source_ids": list(requested_ids),
            "profile_tags": sorted(tags),
            "province": normalized_province,
            "available_credentials": sorted(credential_set),
        },
        "scope_fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "coverage_claim": coverage_claim,
        "counts": {
            "universe": len(source_states),
            "selected": len(selected_states),
            "automated_ready": sum(
                state["execution_status"] == "ready" for state in selected_states
            ),
            "manual": manual_count,
            "unavailable_credential": unavailable_count,
            "omitted": sum(
                state["selection_status"] == "omitted_by_user" for state in source_states
            ),
            "not_applicable": sum(
                state["selection_status"] == "not_applicable" for state in source_states
            ),
        },
        "estimate": estimate,
        "sources": source_states,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="sole-search 범위 계획만 생성합니다. 네트워크·LLM 호출은 하지 않습니다."
    )
    parser.add_argument("--preset", choices=PRESETS, default="recommended")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="focused/custom에서 사용할 source id. 반복 또는 쉼표 구분 가능",
    )
    parser.add_argument("--need", action="append", default=[], help="grant, loan 등 필요 태그")
    parser.add_argument(
        "--profile-tag",
        action="append",
        default=[],
        help="female_owner, tourism 등 선택 소스 트리거",
    )
    parser.add_argument("--province", help="지역 소스 적용 판단용 시/도")
    parser.add_argument(
        "--credential",
        action="append",
        default=[],
        help="현재 사용 가능한 credential id (예: gov24)",
    )
    parser.add_argument("--list-sources", action="store_true")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--compact", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.list_sources:
        payload: Any = {
            "schema_version": SCHEMA_VERSION,
            "domain": "sole-search",
            "sources": SOURCE_REGISTRY,
        }
    else:
        try:
            payload = resolve_scope(
                args.preset,
                args.source,
                needs=args.need,
                profile_tags=args.profile_tag,
                province=args.province,
                credentials=args.credential,
            )
        except ScopePlanError as exc:
            _parser().error(str(exc))

    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=None if args.compact else 2,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
