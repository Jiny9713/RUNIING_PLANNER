from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core_v1_2 import (
    PlanConfig,
    generate_multi_week_plan_v1_2,
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
        injury_flag=False,
    )
    return replace(config, **overrides)


def test_override_recent_weekly_km_takes_precedence() -> None:
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


def test_multi_week_chains_planned_km_without_actuals() -> None:
    config = build_config(recent_weekly_km=50.0)
    race_date = BASE_START + timedelta(weeks=3)
    plan = generate_multi_week_plan_v1_2(
        config,
        start_date=BASE_START,
        race_date=race_date,
        actual_weekly_km=None,
    )
    weeks = plan["weeks"]
    assert len(weeks) == 4  # weeks 0..3 포함
    assert weeks[0]["recent_weekly_km_used"] == pytest.approx(50.0)
    assert weeks[1]["recent_weekly_km_used"] == pytest.approx(weeks[0]["summary"]["planned_weekly_km"])
    assert weeks[2]["recent_weekly_km_used"] == pytest.approx(weeks[1]["summary"]["planned_weekly_km"])


def test_multi_week_uses_actuals_when_available() -> None:
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


def test_single_week_output_when_dates_within_same_week() -> None:
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
    assert set(week.keys()) == {
        "index",
        "start_date",
        "end_date",
        "summary",
        "days",
        "notes",
        "recent_weekly_km_used",
        "actual_weekly_km",
    }
