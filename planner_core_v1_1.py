"""
planner_core_v1_1
-----------------
Based on planner_core.py v1.0, but uses an injury-aware weekly volume heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

from planner_core_v1_0 import PlanConfig as PlanConfigV10, Planner as PlannerV10


@dataclass
class PlanConfigV11(PlanConfigV10):
    injury_flag: bool = False


class PlannerV11(PlannerV10):
    def __init__(self, config: PlanConfigV11, *, start_date: Optional[date] = None):
        super().__init__(config, start_date=start_date)

    def adjusted_target_volume(self) -> float:
        caps = {"G1": 60.0, "G2": 75.0, "G3": 82.0}
        phase_factor = {
            "BASE": 0.70,
            "BUILD": 0.85,
            "PEAK": 0.95,
            "TAPER": 0.60,
        }

        cap = caps[self.goal_mode]
        theoretical = round(cap * phase_factor[self.phase])
        min_volume = 0.9 * theoretical
        max_volume = cap
        recent = self.config.recent_weekly_km
        injury = getattr(self.config, "injury_flag", False)

        if recent >= min_volume:
            target = min(max(recent, min_volume), max_volume)
        elif recent >= 0.6 * min_volume:
            if injury:
                candidate = max(recent * 1.1, 0.8 * min_volume)
                target = min(candidate, max_volume)
            else:
                target = min(min_volume, max_volume)
        else:
            if injury:
                candidate = max(recent * 1.2, 0.5 * min_volume)
            else:
                candidate = max(recent * 1.3, 0.6 * min_volume)
            target = min(candidate, max_volume)

        return max(target, 0.0)


def generate_week_plan_v1_1(
    config: PlanConfigV11,
    *,
    start_date: Optional[date] = None,
) -> Dict[str, Any]:
    planner = PlannerV11(config, start_date=start_date)
    result = planner.build_week()
    quality_sessions = sum(1 for plan in result.plans if plan.session_type.startswith("Quality"))
    long_run = next((plan for plan in result.plans if plan.session_type.startswith("Long")), None)
    long_distance = long_run.distance_km if long_run else 0.0
    long_stage = ""
    if long_run and "Stage" in long_run.session_type:
        long_stage = long_run.session_type.split("Stage")[-1].strip(" )")

    summary = {
        "phase": result.phase,
        "goal_mode": result.goal_mode,
        "target_weekly_km": result.target_weekly_km,
        "planned_weekly_km": result.total_planned_km,
        "quality_sessions": quality_sessions,
        "long_run_distance": long_distance,
        "long_run_stage": long_stage,
    }
    days = [
        {
            "date": plan.date.isoformat(),
            "weekday": plan.weekday,
            "session_type": plan.session_type,
            "distance_km": plan.distance_km,
            "pace_range": plan.pace_range,
            "structure": plan.structure,
            "notes": plan.notes,
        }
        for plan in result.plans
    ]
    return {"summary": summary, "days": days, "notes": result.notes}


__all__ = ["PlanConfigV11", "PlannerV11", "generate_week_plan_v1_1"]
