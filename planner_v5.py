#!/usr/bin/env python3
"""
러닝 플래너 v5 (추가 보완 버전)

- BASE 단계 품질훈련은 최대 1회로 제한하고 저강도 템포를 권장
- TAPER 단계는 주차별 품질 횟수를 명시: T-2주 1회, T-1/레이스 주 0회
- 레이스 주간 롱런을 4km 수준으로 완화
- 피로도에 따른 주간 목표 거리 재조정(10~20% 감축)
- Stage3 추정 시 최근 4~6주 롱런 히스토리를 활용
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional, Sequence


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
    long_run_history: Optional[List[float]] = None
    stage3_count: Optional[int] = None
    peak_long_done: Optional[bool] = None


@dataclass
class PlanDetails:
    plans: List[DayPlan]
    stage3_used: int
    stage3_inferred: bool
    peak_long_done: bool
    peak_long_inferred: bool


# -----------------------------
# 상수 / 유틸
# -----------------------------


WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
QUALITY_DAY_PRIORITY = [1, 3, 4, 2, 5, 0, 6]
EASY_DAY_PRIORITY = [0, 2, 4, 5, 3, 1, 6]


def parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def start_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def round_km(x: float) -> float:
    return round(x, 1)


# -----------------------------
# Phase / 목표 거리
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


def adjust_target_for_fatigue(target: float, fatigue_level: int) -> float:
    """Apply 10~20% reduction based on fatigue to keep workload manageable."""
    if fatigue_level >= 8:
        factor = 0.8
    elif fatigue_level >= 6:
        factor = 0.85
    elif fatigue_level >= 4:
        factor = 0.9
    else:
        factor = 1.0
    adjusted = round_km(target * factor)
    return max(20.0, adjusted)


# -----------------------------
# Stage/롱런 관련
# -----------------------------


def _normalize_history(history: Sequence[float], fallback: float) -> List[float]:
    values = [h for h in history if h > 0]
    if not values:
        values = [fallback]
    return values[-6:]


def estimate_stage3_count(history: Sequence[float], fallback: float) -> int:
    recent = _normalize_history(history, fallback)
    max_run = max(recent)
    heavy = sum(1 for d in recent if d >= 26)
    moderate = sum(1 for d in recent if 24 <= d < 26)

    if max_run < 22:
        return 0
    if heavy >= 2:
        return 3
    if heavy == 1 or moderate >= 2:
        return 2
    if max_run >= 24:
        return 1
    return 0


def infer_peak_long_done(recent_long_run: float, weeks_left: float) -> bool:
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
        return 4.0

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


def min_long_distance_for_phase(phase: str) -> float:
    return {
        "BASE": 18.0,
        "BUILD": 20.0,
        "PEAK": 24.0,
        "TAPER": 4.0,
    }.get(phase, 18.0)


# -----------------------------
# 품질 세션
# -----------------------------


def decide_quality_sessions(
    phase: str,
    fatigue_level: int,
    recent_long_run: float,
    target_weekly_km: float,
    weekly_frequency: int,
    weeks_left: float,
) -> int:
    if fatigue_level >= 7 or weekly_frequency <= 2:
        return 0

    if phase == "TAPER":
        if weeks_left > 1.5:
            return 1 if fatigue_level <= 5 else 0
        # T-1주 및 레이스 주: 품질 없음
        return 0

    if phase == "BASE":
        if (
            target_weekly_km >= 48
            and fatigue_level <= 4
            and weekly_frequency >= 4
        ):
            return 1
        return 0

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
        return "저강도 템포 (6~8km)"
    if phase == "BUILD":
        return "템포/언덕 인터벌"
    if phase == "PEAK":
        return "레이스 페이스 인터벌"
    return "회복용 인터벌"


def quality_distance_for_phase(phase: str, target_weekly_km: float) -> float:
    if phase == "BASE":
        return min(max(target_weekly_km * 0.08, 6.0), 8.0)
    if phase == "TAPER":
        return min(max(target_weekly_km * 0.09, 6.0), 9.0)
    return min(max(target_weekly_km * 0.12, 8.0), 12.0)


# -----------------------------
# 거리 정규화
# -----------------------------


def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def normalize_distances(
    phase: str,
    target_weekly_km: float,
    long_run_km: float,
    quality_km_each: float,
    quality_count: int,
    easy_sessions: int,
) -> tuple[float, float, float]:
    total_quality_km = quality_km_each * quality_count
    scheduled = long_run_km + total_quality_km
    long_min = min_long_distance_for_phase(phase)

    if scheduled > target_weekly_km:
        deficit = scheduled - target_weekly_km
        reducible_long = max(long_run_km - long_min, 0.0)
        reduce = min(deficit, reducible_long)
        long_run_km -= reduce
        deficit -= reduce

        if deficit > 0 and total_quality_km > 0:
            total_quality_km = max(total_quality_km - deficit, 0.0)
            quality_km_each = (
                total_quality_km / quality_count if quality_count > 0 else 0.0
            )
            deficit = 0.0

    scheduled = long_run_km + quality_km_each * quality_count
    remaining = max(target_weekly_km - scheduled, 0.0)

    if easy_sessions == 0 and remaining > 0:
        # 분배할 easy 세션이 없으면 롱런/품질에 균등 분배
        bonus = remaining / (quality_count + (1 if long_run_km > 0 else 0))
        if long_run_km > 0:
            long_run_km += bonus
        if quality_count > 0:
            quality_km_each += bonus
        remaining = 0.0

    return long_run_km, quality_km_each, remaining


# -----------------------------
# 주간 계획 생성
# -----------------------------


def generate_week_plan(config: PlanConfig) -> PlanDetails:
    start = start_of_week(config.today)
    phase = determine_phase(config.today, config.race_date)
    days_left = (config.race_date - config.today).days
    weeks_left = days_left / 7.0

    target_weekly_km = compute_target_weekly_km(
        phase, config.recent_weekly_km, weeks_left
    )
    target_weekly_km = adjust_target_for_fatigue(
        target_weekly_km, config.fatigue_level
    )

    history = (
        config.long_run_history if config.long_run_history is not None else []
    )

    if config.stage3_count is not None:
        stage3_count = clamp_int(config.stage3_count, 0, 3)
        stage3_inferred = False
    else:
        stage3_count = estimate_stage3_count(history, config.recent_long_run)
        stage3_inferred = True

    if config.peak_long_done is not None:
        peak_long_done = config.peak_long_done
        peak_inferred = False
    else:
        peak_long_done = infer_peak_long_done(
            config.recent_long_run, weeks_left
        )
        peak_inferred = True

    long_run_km = select_long_run_distance(
        phase, weeks_left, config.recent_long_run, peak_long_done, stage3_count
    )

    run_days = max(config.weekly_frequency, 0)
    base_quality_count = decide_quality_sessions(
        phase,
        config.fatigue_level,
        config.recent_long_run,
        target_weekly_km,
        config.weekly_frequency,
        weeks_left,
    )

    long_slot = 1 if run_days > 0 else 0
    max_quality_allowed = max(run_days - long_slot, 0)
    quality_count = max(0, min(base_quality_count, max_quality_allowed))
    easy_sessions = max(run_days - long_slot - quality_count, 0)

    quality_km_each = (
        quality_distance_for_phase(phase, target_weekly_km)
        if quality_count > 0
        else 0.0
    )

    long_run_km, quality_km_each, easy_volume = normalize_distances(
        phase,
        target_weekly_km,
        long_run_km,
        quality_km_each,
        quality_count,
        easy_sessions,
    )

    easy_km_each = (
        easy_volume / easy_sessions if easy_sessions > 0 else 0.0
    )

    long_run_day_index = 6
    long_run_scheduled = long_slot == 1

    quality_day_indices = [
        d for d in QUALITY_DAY_PRIORITY if d != long_run_day_index
    ][:quality_count]
    easy_day_indices = [
        d
        for d in EASY_DAY_PRIORITY
        if d not in quality_day_indices and d != long_run_day_index
    ][:easy_sessions]

    plans: List[DayPlan] = []
    for i in range(7):
        current_date = start + timedelta(days=i)
        label = WEEKDAY_LABELS[i]
        if i == long_run_day_index and long_run_scheduled:
            plan_type = "LONG"
            desc = f"롱런 {long_run_km:.1f}km (일요일)"
            km = long_run_km
        elif i in quality_day_indices:
            plan_type = "QUALITY"
            desc = f"{quality_type_for_phase(phase)} ~{quality_km_each:.1f}km"
            km = quality_km_each
        elif i in easy_day_indices:
            plan_type = "EASY"
            desc = "Easy 러닝"
            km = easy_km_each
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

    return PlanDetails(
        plans=plans,
        stage3_used=stage3_count,
        stage3_inferred=stage3_inferred,
        peak_long_done=peak_long_done,
        peak_long_inferred=peak_inferred,
    )


# -----------------------------
# CLI
# -----------------------------


def print_week_plan(details: PlanDetails, target_weekly_km: float) -> None:
    print("\n===== 이번 주 러닝 플랜 =====")
    total = 0.0
    for p in details.plans:
        date_str = p.date.strftime("%Y-%m-%d")
        print(
            f"{date_str} ({p.label}) | {p.type:7} | "
            f"{p.planned_km:4.1f} km | {p.description}"
        )
        total += p.planned_km
    print("----------------------------")
    print(f"합계: {total:.1f} km (목표 {target_weekly_km:.1f} km)")

    if details.stage3_inferred:
        print(f"* Stage3 횟수 자동 추정 결과: {details.stage3_used}회 적용")
    if details.peak_long_inferred:
        status = "완료" if details.peak_long_done else "미완료"
        print(f"* 피크 롱런 완료 여부 자동 추정: {status}")


def parse_history_input(raw: str) -> Optional[List[float]]:
    if not raw.strip():
        return None
    parts = [p.strip() for p in raw.split(",")]
    values: List[float] = []
    for p in parts:
        if not p:
            continue
        try:
            values.append(float(p))
        except ValueError:
            continue
    return values or None


def gather_config_from_cli() -> PlanConfig:
    print("=== 러닝 플래너 v5 (히스토리 보강 버전) ===")
    today_str = input("오늘 날짜 (YYYY-MM-DD, Enter=오늘): ").strip()
    today = parse_date(today_str) if today_str else date.today()

    race_date = parse_date(input("레이스 날짜 (YYYY-MM-DD): ").strip())
    recent_weekly_km = float(input("최근 주간 총 거리 (km): ").strip())
    recent_long_run = float(input("최근 롱런 거리 (km): ").strip())
    weekly_freq = int(input("주간 러닝 횟수 (예: 4,5): ").strip())
    fatigue_level = int(input("현재 피로도(0~10): ").strip())

    history_input = input(
        "최근 4~6주 롱런 거리 목록(콤마, Enter=최근 기록만 사용): "
    )
    history = parse_history_input(history_input)
    if history is None:
        history = [recent_long_run]

    stage3_input = input(
        "Stage3 진행 횟수 (0~3, Enter=자동 추정): "
    ).strip()
    stage3_count = None
    if stage3_input:
        try:
            stage3_count = clamp_int(int(stage3_input), 0, 3)
        except ValueError:
            stage3_count = None

    peak_input = input(
        "30km 이상 피크 롱런 완료 여부 (y/n, Enter=자동 추정): "
    ).strip().lower()
    if peak_input in {"y", "yes"}:
        peak_long_done: Optional[bool] = True
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
        long_run_history=history,
        stage3_count=stage3_count,
        peak_long_done=peak_long_done,
    )


def main() -> None:
    config = gather_config_from_cli()
    phase = determine_phase(config.today, config.race_date)
    weeks_left = (config.race_date - config.today).days / 7.0
    target = compute_target_weekly_km(phase, config.recent_weekly_km, weeks_left)
    target = adjust_target_for_fatigue(target, config.fatigue_level)

    details = generate_week_plan(config)
    print_week_plan(details, target)


if __name__ == "__main__":
    main()

