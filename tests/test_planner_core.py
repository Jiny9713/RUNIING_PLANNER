from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core import PlanConfig, generate_week_plan


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
