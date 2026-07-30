"""Explicit source-scope contract tests (network-free)."""

import importlib
import json

import pytest


@pytest.fixture(scope="module")
def scope_plan():
    return importlib.import_module("scope_plan")


def _state(plan, source_id):
    return next(source for source in plan["sources"] if source["source_id"] == source_id)


def test_quick_selects_only_sbiz24_and_keeps_omissions_visible(scope_plan):
    plan = scope_plan.resolve_scope("quick")

    assert plan["counts"]["selected"] == 1
    assert _state(plan, "sbiz24")["selection_status"] == "selected"
    assert _state(plan, "bizinfo")["selection_status"] == "omitted_by_user"
    assert plan["estimate"]["model_tokens"] == 0


def test_focused_requires_exactly_one_explicit_source(scope_plan):
    with pytest.raises(scope_plan.ScopePlanError):
        scope_plan.resolve_scope("focused")
    with pytest.raises(scope_plan.ScopePlanError):
        scope_plan.resolve_scope("focused", ["sbiz24", "bizinfo"])

    plan = scope_plan.resolve_scope("focused", ["fanfandaero"])
    assert _state(plan, "fanfandaero")["selection_status"] == "selected"


def test_recommended_uses_profile_triggers_and_seoul_region(scope_plan):
    plan = scope_plan.resolve_scope(
        "recommended",
        needs=["online_sales", "loan"],
        province="서울특별시",
    )

    selected = {
        source["source_id"]
        for source in plan["sources"]
        if source["selection_status"] == "selected"
    }
    assert selected == {
        "sbiz24",
        "bizinfo",
        "fanfandaero",
        "seoulshinbo",
        "semas_loan_status",
        "koreg",
        "regional_portal",
    }
    assert plan["coverage_claim"] == "manual_required"


def test_seoul_source_is_not_applicable_for_other_regions(scope_plan):
    plan = scope_plan.resolve_scope("recommended", province="부산광역시")
    state = _state(plan, "seoulshinbo")

    assert state["selection_status"] == "not_applicable"
    assert state["estimated_requests"] == {"min": 0, "max": 0}


def test_all_registered_reports_missing_credential_honestly(scope_plan):
    plan = scope_plan.resolve_scope(
        "all_registered", needs=["grant", "loan"], province="서울"
    )
    gov24 = _state(plan, "gov24")

    assert gov24["selection_status"] == "selected"
    assert gov24["execution_status"] == "unavailable_credential"
    assert plan["coverage_claim"] == "selected_scope_partial"
    assert plan["counts"]["unavailable_credential"] == 1


def test_all_known_includes_candidates_without_automating_them(scope_plan):
    plan = scope_plan.resolve_scope("all_known", province="서울")
    selected = {
        source["source_id"]
        for source in plan["sources"]
        if source["selection_status"] == "selected"
    }

    assert selected == {source["id"] for source in scope_plan.SOURCE_REGISTRY}
    assert _state(plan, "work24")["execution_status"] == "manual_only"
    assert _state(plan, "work24")["availability_status"] == "candidate"
    assert plan["coverage_claim"] == "selected_scope_partial"
    assert plan["counts"]["manual"] > 0
    assert plan["estimate"]["model_tokens"] == 0


def test_registered_credential_becomes_ready(scope_plan):
    plan = scope_plan.resolve_scope(
        "custom", ["gov24"], credentials=["gov24"]
    )

    assert _state(plan, "gov24")["execution_status"] == "ready"
    assert plan["coverage_claim"] == "selected_scope_ready"
    assert plan["estimate"]["requests"]["min"] > 0


def test_custom_candidate_is_explicitly_manual(scope_plan):
    plan = scope_plan.resolve_scope("custom", ["sbiz24", "work24"])

    assert _state(plan, "work24")["availability_status"] == "candidate"
    assert _state(plan, "work24")["execution_status"] == "manual_only"
    assert plan["coverage_claim"] == "manual_required"


def test_fingerprint_is_stable_across_input_order(scope_plan):
    first = scope_plan.resolve_scope(
        "custom",
        ["work24", "sbiz24"],
        needs=["education", "grant"],
        credentials=["gov24"],
    )
    second = scope_plan.resolve_scope(
        "custom",
        ["sbiz24", "work24"],
        needs=["grant", "education"],
        credentials=["gov24"],
    )

    assert first["scope_fingerprint"] == second["scope_fingerprint"]


def test_cli_writes_credential_and_manual_states(scope_plan, tmp_path):
    output = tmp_path / "scope-plan.json"

    assert scope_plan.main(
        [
            "--preset",
            "custom",
            "--source",
            "gov24,work24",
            "--credential",
            "gov24",
            "--compact",
            "-o",
            str(output),
        ]
    ) == 0

    plan = json.loads(output.read_text(encoding="utf-8"))
    assert _state(plan, "gov24")["execution_status"] == "ready"
    assert _state(plan, "work24")["execution_status"] == "manual_only"
    assert plan["estimate"]["model_tokens"] == 0
