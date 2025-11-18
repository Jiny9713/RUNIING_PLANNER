"""
planner_core_v1_2
-----------------
Based on planner_core.py (injury-aware default). Adds actual-mileage chaining
and multi-week planning utilities without modifying the default engine.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from planner_core import PlanConfig, Planner, WEEKDAY_LABELS


def _build_week_payload(config: PlanConfig, *, start_date: Optional[date]) -> Dict[str, Any]:
    planner = Planner(config, start_date=start_date)
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
    notes = list(result.notes)
    recent_km = config.recent_weekly_km
    planned_km = result.total_planned_km
    if recent_km > 0:
        ratio = planned_km / recent_km
        if ratio >= 1.25:
            notes.append("지난 주 대비 주간 거리가 25% 이상 증가했습니다. 피로도·통증을 점검하고 필요 시 거리를 줄여 주세요.")
    phase_focus = {
        "BASE": "BASE Phase: 에어로빅 베이스와 Easy 러닝 비율을 충분히 확보하는 주입니다. 페이스보다는 거리와 주간 리듬에 집중해 주세요.",
        "BUILD": "BUILD Phase: 품질 세션 후 회복일을 충분히 확보하면서, 롱런 후반 집중도를 점차 올리는 주입니다.",
        "PEAK": "PEAK Phase: 레이스 페이스 감각을 키우는 것이 핵심입니다. 롱런과 포인트 훈련에서 식이·보급·페이스 전략을 리허설해 보세요.",
        "TAPER": "TAPER Phase: 볼륨을 줄이고 회복을 극대화하는 구간입니다. 수면·영양·스트레스 관리를 우선시해 주세요.",
    }
    phase_note = phase_focus.get(result.phase)
    if phase_note:
        notes.append(phase_note)
    if quality_sessions == 0:
        notes.append("이번 주는 품질 세션 없이 회복 중심 주간입니다. Easy 페이스에서 부상 신호를 체크해 주세요.")
    elif quality_sessions >= 2:
        notes.append("품질 세션이 2회 이상인 주간입니다. 세션 사이 회복일의 수면·영양 관리에 특히 신경 써 주세요.")
    if long_stage in {"3", "4"} and long_distance >= 28.0:
        notes.append("이번 롱런은 Stage{0} 단계로, 레이스 시뮬레이션에 가까운 강도입니다. 보급 계획과 페이스 전략을 미리 연습해 보세요.".format(long_stage))
    days = []
    for plan in result.plans:
        weekday_label = WEEKDAY_LABELS[plan.date.weekday()]
        days.append(
            {
                "date": plan.date.isoformat(),
                "weekday": weekday_label,
                "session_type": plan.session_type,
                "distance_km": plan.distance_km,
                "pace_range": plan.pace_range,
                "structure": plan.structure,
                "notes": plan.notes,
            }
        )
    return {"summary": summary, "days": days, "notes": notes}


def generate_week_plan_v1_2(
    config: PlanConfig,
    *,
    start_date: Optional[date] = None,
    override_recent_weekly_km: Optional[float] = None,
) -> Dict[str, Any]:
    """주간 플랜을 생성하되 override_recent_weekly_km가 있으면 해당 값을 지난 주 실제 거리로 사용한다."""
    recent = config.recent_weekly_km
    if override_recent_weekly_km is not None and override_recent_weekly_km > 0:
        recent = override_recent_weekly_km
    config_override = replace(config, recent_weekly_km=recent)
    return _build_week_payload(config_override, start_date=start_date)


def generate_multi_week_plan_v1_2(
    base_config: PlanConfig,
    *,
    start_date: date,
    race_date: date,
    actual_weekly_km: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    실제 주간 거리 정보를 활용해 레이스 주간까지 이어지는 멀티 주간 플랜을 생성한다.
    actual_weekly_km 리스트는 이미 완료한 주의 실제 거리(week index 기준)를 전달한다.
    """
    if start_date > race_date:
        raise ValueError("start_date must be on or before race_date")
    actual_weekly_km = actual_weekly_km or []
    weeks: List[Dict[str, Any]] = []
    idx = 0
    current_start = start_date
    while current_start <= race_date:
        current_end = min(current_start + timedelta(days=6), race_date)
        if idx == 0:
            recent = base_config.recent_weekly_km
        else:
            actual_prev = actual_weekly_km[idx - 1] if idx - 1 < len(actual_weekly_km) else None
            if actual_prev is not None and actual_prev > 0:
                recent = actual_prev
            else:
                recent = weeks[-1]["summary"]["planned_weekly_km"]
        week_config = replace(base_config, recent_weekly_km=recent)
        week_plan = generate_week_plan_v1_2(week_config, start_date=current_start)
        actual_this_week = actual_weekly_km[idx] if idx < len(actual_weekly_km) else None
        weeks.append(
            {
                "index": idx,
                "start_date": current_start,
                "end_date": current_end,
                "summary": week_plan["summary"],
                "days": week_plan["days"],
                "notes": week_plan["notes"],
                "recent_weekly_km_used": recent,
                "actual_weekly_km": actual_this_week,
            }
        )
        current_start += timedelta(days=7)
        idx += 1
    return {"weeks": weeks}


__all__ = [
    "PlanConfig",
    "generate_week_plan_v1_2",
    "generate_multi_week_plan_v1_2",
]
