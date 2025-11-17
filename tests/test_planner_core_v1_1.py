from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core_v1_1 import PlanConfigV11, generate_week_plan_v1_1


BASE_START = date(2025, 1, 6)


def build_config(**overrides) -> PlanConfigV11:
    config = PlanConfigV11(
        race_date=BASE_START + timedelta(weeks=12),
        recent_weekly_km=60.0,
        recent_long_km=24.0,
        goal_marathon_time="03:30:00",
        current_mp="05:10",
        injury_flag=False,
    )
    return replace(config, **overrides)


def test_recent_volume_above_min_keeps_current_level() -> None:
    config = build_config(recent_weekly_km=60.0)
    result = generate_week_plan_v1_1(config, start_date=BASE_START)

    assert pytest.approx(result["summary"]["target_weekly_km"], rel=1e-2) == 60.0


def test_cutback_week_recovers_to_minimum() -> None:
    config = build_config(recent_weekly_km=40.0, injury_flag=False)
    result = generate_week_plan_v1_1(config, start_date=BASE_START)

    min_volume = 0.9 * round(75 * 0.70)  # Build_config uses BASE (12w out) so cap=75
    assert pytest.approx(result["summary"]["target_weekly_km"], rel=1e-2) == min_volume


def test_injury_week_rises_cautiously() -> None:
    config = build_config(recent_weekly_km=40.0, injury_flag=True)
    result = generate_week_plan_v1_1(config, start_date=BASE_START)

    min_volume = 0.9 * round(75 * 0.70)
    expected = max(40.0 * 1.1, 0.8 * min_volume)
    assert pytest.approx(result["summary"]["target_weekly_km"], rel=1e-2) == expected


def test_low_injury_week_increases_from_low_base() -> None:
    config = build_config(recent_weekly_km=20.0, injury_flag=True)
    result = generate_week_plan_v1_1(config, start_date=BASE_START)

    min_volume = 0.9 * round(75 * 0.70)
    expected = max(20.0 * 1.2, 0.5 * min_volume)
    assert pytest.approx(result["summary"]["target_weekly_km"], rel=1e-2) == expected
