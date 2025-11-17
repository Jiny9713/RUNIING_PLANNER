#!/usr/bin/env python3
"""
planner_v7
-----------
Goal-mode 기반 · 단계별 강도 자동 조정 · 안전 스위치 내장형 러닝 플래너 (Coach.md v4 반영)

주요 특징:
- 오늘/레이스 날짜로 Phase 자동 판정
- Goal Mode(G1/G2/G3) 및 MP 기반 페이스 산출
- 롱런 Stage 제한 및 안전 스위치(피로 연속, 고도 추정) 적용
- Race week strides/short jog 패턴 포함
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional


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

    def formatted(self) -> str:
        info = (
            f"{self.date:%Y-%m-%d} ({self.weekday}) | {self.session_type} | "
            f"{self.distance_km:.1f} km | Pace {self.pace_range} | {self.structure}"
        )
        note = f" | Notes: {self.notes}" if self.notes else ""
        safe = (
            f" | Safety: {', '.join(self.safety_overrides)}"
            if self.safety_overrides
            else ""
        )
        return info + note + safe


@dataclass
class PlanConfig:
    today: date
    race_date: date
    recent_weekly_km: float
    recent_long_run: float
    weekly_frequency: int
    mp_target: str
    mp_current: str
    fatigue_level: int
    long_run_history: Optional[List[float]] = None


@dataclass
class PlanResult:
    goal_mode: str
    phase: str
    target_weekly_km: float
    total_planned_km: float
    notes: List[str]
    plans: List[DayPlan]


@dataclass
class SafetyContext:
    fatigue_streak: int = 0
    prev_day_altitude: float = 0.0


WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
QUALITY_DAY_OPTIONS = [1, 3, 5]  # Tue/Thu/Sat 기본 품질 슬롯


# -----------------------------
# 보조 함수
# -----------------------------


def pace_to_seconds(pace_str: str) -> float:
    minute, sec = pace_str.strip().split(":")
    return int(minute) * 60 + int(sec)


def seconds_to_pace(sec: float) -> str:
    sec = max(sec, 0)
    minute = int(sec // 60)
    second = int(round(sec % 60))
    return f"{minute}:{second:02d}/km"


def format_range(base: float, low_offset: float, high_offset: float) -> str:
    return f"{seconds_to_pace(base + low_offset)} ~ {seconds_to_pace(base + high_offset)}"


def determine_phase(today: date, race_date: date) -> str:
    weeks_left = max((race_date - today).days / 7.0, 0.0)
    if weeks_left >= 10:
        return "BASE"
    if weeks_left >= 6:
        return "BUILD"
    if weeks_left >= 3:
        return "PEAK"
    return "TAPER"


# -----------------------------
# Goal mode & pace
# -----------------------------


def compute_goal_mode(mp_target: float, mp_current: float) -> str:
    delta = mp_current - mp_target  # +면 목표가 더 빠름
    if delta <= 0:
        return "G1"
    if delta <= 20:  # 20초 이내면 현실 PB 영역
        return "G2"
    return "G3"  # 공격형


def compute_paces(goal_mode: str, mp_target: float) -> Dict[str, str]:
    easy_offsets = {
        "G1": (70, 100),
        "G2": (55, 85),
        "G3": (45, 75),
    }
    long_offsets = {
        1: (40, 70),
        2: (25, 55),
        3: (15, 45),
        4: (5, 25),
    }
    paces: Dict[str, str] = {
        "easy": format_range(mp_target, *easy_offsets[goal_mode]),
        "mp": format_range(mp_target, -5, 5),
        "tempo": format_range(mp_target, -25, -15),
        "interval": format_range(mp_target, -65, -40),
        "taper": format_range(mp_target, 5, 15),
    }
    for stage, offsets in long_offsets.items():
        paces[f"long_{stage}"] = format_range(mp_target, *offsets)
    return paces


# -----------------------------
# 세션 빌더
# -----------------------------


def build_easy_session(
    session_date: date,
    weekday: str,
    distance: float,
    notes: str,
    pace: str,
) -> DayPlan:
    return DayPlan(
        date=session_date,
        weekday=weekday,
        session_type="Easy",
        distance_km=distance,
        pace_range=pace,
        structure=f"Easy jog {distance:.1f}km",
        notes=notes,
    )


def build_point_session(
    session_date: date,
    weekday: str,
    kind: str,
    distance: float,
    pace_range: str,
    structure: str,
    purpose: str,
) -> DayPlan:
    return DayPlan(
        date=session_date,
        weekday=weekday,
        session_type=f"Quality - {kind}",
        distance_km=distance,
        pace_range=pace_range,
        structure=structure,
        notes=purpose,
    )


def build_long_run_session(
    session_date: date,
    weekday: str,
    stage: int,
    distance: float,
    pace_range: str,
    goal_mode: str,
) -> DayPlan:
    mp_ratio = {"G1": 0.0, "G2": 0.2, "G3": 0.3}[goal_mode]
    if stage == 4:
        mp_ratio = {"G1": 0.0, "G2": 0.25, "G3": 0.35}[goal_mode]
    elif stage == 1:
        mp_ratio = 0.0
    mp_distance = distance * mp_ratio
    structure = (
        f"{distance - mp_distance:.1f}km Easy-LR + {mp_distance:.1f}km MP finish"
        if mp_distance > 0
        else f"Continuous LR {distance:.1f}km"
    )
    notes = f"Stage{stage} 롱런 | 후반 MP {mp_ratio*100:.0f}%"
    return DayPlan(
        date=session_date,
        weekday=weekday,
        session_type=f"Long Run (Stage {stage})",
        distance_km=distance,
        pace_range=pace_range,
        structure=structure,
        notes=notes,
    )


def build_strides_session(session_date: date, weekday: str, pace: str) -> DayPlan:
    return DayPlan(
        date=session_date,
        weekday=weekday,
        session_type="Easy + Strides",
        distance_km=4.0,
        pace_range=pace,
        structure="3km Easy + 3×80m strides",
        notes="Race week 리듬 유지",
    )


# -----------------------------
# 안전 스위치
# -----------------------------


def estimate_session_altitude(plan: DayPlan, default_gain: float) -> float:
    if plan.session_type.startswith("Long"):
        return max(default_gain, 350.0)
    if plan.session_type.startswith("Quality"):
        return max(default_gain, 220.0)
    if plan.session_type.startswith("Easy"):
        return max(default_gain * 0.5, 120.0)
    return 60.0


def apply_safety_overrides(
    plan: DayPlan,
    context: SafetyContext,
    fatigue_level: int,
    easy_pace: str,
) -> DayPlan:
    overrides: List[str] = []
    if context.fatigue_streak >= 3:
        overrides.append("피로 3일 연속 → Easy 전환")
        distance = 14.0 if plan.session_type.startswith("Long") else max(plan.distance_km, 8.0)
        plan = build_easy_session(plan.date, plan.weekday, distance, "안전 스위치", easy_pace)

    if context.prev_day_altitude > 300 and plan.session_type.startswith("Quality"):
        overrides.append("전날 고도 >300m → Easy")
        plan = build_easy_session(plan.date, plan.weekday, max(plan.distance_km, 8.0), "고도 회복", easy_pace)

    if fatigue_level >= 7 and plan.session_type.startswith("Quality"):
        overrides.append("피로도 7 이상 → 품질 제한")
        plan = build_easy_session(plan.date, plan.weekday, max(plan.distance_km, 6.0), "High fatigue", easy_pace)

    plan.safety_overrides.extend(overrides)
    return plan


# -----------------------------
# Planner
# -----------------------------


class Planner:
    def __init__(self, config: PlanConfig):
        self.config = config
        self.phase = determine_phase(config.today, config.race_date)
        self.weeks_left = max((config.race_date - config.today).days / 7.0, 0.0)
        self.mp_target_sec = pace_to_seconds(config.mp_target)
        self.mp_current_sec = pace_to_seconds(config.mp_current)
        self.goal_mode = compute_goal_mode(self.mp_target_sec, self.mp_current_sec)
        self.paces = compute_paces(self.goal_mode, self.mp_target_sec)
        self.history = config.long_run_history or [config.recent_long_run]
        self.stage3_history = sum(1 for d in self.history[-6:] if 26 <= d < 30)
        self.stage4_history = sum(1 for d in self.history[-6:] if d >= 30)
        self.weekly_altitude_sum = self.estimate_weekly_altitude()

    def estimate_weekly_altitude(self) -> float:
        base = self.config.recent_weekly_km * 8.0  # 기본 ~8m/km
        bonus = sum(max(d - 20.0, 0.0) * 10.0 for d in self.history[-4:])
        return base + bonus

    def adjusted_target_volume(self) -> float:
        base = min(self.config.recent_weekly_km * 1.1, 82.0)
        caps = {"G1": 60.0, "G2": 75.0, "G3": 82.0}
        base = min(base, caps[self.goal_mode])
        if self.phase == "TAPER":
            if self.weeks_left > 1.5:
                base *= 0.8
            elif self.weeks_left > 0.5:
                base *= 0.6
            else:
                base *= 0.4
        if self.config.fatigue_level >= 7:
            return base * 0.8
        if self.config.fatigue_level == 6:
            return base * 0.9
        return base

    def determine_stage(self) -> int:
        lr = self.config.recent_long_run
        if self.phase == "BASE":
            if lr < 22:
                return 1
            return 2
        if self.phase == "BUILD":
            if lr < 24:
                return 2
            return 3
        if self.phase == "PEAK":
            if lr >= 30:
                return 4
            return 3
        return 2

    def stage_adjustments(self, stage: int, notes: List[str]) -> int:
        stage = min(stage, 4)
        if stage >= 3 and (self.config.fatigue_level >= 7 or self.config.fatigue_level == 6):
            notes.append("피로도 제약으로 롱런 Stage ↓")
            stage = 2
        if stage == 3 and self.stage3_history >= 2:
            notes.append("Stage3 2회 수행 → 이번 주 Stage2")
            stage = 2
        if stage == 4 and self.stage4_history >= 1:
            notes.append("Stage4 이미 수행 → Stage3 유지")
            stage = 3
        if self.weekly_altitude_sum >= 1000 and stage >= 3:
            notes.append("주간 고도 1000m↑ → Stage2 제한")
            stage = 2
        if self.phase == "TAPER":
            stage = min(stage, 2)
        return stage

    def decide_quality_count(self) -> int:
        fatigue = self.config.fatigue_level
        if fatigue >= 7:
            return 0
        if self.phase == "BASE":
            return 1 if self.goal_mode != "G1" and fatigue <= 4 else 0
        if self.phase == "BUILD":
            return 1 if fatigue >= 6 else 2
        if self.phase == "PEAK":
            return 2 if fatigue <= 5 else 1
        if self.phase == "TAPER":
            return 1 if self.weeks_left > 1.5 else 0
        return 1

    def schedule_days(self, quality_count: int) -> Dict[int, str]:
        if self.weeks_left <= 0.5:
            return {0: "Easy", 1: "Strides", 2: "Rest", 3: "Easy", 4: "Rest", 5: "Rest", 6: "Long"}

        plan = {i: "Rest" for i in range(7)}
        run_days = min(self.config.weekly_frequency, 6)
        plan[6] = "Long"
        run_days -= 1
        assigned_q = 0
        for idx in QUALITY_DAY_OPTIONS:
            if assigned_q >= quality_count or run_days <= 0:
                break
            plan[idx] = "Quality"
            assigned_q += 1
            run_days -= 1
        i = 0
        while run_days > 0 and i < 7:
            if plan[i] == "Rest":
                plan[i] = "Easy"
                run_days -= 1
            i += 1
        return plan

    def long_run_distance(self, stage: int) -> float:
        if self.phase == "TAPER":
            if self.weeks_left <= 0.5:
                return 4.0
            if self.weeks_left <= 1.5:
                return 16.0
            return 22.0
        table = {1: 20.0, 2: 24.0, 3: 28.0, 4: 32.0}
        return table.get(stage, 20.0)

    def build_point_session(self, session_date: date, weekday: str) -> DayPlan:
        if self.phase == "BASE":
            return build_point_session(
                session_date,
                weekday,
                "Tempo",
                10.0,
                self.paces["tempo"],
                "2km warm / 6km tempo / 2km easy",
                "LT 기반 강화",
            )
        if self.phase == "BUILD":
            kind = "MP Run" if self.goal_mode == "G1" else "Tempo"
            pace = self.paces["mp"] if kind == "MP Run" else self.paces["tempo"]
            structure = "3km warm / 6km MP / 3km easy" if kind == "MP Run" else "3km warm / 8km tempo / 3km easy"
            purpose = "MP 감각" if kind == "MP Run" else "젖산 역치"
            return build_point_session(session_date, weekday, kind, 12.0, pace, structure, purpose)
        if self.phase == "PEAK":
            kind = "Interval" if self.goal_mode == "G3" else "Tempo"
            pace = self.paces["interval"] if kind == "Interval" else self.paces["tempo"]
            structure = "3km warm / 5×1km @I (400m jog) / 3km easy" if kind == "Interval" else "3km warm / 8km tempo / 3km easy"
            purpose = "스피드 지구력" if kind == "Interval" else "마라톤 특이성"
            return build_point_session(session_date, weekday, kind, 14.0, pace, structure, purpose)
        return build_point_session(
            session_date,
            weekday,
            "MP Run",
            10.0,
            self.paces["taper"],
            "2km warm / 6km steady / 2km easy",
            "Taper 리듬 유지",
        )

    def build_week(self) -> PlanResult:
        notes: List[str] = []
        target_km = self.adjusted_target_volume()
        base_stage = self.determine_stage()
        stage = self.stage_adjustments(base_stage, notes)
        long_distance = self.long_run_distance(stage)

        quality_count = self.decide_quality_count()
        if self.weekly_altitude_sum >= 1000:
            quality_count = min(quality_count, 1)
            notes.append("고도 부하 ↑ → 품질 1회 제한")
        if self.weeks_left <= 0.5:
            quality_count = 0

        schedule = self.schedule_days(quality_count)
        safety = SafetyContext()
        plans: List[DayPlan] = []
        easy_sessions = sum(1 for v in schedule.values() if v == "Easy")
        remaining_easy_km = max(target_km - long_distance - quality_count * 12.0, 0.0)
        easy_default = remaining_easy_km / easy_sessions if easy_sessions else 0.0

        for idx in range(7):
            current_date = self.config.today + timedelta(days=idx)
            label = WEEKDAY_LABELS[idx]
            slot = schedule.get(idx, "Rest")
            if slot == "Long":
                plan = build_long_run_session(current_date, label, stage, long_distance, self.paces[f"long_{stage}"], self.goal_mode)
            elif slot == "Quality":
                plan = self.build_point_session(current_date, label)
            elif slot == "Easy":
                plan = build_easy_session(current_date, label, max(easy_default, 6.0), "기본 Easy", self.paces["easy"])
            elif slot == "Strides":
                plan = build_strides_session(current_date, label, self.paces["easy"])
            else:
                plan = DayPlan(current_date, label, "Rest / Mobility", 0.0, "-", "Mobility & Stretch", "완전 회복")

            plan = apply_safety_overrides(plan, safety, self.config.fatigue_level, self.paces["easy"])
            plans.append(plan)

            est_alt = estimate_session_altitude(plan, self.config.recent_weekly_km * 0.5)
            safety.prev_day_altitude = est_alt
            if plan.session_type.startswith("Easy") or plan.session_type.startswith("Rest"):
                safety.fatigue_streak = 0
            else:
                safety.fatigue_streak += 1

        plans = self.balance_total_distance(plans, target_km)
        total = sum(p.distance_km for p in plans)
        return PlanResult(self.goal_mode, self.phase, target_km, total, notes, plans)

    def balance_total_distance(self, plans: List[DayPlan], target: float) -> List[DayPlan]:
        total = sum(p.distance_km for p in plans)
        easy_sessions = [p for p in plans if p.session_type.startswith("Easy")]
        if not easy_sessions or abs(total - target) < 1.0:
            return plans
        adjust = (total - target) / len(easy_sessions)
        for plan in easy_sessions:
            plan.distance_km = max(plan.distance_km - adjust, 4.0)
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


def parse_history_input(raw: str) -> Optional[List[float]]:
    raw = raw.strip()
    if not raw:
        return None
    values: List[float] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(float(part))
        except ValueError:
            continue
    return values or None


def gather_config_from_cli() -> PlanConfig:
    print("=== 러닝 플래너 v7 ===")
    today_default = date.today()
    today_raw = input(f"오늘 날짜 (YYYY-MM-DD, Enter={today_default:%Y-%m-%d}): ").strip()
    today = datetime.strptime(today_raw, "%Y-%m-%d").date() if today_raw else today_default
    race_default = today + timedelta(days=70)
    race_raw = input(f"레이스 날짜 (YYYY-MM-DD, Enter={race_default:%Y-%m-%d}): ").strip()
    race_date = datetime.strptime(race_raw, "%Y-%m-%d").date() if race_raw else race_default
    recent_weekly_km = prompt_float("최근 주간 총 거리(km)", 45.0)
    recent_long_run = prompt_float("최근 롱런 거리(km)", 18.0)
    weekly_freq = prompt_int("주간 러닝 횟수", 4)
    mp_target = prompt_pace("목표 MP", "05:30")
    mp_current = prompt_pace("최근 기록 기반 MP", mp_target)
    fatigue = prompt_int("현재 피로도(0~10)", 3)
    history = parse_history_input(input("최근 4~6주 롱런 거리(콤마, Enter=최근 기록만): "))

    return PlanConfig(
        today=today,
        race_date=race_date,
        recent_weekly_km=recent_weekly_km,
        recent_long_run=recent_long_run,
        weekly_frequency=weekly_freq,
        mp_target=mp_target,
        mp_current=mp_current,
        fatigue_level=fatigue,
        long_run_history=history,
    )


def print_plan(result: PlanResult) -> None:
    print("\n=== 주간 개요 ===")
    print(f"Phase: {result.phase} | Goal Mode: {result.goal_mode}")
    print(f"목표 주간 거리: {result.target_weekly_km:.1f} km | 계획 주간 거리: {result.total_planned_km:.1f} km")
    if result.notes:
        print("Notes: " + "; ".join(result.notes))

    print("\n=== 요일별 DayPlan ===")
    for plan in result.plans:
        print(plan.formatted())


def main() -> None:
    config = gather_config_from_cli()
    planner = Planner(config)
    result = planner.build_week()
    print_plan(result)


if __name__ == "__main__":
    main()
