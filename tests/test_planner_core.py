from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core import (
    PlanConfig,
    generate_multi_week_plan_v1_2,
    generate_week_plan,
    generate_week_plan_v1_2,
)


BASE_START = date(2025, 1, 6)


def build_config(**overrides) -> PlanConfig:
    config = PlanConfig(
        race_date=BASE_START + timedelta(weeks=12),
        recent_weekly_km=60.0,
        recent_long_km=24.0,
        goal_marathon_time="03:30:00",
        current_mp="05:10",
    )
    return replace(config, **overrides)


def test_generate_week_plan_returns_full_week() -> None:
    config = build_config()
    plan = generate_week_plan(config, start_date=BASE_START)

    assert len(plan["days"]) == 7
    assert plan["summary"]["long_run_distance"] >= 20.0
    assert plan["summary"]["quality_sessions"] >= 1


def test_goal_mode_g1_limits_quality_sessions() -> None:
    config = build_config(goal_marathon_time="03:50:00")
    plan = generate_week_plan(config, start_date=BASE_START)

    assert plan["summary"]["quality_sessions"] == 0


def test_build_phase_g3_adds_two_quality_sessions() -> None:
    config = build_config(
        race_date=BASE_START + timedelta(weeks=8),
        goal_marathon_time="03:20:00",
        current_mp="05:40",
    )
    plan = generate_week_plan(config, start_date=BASE_START)

    assert plan["summary"]["quality_sessions"] >= 2


def test_taper_week_focuses_on_recovery() -> None:
    config = build_config(race_date=BASE_START + timedelta(days=2))
    plan = generate_week_plan(config, start_date=BASE_START)

    assert plan["summary"]["quality_sessions"] == 0
    assert plan["summary"]["long_run_distance"] <= 4.1


def test_recent_volume_above_min_keeps_current_level() -> None:
    config = build_config(recent_weekly_km=60.0)
    plan = generate_week_plan(config, start_date=BASE_START)

    assert pytest.approx(plan["summary"]["target_weekly_km"], rel=1e-2) == 60.0


def test_cutback_week_recovers_to_minimum() -> None:
    config = build_config(recent_weekly_km=40.0, injury_flag=False)
    plan = generate_week_plan(config, start_date=BASE_START)

    min_volume = 0.9 * round(75 * 0.70)
    assert pytest.approx(plan["summary"]["target_weekly_km"], rel=1e-2) == min_volume


def test_injury_week_rises_cautiously() -> None:
    config = build_config(recent_weekly_km=40.0, injury_flag=True)
    plan = generate_week_plan(config, start_date=BASE_START)

    min_volume = 0.9 * round(75 * 0.70)
    expected = max(40.0 * 1.1, 0.8 * min_volume)
    assert pytest.approx(plan["summary"]["target_weekly_km"], rel=1e-2) == expected


def test_low_injury_week_increases_from_low_base() -> None:
    config = build_config(recent_weekly_km=20.0, injury_flag=True)
    plan = generate_week_plan(config, start_date=BASE_START)

    min_volume = 0.9 * round(75 * 0.70)
    expected = max(20.0 * 1.2, 0.5 * min_volume)
    assert pytest.approx(plan["summary"]["target_weekly_km"], rel=1e-2) == expected


def test_weekly_volume_jump_adds_warning_note() -> None:
    config = build_config(recent_weekly_km=20.0, injury_flag=False)
    plan = generate_week_plan(config, start_date=BASE_START)

    assert any("25% 이상 증가" in note for note in plan["notes"])


def test_phase_focus_note_added_for_base_week() -> None:
    config = build_config()
    plan = generate_week_plan(config, start_date=BASE_START)

    assert any(note.startswith("BASE Phase") for note in plan["notes"])


def test_quality_zero_note_present_when_no_sessions() -> None:
    config = build_config(goal_marathon_time="03:50:00")
    plan = generate_week_plan(config, start_date=BASE_START)

    assert any("품질 세션 없이 회복 중심" in note for note in plan["notes"])


def test_quality_two_sessions_note_present() -> None:
    config = build_config(
        race_date=BASE_START + timedelta(weeks=8),
        goal_marathon_time="03:20:00",
        current_mp="05:40",
    )
    plan = generate_week_plan(config, start_date=BASE_START)

    assert any("품질 세션이 2회 이상" in note for note in plan["notes"])


def test_long_run_stage_three_note_present() -> None:
    config = build_config(
        race_date=BASE_START + timedelta(weeks=8),
        goal_marathon_time="03:20:00",
        current_mp="05:40",
        recent_long_km=24.0,
    )
    plan = generate_week_plan(config, start_date=BASE_START)

    assert any("Stage3 단계" in note for note in plan["notes"])


def test_v1_2_override_recent_weekly_km_matches_explicit_config() -> None:
    config = build_config(recent_weekly_km=60.0)
    override_value = 30.0
    plan_override = generate_week_plan_v1_2(
        config,
        start_date=BASE_START,
        override_recent_weekly_km=override_value,
    )
    plan_expected = generate_week_plan_v1_2(
        replace(config, recent_weekly_km=override_value),
        start_date=BASE_START,
    )
    assert pytest.approx(plan_override["summary"]["target_weekly_km"], rel=1e-2) == plan_expected["summary"]["target_weekly_km"]


def test_multi_week_without_actuals_chains_planned_values() -> None:
    config = build_config(recent_weekly_km=50.0)
    race_date = BASE_START + timedelta(weeks=3)
    plan = generate_multi_week_plan_v1_2(
        config,
        start_date=BASE_START,
        race_date=race_date,
        actual_weekly_km=None,
    )
    weeks = plan["weeks"]
    assert len(weeks) == 4
    assert weeks[0]["recent_weekly_km_used"] == pytest.approx(50.0)
    assert weeks[1]["recent_weekly_km_used"] == pytest.approx(weeks[0]["summary"]["planned_weekly_km"])
    assert weeks[2]["recent_weekly_km_used"] == pytest.approx(weeks[1]["summary"]["planned_weekly_km"])


def test_multi_week_uses_actual_values_when_provided() -> None:
    config = build_config(recent_weekly_km=45.0)
    race_date = BASE_START + timedelta(weeks=4)
    actuals = [42.0, 48.0]
    plan = generate_multi_week_plan_v1_2(
        config,
        start_date=BASE_START,
        race_date=race_date,
        actual_weekly_km=actuals,
    )
    weeks = plan["weeks"]
    assert weeks[1]["recent_weekly_km_used"] == pytest.approx(actuals[0])
    assert weeks[2]["recent_weekly_km_used"] == pytest.approx(actuals[1])
    assert weeks[3]["recent_weekly_km_used"] == pytest.approx(weeks[2]["summary"]["planned_weekly_km"])
    assert weeks[0]["actual_weekly_km"] == pytest.approx(actuals[0])
    assert weeks[1]["actual_weekly_km"] == pytest.approx(actuals[1])


def test_single_week_plan_returned_when_race_within_same_week() -> None:
    config = build_config()
    race_date = BASE_START + timedelta(days=3)
    plan = generate_multi_week_plan_v1_2(
        config,
        start_date=BASE_START,
        race_date=race_date,
        actual_weekly_km=[],
    )
    weeks = plan["weeks"]
    assert len(weeks) == 1
    week = weeks[0]
    assert week["start_date"] == BASE_START
    assert week["end_date"] == race_date
    assert "recent_weekly_km_used" in week
    assert "actual_weekly_km" in week


def test_weekly_training_days_three_limits_quality_sessions() -> None:
    config = build_config(weekly_training_days=3)
    plan = generate_week_plan(config, start_date=BASE_START)

    run_days = sum(1 for day in plan["days"] if day["session_type"] != "Rest / Mobility")
    assert run_days <= 4
    assert plan["summary"]["quality_sessions"] <= 1


def test_weekly_training_days_six_increases_run_days() -> None:
    config = build_config(weekly_training_days=6)
    plan = generate_week_plan(config, start_date=BASE_START)

    run_days = sum(1 for day in plan["days"] if day["session_type"] != "Rest / Mobility")
    assert run_days >= 6
