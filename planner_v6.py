#!/usr/bin/env python3
"""
planner_v6
-----------
목표 기록 기반 · 단계별 훈련 강도 자동 조정 · 안전 스위치 내장형 러닝 훈련 생성기

Coach.md 규칙을 기반으로 작성된 최신 버전.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple, Dict


# -----------------------------
# 데이터 모델
# -----------------------------


@dataclass
class DayPlan:
    date: date
    weekday: str
    session_type: str
    distance_km: float
    pace_range: str
    structure: str
    notes: str
    safety_overrides: List[str] = field(default_factory=list)

    def formatted_description(self) -> str:
        return (
            f"{self.date.strftime('%Y-%m-%d')} ({self.weekday}) | "
            f"{self.session_type} | {self.distance_km:.1f} km | "
            f"Pace {self.pace_range} | {self.structure} | Notes: {self.notes} "
            f"{'(Safety: ' + '; '.join(self.safety_overrides) + ')' if self.safety_overrides else ''}"
        )


@dataclass
class PlanConfig:
    today: date
    race_date: date
    phase: str
    recent_weekly_km: float
    recent_long_run: float
    weekly_frequency: int
    mp_target: str
    mp_current: str
    fatigue_level: int
    altitude_gain_recent: float
    hr_delta_percent: Optional[float] = None
    pain_last_48h: bool = False
    fatigue_streak_days: int = 0
    yesterday_altitude_gain: float = 0.0
    long_run_history: Optional[List[float]] = None
    stage3_completed: int = 0
    stage4_completed: int = 0


@dataclass
class PlanResult:
    goal_mode: str
    target_weekly_km: float
    total_planned_km: float
    plans: List[DayPlan]
    notes: List[str]


@dataclass
class SafetyContext:
    pain_48h: bool
    fatigue_streak: int
    prev_day_altitude: float
    hr_delta_percent: Optional[float]


WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
QUALITY_DAY_OPTIONS = [1, 3, 5]  # Tue/Thu/Sat


# -----------------------------
# Pace helpers
# -----------------------------


def pace_to_seconds(pace_str: str) -> float:
    minutes, seconds = pace_str.strip().split(":")
    return int(minutes) * 60 + int(seconds)


def seconds_to_pace(sec: float) -> str:
    sec = max(sec, 0)
    minutes = int(sec // 60)
    seconds = int(round(sec % 60))
    return f"{minutes}:{seconds:02d}/km"


def format_range(base: float, offset_low: float, offset_high: float) -> str:
    low = seconds_to_pace(base + offset_low)
    high = seconds_to_pace(base + offset_high)
    return f"{low} ~ {high}"


# -----------------------------
# Goal mode & pace profiles
# -----------------------------


def compute_goal_mode(mp_target: float, mp_current: float) -> str:
    delta = mp_current - mp_target  # +면 목표가 더 빠름
    if mp_target >= mp_current + 5:
        return "G1"
    if delta <= 10:
        return "G2"
    return "G3"


def compute_paces(goal_mode: str, mp_target: float) -> Dict[str, str]:
    easy_offsets = {
        "G1": (70, 100),
        "G2": (55, 85),
        "G3": (45, 75),
    }
    long_stage_offsets = {
        1: (40, 70),
        2: (25, 55),
        3: (15, 45),
        4: (5, 25),
    }

    paces: Dict[str, str] = {}
    paces["easy"] = format_range(mp_target, *easy_offsets[goal_mode])
    paces["mp_run"] = format_range(mp_target, -5, 5)
    paces["tempo"] = format_range(mp_target, -25, -15)
    paces["interval"] = format_range(mp_target, -65, -40)
    paces["taper_t2"] = format_range(mp_target, 5, 15)

    for stage, offsets in long_stage_offsets.items():
        paces[f"long_stage_{stage}"] = format_range(mp_target, *offsets)
    return paces


# -----------------------------
# Safety logic
# -----------------------------


def apply_safety_overrides(
    plan: DayPlan,
    context: SafetyContext,
    fatigue_level: int,
) -> DayPlan:
    overrides = []

    if context.pain_48h:
        overrides.append("48시간 통증 → 강훈 금지")
        plan.session_type = "Rest / Recovery"
        plan.distance_km = 0.0
        plan.structure = "Complete Rest (통증 관리)"
        plan.pace_range = "-"

    if context.fatigue_streak >= 3 and plan.session_type.startswith("Quality"):
        overrides.append("3일 연속 피로 → Easy 전환")
        plan = build_easy_session(
            plan.date,
            plan.weekday,
            plan.distance_km or 8.0,
            "피로 누적 안전 스위치",
        )

    if context.prev_day_altitude > 300 and plan.session_type.startswith("Quality"):
        overrides.append("전날 고도 >300m → Easy 전환")
        plan = build_easy_session(
            plan.date,
            plan.weekday,
            max(plan.distance_km, 8.0),
            "고도 회복 모드",
        )

    if context.hr_delta_percent and context.hr_delta_percent >= 8:
        if plan.session_type.startswith("Quality"):
            overrides.append("HR +8% → 품질 금지")
            plan = build_easy_session(
                plan.date, plan.weekday, plan.distance_km or 6.0, "HR 안정화"
            )

    if fatigue_level >= 7 and plan.session_type.startswith("Quality"):
        overrides.append("피로도 7 이상 → 품질 금지")
        plan = build_easy_session(
            plan.date, plan.weekday, plan.distance_km or 6.0, "고피로 회복"
        )

    plan.safety_overrides.extend(overrides)
    return plan


def estimate_session_altitude(plan: DayPlan, default_gain: float) -> float:
    if plan.session_type.startswith("Long"):
        return max(350.0, default_gain)
    if plan.session_type.startswith("Quality"):
        return 250.0
    if plan.session_type.startswith("Easy"):
        return min(default_gain, 150.0)
    return 50.0


# -----------------------------
# Session builders
# -----------------------------


def build_easy_session(
    session_date: date,
    weekday: str,
    distance: float,
    notes: str,
    pace: str = "",
) -> DayPlan:
    return DayPlan(
        date=session_date,
        weekday=weekday,
        session_type="Easy Run",
        distance_km=distance,
        pace_range=pace or "유연 (목표 MP 기반 +45~90초)",
        structure=f"Easy jog {distance:.1f}km",
        notes=notes,
    )


def build_point_session(
    session_date: date,
    weekday: str,
    session_kind: str,
    distance: float,
    pace_range: str,
    structure: str,
    purpose: str,
) -> DayPlan:
    return DayPlan(
        date=session_date,
        weekday=weekday,
        session_type=f"Quality - {session_kind}",
        distance_km=distance,
        pace_range=pace_range,
        structure=structure,
        notes=purpose,
    )


def build_long_run_structure(
    session_date: date,
    weekday: str,
    stage: int,
    distance: float,
    pace_range: str,
    goal_mode: str,
) -> DayPlan:
    if stage == 4:
        mp_ratio = {"G1": 0.0, "G2": 0.25, "G3": 0.35}[goal_mode]
    elif stage == 3:
        mp_ratio = {"G1": 0.0, "G2": 0.2, "G3": 0.3}[goal_mode]
    else:
        mp_ratio = {"G1": 0.0, "G2": 0.15, "G3": 0.2}[goal_mode]

    mp_distance = distance * mp_ratio
    warmup = distance - mp_distance
    structure = (
        f"{warmup:.1f}km Easy-LR + {mp_distance:.1f}km MP finish"
        if mp_distance > 0
        else f"Continuous LR {distance:.1f}km"
    )
    notes = f"Stage{stage} 롱런 | 후반 MP 비율 {mp_ratio*100:.0f}%"

    return DayPlan(
        date=session_date,
        weekday=weekday,
        session_type=f"Long Run (Stage {stage})",
        distance_km=distance,
        pace_range=pace_range,
        structure=structure,
        notes=notes,
    )


def make_description_rich(plan: DayPlan) -> str:
    return plan.formatted_description()


# -----------------------------
# Planner 클래스
# -----------------------------


class Planner:
    def __init__(self, config: PlanConfig):
        self.config = config
        self.mp_target_sec = pace_to_seconds(config.mp_target)
        self.mp_current_sec = pace_to_seconds(config.mp_current)
        self.goal_mode = compute_goal_mode(
            self.mp_target_sec, self.mp_current_sec
        )
        self.paces = compute_paces(self.goal_mode, self.mp_target_sec)
        self.history = config.long_run_history or [config.recent_long_run]

    def determine_stage(self) -> int:
        lr = self.config.recent_long_run
        if lr >= 30 and self.config.stage4_completed == 0:
            return 4
        if lr >= 26:
            if self.config.stage3_completed >= 2:
                return 2
            return 3
        if lr >= 22:
            return 2
        return 1

    def adjusted_target_volume(self) -> float:
        base = min(self.config.recent_weekly_km * 1.1, 82)
        goal_caps = {"G1": 60.0, "G2": 75.0, "G3": 82.0}
        capped = min(base, goal_caps[self.goal_mode])
        fatigue_adjustment = 0.8 if self.config.fatigue_level >= 7 else 1.0
        return capped * fatigue_adjustment

    def decide_quality_count(self) -> int:
        fatigue = self.config.fatigue_level
        phase = self.config.phase.upper()
        if fatigue >= 7:
            return 0
        if phase == "BASE":
            return 1 if self.goal_mode != "G1" and fatigue <= 4 else 0
        if phase == "BUILD":
            return 1 if fatigue >= 5 else 2
        if phase == "PEAK":
            return 2 if fatigue <= 5 else 1
        if phase == "TAPER":
            weeks_left = self.estimate_weeks_left()
            return 1 if weeks_left > 1.5 else 0
        return 1

    def estimate_weeks_left(self) -> float:
        return max((self.config.race_date - self.config.today).days / 7.0, 0.0)

    def stage_adjustments(self, stage: int) -> int:
        if self.config.fatigue_level >= 7 and stage >= 3:
            return 2
        if stage == 3 and self.config.stage3_completed >= 2:
            return 2
        if stage == 4 and self.config.stage4_completed >= 1:
            return 3
        return stage

    def schedule_days(self, quality_count: int) -> Dict[int, str]:
        plan = {i: "Rest" for i in range(7)}
        run_days = min(self.config.weekly_frequency, 6)

        long_day = 6
        plan[long_day] = "Long"
        run_days -= 1

        assigned_quality = 0
        for idx in QUALITY_DAY_OPTIONS:
            if assigned_quality >= quality_count or run_days <= 0:
                break
            plan[idx] = "Quality"
            assigned_quality += 1
            run_days -= 1

        i = 0
        while run_days > 0 and i < 7:
            if plan[i] == "Rest":
                plan[i] = "Easy"
                run_days -= 1
            i += 1

        return plan

    def build_week(self) -> PlanResult:
        notes: List[str] = []
        target_km = self.adjusted_target_volume()
        stage = self.stage_adjustments(self.determine_stage())
        long_distance = self.long_run_distance_for_stage(stage)

        quality_count = self.decide_quality_count()
        if self.config.hr_delta_percent and self.config.hr_delta_percent >= 8:
            quality_count = 0
            notes.append("HR +8% → 품질 세션 생략")

        schedule = self.schedule_days(quality_count)
        safety_context = SafetyContext(
            pain_48h=self.config.pain_last_48h,
            fatigue_streak=self.config.fatigue_streak_days,
            prev_day_altitude=self.config.yesterday_altitude_gain,
            hr_delta_percent=self.config.hr_delta_percent,
        )

        plans: List[DayPlan] = []
        remaining_easy_volume = max(target_km - long_distance, 0.0)
        easy_sessions_planned = list(schedule.values()).count("Easy")
        easy_distance_default = (
            remaining_easy_volume / max(easy_sessions_planned, 1)
            if easy_sessions_planned > 0
            else 0.0
        )

        for i in range(7):
            current_date = self.config.today + timedelta(days=i)
            session_label = schedule[i]
            if session_label == "Long":
                plan = build_long_run_structure(
                    current_date,
                    WEEKDAY_LABELS[i],
                    stage,
                    long_distance,
                    self.paces[f"long_stage_{stage}"],
                    self.goal_mode,
                )
            elif session_label == "Quality":
                plan = self.build_point_training_session(
                    current_date, WEEKDAY_LABELS[i]
                )
            elif session_label == "Easy":
                plan = build_easy_session(
                    current_date,
                    WEEKDAY_LABELS[i],
                    max(easy_distance_default, 6.0),
                    "기본 Easy 세션",
                    self.paces["easy"],
                )
            else:
                plan = DayPlan(
                    date=current_date,
                    weekday=WEEKDAY_LABELS[i],
                    session_type="Rest / Mobility",
                    distance_km=0.0,
                    pace_range="-",
                    structure="Mobility + 스트레칭",
                    notes="완전 회복",
                )

            plan = apply_safety_overrides(
                plan, safety_context, self.config.fatigue_level
            )
            plans.append(plan)

            est_alt = estimate_session_altitude(
                plan, self.config.altitude_gain_recent / max(self.config.weekly_frequency, 1)
            )
            safety_context.prev_day_altitude = est_alt
            if plan.session_type.startswith("Easy") or plan.session_type.startswith(
                "Rest"
            ):
                safety_context.fatigue_streak = 0
            else:
                safety_context.fatigue_streak += 1

        plans = self.balance_total_distance(plans, target_km)
        total = sum(p.distance_km for p in plans)
        return PlanResult(
            goal_mode=self.goal_mode,
            target_weekly_km=target_km,
            total_planned_km=total,
            plans=plans,
            notes=notes,
        )

    def long_run_distance_for_stage(self, stage: int) -> float:
        if self.config.phase.upper() == "TAPER":
            weeks_left = self.estimate_weeks_left()
            if weeks_left <= 0.5:
                return 4.0
            if weeks_left <= 1.5:
                return 16.0
            return 22.0

        distances = {1: 20.0, 2: 24.0, 3: 28.0, 4: 32.0}
        return distances.get(stage, 20.0)

    def build_point_training_session(
        self, session_date: date, weekday: str
    ) -> DayPlan:
        phase = self.config.phase.upper()
        if phase == "BASE":
            kind = "Tempo"
            distance = 10.0
            pace = self.paces["tempo"]
            structure = "2km warm / 6km tempo / 2km easy"
            purpose = "LT 상승"
        elif phase == "BUILD":
            kind = "MP Run" if self.goal_mode == "G1" else "Tempo"
            distance = 12.0
            pace = self.paces["mp_run"] if kind == "MP Run" else self.paces["tempo"]
            structure = "3km warm / 6km MP-T / 3km easy"
            purpose = "마라톤 페이스 감각"
        elif phase == "PEAK":
            kind = "Interval" if self.goal_mode == "G3" else "Tempo"
            distance = 14.0
            pace = (
                self.paces["interval"]
                if kind == "Interval"
                else self.paces["tempo"]
            )
            structure = (
                "3km warm / 5x1km @I w/400m jog / 3km easy"
                if kind == "Interval"
                else "3km warm / 8km tempo / 3km easy"
            )
            purpose = "최고 스피드 지구력"
        else:
            kind = "MP Run"
            distance = 10.0
            pace = self.paces["taper_t2"]
            structure = "2km warm / 6km steady / 2km easy"
            purpose = "리듬 유지"

        return build_point_session(
            session_date,
            weekday,
            kind,
            distance,
            pace,
            structure,
            purpose,
        )

    def balance_total_distance(
        self, plans: List[DayPlan], target: float
    ) -> List[DayPlan]:
        total = sum(p.distance_km for p in plans)
        easy_sessions = [p for p in plans if p.session_type.startswith("Easy")]
        if not easy_sessions:
            return plans
        diff = total - target
        if abs(diff) < 1.0:
            return plans

        adjust_per = diff / len(easy_sessions)
        for plan in easy_sessions:
            plan.distance_km = max(plan.distance_km - adjust_per, 4.0)
            plan.structure = f"Easy jog {plan.distance_km:.1f}km (조정)"

        return plans


# -----------------------------
# CLI
# -----------------------------


def prompt_float(message: str, default: float) -> float:
    raw = input(f"{message} (Enter={default}): ").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def prompt_int(message: str, default: int) -> int:
    raw = input(f"{message} (Enter={default}): ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def prompt_pace(message: str, default: str) -> str:
    raw = input(f"{message} (mm:ss, Enter={default}): ").strip()
    if not raw:
        return default
    try:
        pace_to_seconds(raw)
        return raw
    except ValueError:
        return default


def gather_config_from_cli() -> PlanConfig:
    print("=== 러닝 플래너 v6 ===")
    today_default = date.today()
    today_str = input(
        f"오늘 날짜 (YYYY-MM-DD, Enter={today_default.isoformat()}): "
    ).strip()
    today = (
        datetime.strptime(today_str, "%Y-%m-%d").date()
        if today_str
        else today_default
    )
    default_race = today + timedelta(days=56)
    race_str = input(
        f"레이스 날짜 (YYYY-MM-DD, Enter={default_race.isoformat()}): "
    ).strip()
    race_date = (
        datetime.strptime(race_str, "%Y-%m-%d").date()
        if race_str
        else default_race
    )
    phase = (
        input("훈련 단계(BASE/BUILD/PEAK/TAPER, Enter=BASE): ")
        .strip()
        .upper()
        or "BASE"
    )
    recent_weekly_km = prompt_float("최근 주간 총 거리(km)", 45.0)
    recent_long_run = prompt_float("최근 롱런 거리(km)", 18.0)
    weekly_freq = prompt_int("주간 러닝 횟수", 4)
    mp_target = prompt_pace("목표 MP", "05:30")
    mp_current = prompt_pace("최근 기록 기반 MP", mp_target)
    fatigue = prompt_int("피로도(0~10)", 3)
    altitude_recent = prompt_float("최근 주간 고도(m)", 0.0)
    hr_delta_raw = input("HR 증감(%), Enter=미적용: ").strip()
    hr_delta = None
    if hr_delta_raw:
        try:
            hr_delta = float(hr_delta_raw)
        except ValueError:
            hr_delta = None
    pain_flag = input("48시간 내 통증 있었나요? (y/N): ").strip().lower().startswith("y")
    fatigue_streak = prompt_int("최근 연속 피로 일수", 0)
    yesterday_alt = prompt_float("어제 고도(m)", 0.0)
    history_input = input(
        "최근 4~6주 롱런 거리(콤마, Enter=최근 기록만 사용): "
    ).strip()
    history = (
        [float(x) for x in history_input.split(",") if x.strip()]
        if history_input
        else None
    )
    stage3_completed = prompt_int("이번 싸이클 Stage3 수행 횟수", 0)
    stage4_completed = prompt_int("이번 싸이클 Stage4 수행 횟수", 0)

    return PlanConfig(
        today=today,
        race_date=race_date,
        phase=phase,
        recent_weekly_km=recent_weekly_km,
        recent_long_run=recent_long_run,
        weekly_frequency=weekly_freq,
        mp_target=mp_target,
        mp_current=mp_current,
        fatigue_level=fatigue,
        altitude_gain_recent=altitude_recent,
        hr_delta_percent=hr_delta,
        pain_last_48h=pain_flag,
        fatigue_streak_days=fatigue_streak,
        yesterday_altitude_gain=yesterday_alt,
        long_run_history=history,
        stage3_completed=stage3_completed,
        stage4_completed=stage4_completed,
    )


def print_plan(result: PlanResult) -> None:
    print("\n=== 주간 개요 ===")
    print(f"Goal Mode: {result.goal_mode}")
    print(f"목표 주간 거리: {result.target_weekly_km:.1f} km")
    print(f"계획 주간 거리: {result.total_planned_km:.1f} km")
    if result.notes:
        print("Notes: " + "; ".join(result.notes))

    print("\n=== 요일별 계획 ===")
    for plan in result.plans:
        print(make_description_rich(plan))
        if plan.safety_overrides:
            print("  -> Safety overrides: " + ", ".join(plan.safety_overrides))


def main() -> None:
    config = gather_config_from_cli()
    planner = Planner(config)
    result = planner.build_week()
    print_plan(result)


if __name__ == "__main__":
    main()
