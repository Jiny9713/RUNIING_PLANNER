#!/usr/bin/env python3
"""
러닝 플래너 v3 (분리된 버전)

- 기존 planner.py는 유지하고, 이 파일에서 개선된 로직/입력 방식을 제공
- 입력: 대회 날짜, 최근 주간/롱런 거리, 주간 빈도, 피로도, Stage3/피크 런 여부(옵션)
- 출력: 주간 러닝 계획
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional


# -----------------------------
# 데이터 모델
# -----------------------------


@dataclass
class DayPlan:
    date: date
    label: str
    type: str
    description: str
    planned_km: float


@dataclass
class PlanConfig:
    today: date
    race_date: date
    recent_weekly_km: float
    recent_long_run: float
    weekly_frequency: int
    fatigue_level: int
    stage3_count: Optional[int] = None
    peak_long_done: Optional[bool] = None


# -----------------------------
# 유틸 함수
# -----------------------------


WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def start_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def round_km(x: float) -> float:
    return round(x, 1)


# -----------------------------
# Phase / 목표 계산
# -----------------------------


def determine_phase(today: date, race_date: date) -> str:
    days_left = (race_date - today).days
    weeks_left = days_left / 7.0
    if weeks_left >= 10:
        return "BASE"
    if 6 <= weeks_left < 10:
        return "BUILD"
    if 3 <= weeks_left < 6:
        return "PEAK"
    return "TAPER"


def compute_target_weekly_km(
    phase: str,
    recent_weekly_km: float,
    weeks_left: float,
) -> float:
    if phase == "BASE":
        target = max(45.0, min(55.0, recent_weekly_km))
    elif phase == "BUILD":
        target = min(recent_weekly_km * 1.2, recent_weekly_km + 10.0, 70.0)
        target = max(target, 50.0)
    elif phase == "PEAK":
        target = min(recent_weekly_km * 1.3, recent_weekly_km + 15.0, 82.0)
        target = max(target, 60.0)
    else:
        if weeks_left > 1.5:
            target = recent_weekly_km * 0.8
        elif weeks_left > 0.5:
            target = recent_weekly_km * 0.6
        else:
            target = recent_weekly_km * 0.4
        target = max(target, 25.0)
    return round_km(target)


# -----------------------------
# Stage/롱런 판단
# -----------------------------


def estimate_stage3_count(recent_long_run: float) -> int:
    """최근 롱런 거리로 Stage3 반복 횟수를 추정."""
    if recent_long_run < 22:
        return 0
    if recent_long_run < 24:
        return 1
    if recent_long_run < 26:
        return 2
    return 3


def infer_peak_long_done(recent_long_run: float, weeks_left: float) -> bool:
    """30km 이상 롱런 경험 여부를 추정."""
    if recent_long_run >= 30:
        return True
    if weeks_left <= 4 and recent_long_run >= 28:
        return True
    return False


def select_long_run_distance(
    phase: str,
    weeks_left: float,
    recent_long_run: float,
    peak_long_done: bool,
    stage3_count: int,
) -> float:
    if phase == "TAPER":
        if weeks_left > 1.5:
            return 21.0
        if weeks_left > 0.5:
            return 14.0
        return 10.0

    if phase == "BASE":
        if recent_long_run < 18:
            return 18.0
        if recent_long_run < 22:
            return 20.0
        if recent_long_run < 24:
            return 22.0
        return 24.0

    if phase == "BUILD":
        if recent_long_run < 20:
            return 20.0
        if recent_long_run < 22:
            return 22.0
        if recent_long_run < 24:
            return 24.0
        if recent_long_run < 26:
            return 24.0 if stage3_count >= 2 else 26.0
        return min(recent_long_run, 28.0)

    if phase == "PEAK":
        if not peak_long_done:
            return 32.0
        if recent_long_run >= 30:
            return 26.0
        if recent_long_run >= 26:
            return recent_long_run
        return 24.0

    return max(18.0, recent_long_run)


# -----------------------------
# 품질 세션 판단
# -----------------------------


def decide_quality_sessions(
    phase: str,
    fatigue_level: int,
    recent_long_run: float,
    target_weekly_km: float,
    weekly_frequency: int,
) -> int:
    if fatigue_level >= 7 or weekly_frequency <= 2:
        return 0

    if phase == "TAPER":
        return 1 if fatigue_level <= 5 else 0

    if phase == "BASE":
        if target_weekly_km >= 50 and fatigue_level <= 4 and weekly_frequency >= 4:
            return 2
        return 1

    if phase in {"BUILD", "PEAK"}:
        if (
            weekly_frequency >= 4
            and target_weekly_km >= 60
            and recent_long_run >= 24
            and fatigue_level <= 4
        ):
            return 2
        return 1

    return 1


def quality_type_for_phase(phase: str) -> str:
    if phase == "BASE":
        return "유산소 + 가벼운 템포"
    if phase == "BUILD":
        return "템포 또는 언덕 인터벌"
    if phase == "PEAK":
        return "레이스 페이스 인터벌"
    return "가벼운 인터벌(회복 위주)"


# -----------------------------
# 주간 계획 생성
# -----------------------------


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def generate_week_plan(config: PlanConfig) -> List[DayPlan]:
    start = start_of_week(config.today)
    phase = determine_phase(config.today, config.race_date)
    days_left = (config.race_date - config.today).days
    weeks_left = days_left / 7.0

    target_weekly_km = compute_target_weekly_km(
        phase, config.recent_weekly_km, weeks_left
    )

    stage3_count = (
        clamp(config.stage3_count, 0, 3)
        if config.stage3_count is not None
        else estimate_stage3_count(config.recent_long_run)
    )
    peak_long_done = (
        config.peak_long_done
        if config.peak_long_done is not None
        else infer_peak_long_done(config.recent_long_run, weeks_left)
    )

    long_run_km = select_long_run_distance(
        phase, weeks_left, config.recent_long_run, peak_long_done, stage3_count
    )

    run_days = max(config.weekly_frequency, 1)
    quality_count = decide_quality_sessions(
        phase,
        config.fatigue_level,
        config.recent_long_run,
        target_weekly_km,
        config.weekly_frequency,
    )
    max_quality_allowed = max(run_days - 1, 0)
    quality_count = min(quality_count, max_quality_allowed)

    quality_km_each = (
        min(max(target_weekly_km * 0.12, 8.0), 12.0) if quality_count > 0 else 0.0
    )
    total_quality_km = quality_km_each * quality_count

    remaining_km = target_weekly_km - long_run_km - total_quality_km
    if remaining_km < 0:
        deficit = -remaining_km
        reducible_long = max(long_run_km - 16.0, 0.0)
        reduce = min(deficit, reducible_long)
        long_run_km -= reduce
        deficit -= reduce
        if deficit > 0 and total_quality_km > 0:
            total_quality_km = max(total_quality_km - deficit, 0.0)
            quality_km_each = (
                total_quality_km / quality_count if quality_count > 0 else 0.0
            )
        remaining_km = 0.0

    easy_sessions = max(run_days - 1 - quality_count, 0)
    easy_km_each = remaining_km / easy_sessions if easy_sessions > 0 else 0.0

    preferred_quality_days = [1, 3, 4, 2, 5, 0]
    quality_day_indices = preferred_quality_days[:quality_count]
    long_run_day_index = 6  # Sunday

    plans: List[DayPlan] = []
    easy_used = 0

    for i in range(7):
        current_date = start + timedelta(days=i)
        label = WEEKDAY_LABELS[i]

        if i == long_run_day_index and run_days > 0:
            plan_type = "LONG"
            desc = f"롱런 {long_run_km:.1f}km (일요일)"
            km = long_run_km
        elif i in quality_day_indices:
            plan_type = "QUALITY"
            desc = f"{quality_type_for_phase(phase)} ~{quality_km_each:.1f}km"
            km = quality_km_each
        else:
            if easy_used < easy_sessions:
                plan_type = "EASY"
                desc = "Easy 러닝"
                km = easy_km_each
                easy_used += 1
            else:
                plan_type = "REST"
                desc = "휴식 또는 크로스 트레이닝"
                km = 0.0

        plans.append(
            DayPlan(
                date=current_date,
                label=label,
                type=plan_type,
                description=desc,
                planned_km=round_km(km),
            )
        )

    return plans


# -----------------------------
# CLI
# -----------------------------


def print_week_plan(plans: List[DayPlan], target_weekly_km: float) -> None:
    print("\n===== 이번 주 러닝 플랜 =====")
    total = 0.0
    for p in plans:
        date_str = p.date.strftime("%Y-%m-%d")
        print(
            f"{date_str} ({p.label}) | {p.type:7} | "
            f"{p.planned_km:4.1f} km | {p.description}"
        )
        total += p.planned_km
    print("----------------------------")
    print(f"합계: {total:.1f} km (목표 {target_weekly_km:.1f} km)")


def gather_config_from_cli() -> PlanConfig:
    print("=== 러닝 플래너 v3 (신규 버전) ===")
    today_str = input("오늘 날짜 (YYYY-MM-DD, Enter=오늘): ").strip()
    today = parse_date(today_str) if today_str else date.today()

    race_date = parse_date(input("레이스 날짜 (YYYY-MM-DD): ").strip())
    recent_weekly_km = float(input("최근 주간 총 거리 (km): ").strip())
    recent_long_run = float(input("최근 롱런 거리 (km): ").strip())
    weekly_freq = int(input("주간 러닝 빈도 (예: 4,5): ").strip())
    fatigue_level = int(input("현재 피로도(0~10): ").strip())

    stage3_input = input(
        "Stage3 플랜 진행 횟수 (0~3, Enter=자동 추정): "
    ).strip()
    stage3_count = None
    if stage3_input:
        try:
            stage3_count = clamp(int(stage3_input), 0, 3)
        except ValueError:
            stage3_count = None

    peak_input = input(
        "30km 이상 피크 롱런 완료 여부 (y/n, Enter=자동 추정): "
    ).strip().lower()
    peak_long_done: Optional[bool]
    if peak_input in {"y", "yes"}:
        peak_long_done = True
    elif peak_input in {"n", "no"}:
        peak_long_done = False
    else:
        peak_long_done = None

    return PlanConfig(
        today=today,
        race_date=race_date,
        recent_weekly_km=recent_weekly_km,
        recent_long_run=recent_long_run,
        weekly_frequency=weekly_freq,
        fatigue_level=fatigue_level,
        stage3_count=stage3_count,
        peak_long_done=peak_long_done,
    )


def main() -> None:
    config = gather_config_from_cli()

    phase = determine_phase(config.today, config.race_date)
    weeks_left = (config.race_date - config.today).days / 7.0
    target = compute_target_weekly_km(phase, config.recent_weekly_km, weeks_left)

    plans = generate_week_plan(config)
    print_week_plan(plans, target)


if __name__ == "__main__":
    main()
