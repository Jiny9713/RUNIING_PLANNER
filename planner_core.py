#!/usr/bin/env python3
"""
planner_v7
-----------
Goal-mode 기반 · 단계별 강도 자동 조정 · 안전 스위치 내장형 러닝 플래너 (Coach.md v4 반영)

주요 특징:
- 오늘/레이스 날짜로 Phase 자동 판정
- Goal Mode(G1/G2/G3) 및 MP 기반 페이스 산출
- 롱런 Stage 제한 및 안전 스위치(피로 연속, 고도 추정) 적용
- 부상 여부 기반 주간 볼륨 휴리스틱
- Race week strides/short jog 패턴 포함
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Dict, List, Optional


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

    def formatted(self) -> str:
        info = (
            f"{self.date:%Y-%m-%d} ({self.weekday}) | {self.session_type} | "
            f"{self.distance_km:.1f} km | Pace {self.pace_range} | {self.structure}"
        )
        note = f" | Notes: {self.notes}" if self.notes else ""
        return info + note


@dataclass
class PlanConfig:
    race_date: date
    recent_weekly_km: float
    recent_long_km: float
    goal_marathon_time: str
    current_mp: str
    injury_flag: bool = False


@dataclass
class PlanResult:
    goal_mode: str
    phase: str
    target_weekly_km: float
    total_planned_km: float
    notes: List[str]
    plans: List[DayPlan]


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


def marathon_time_to_pace(goal_time: str) -> str:
    """
    Convert a marathon finish time string (HH:MM or HH:MM:SS) into an MP pace string.
    """
    parts = goal_time.strip().split(":")
    if not parts or not all(part.isdigit() for part in parts):
        raise ValueError("Invalid marathon goal time format")
    parts = [int(p) for p in parts]
    if len(parts) == 2:
        hours, minutes = parts
        seconds = 0
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError("Goal time must be HH:MM or HH:MM:SS")
    total_seconds = hours * 3600 + minutes * 60 + seconds
    if total_seconds <= 0:
        raise ValueError("Goal time must be positive")
    pace_seconds = total_seconds / 42.195
    return seconds_to_pace(pace_seconds).replace("/km", "")


def derive_weekly_frequency(recent_weekly_km: float) -> int:
    if recent_weekly_km < 30:
        return 4
    if recent_weekly_km < 55:
        return 5
    return 6


def build_long_run_history(recent_long_km: float) -> List[float]:
    base = max(recent_long_km, 18.0)
    return [max(base - idx * 2.0, 16.0) for idx in range(4)]


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
# Planner
# -----------------------------


class Planner:
    def __init__(self, config: PlanConfig, *, start_date: Optional[date] = None):
        self.config = config
        self.start_date = start_date or date.today()
        self.phase = determine_phase(self.start_date, config.race_date)
        self.weeks_left = max((config.race_date - self.start_date).days / 7.0, 0.0)
        try:
            goal_pace = marathon_time_to_pace(config.goal_marathon_time)
        except ValueError:
            goal_pace = config.current_mp
        self.mp_target_sec = pace_to_seconds(goal_pace)
        self.mp_current_sec = pace_to_seconds(config.current_mp)
        self.goal_mode = compute_goal_mode(self.mp_target_sec, self.mp_current_sec)
        self.paces = compute_paces(self.goal_mode, self.mp_target_sec)
        self.weekly_frequency = derive_weekly_frequency(config.recent_weekly_km)
        self.history = build_long_run_history(config.recent_long_km)
        self.stage3_history = sum(1 for d in self.history[-6:] if 26 <= d < 30)
        self.stage4_history = sum(1 for d in self.history[-6:] if d >= 30)

    def adjusted_target_volume(self) -> float:
        # 부상 여부와 최근 주간 거리 추세를 함께 고려해 목표 볼륨을 산출한다.
        caps = {"G1": 60.0, "G2": 75.0, "G3": 82.0}
        phase_factor = {"BASE": 0.70, "BUILD": 0.85, "PEAK": 0.95, "TAPER": 0.60}

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

        if self.phase == "TAPER":
            if self.weeks_left > 1.5:
                target *= 0.8
            elif self.weeks_left > 0.5:
                target *= 0.6
            else:
                target *= 0.4
        return max(target, 0.0)

    def determine_stage(self) -> int:
        lr = self.config.recent_long_km
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
        if stage == 3 and self.stage3_history >= 2:
            notes.append("Stage3 2회 이상 → 이번 주는 Stage2")
            stage = 2
        if stage == 4 and self.stage4_history >= 1:
            notes.append("Stage4 경험 있음 → Stage3 유지")
            stage = 3
        if self.phase == "TAPER":
            stage = min(stage, 2)
        return stage

    def decide_quality_count(self) -> int:
        if self.phase == "BASE":
            return 1 if self.goal_mode != "G1" else 0
        if self.phase == "BUILD":
            return 2 if self.goal_mode == "G3" else 1
        if self.phase == "PEAK":
            return 2
        if self.phase == "TAPER":
            return 1 if self.weeks_left > 1.5 else 0
        return 1

    def schedule_days(self, quality_count: int) -> Dict[int, str]:
        if self.weeks_left <= 0.5:
            return {0: "Easy", 1: "Strides", 2: "Rest", 3: "Easy", 4: "Rest", 5: "Rest", 6: "Long"}

        plan = {i: "Rest" for i in range(7)}
        run_days = min(self.weekly_frequency, 6)
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
        if self.weeks_left <= 0.5:
            quality_count = 0

        schedule = self.schedule_days(quality_count)
        plans: List[DayPlan] = []
        easy_sessions = sum(1 for v in schedule.values() if v == "Easy")
        remaining_easy_km = max(target_km - long_distance - quality_count * 12.0, 0.0)
        easy_default = remaining_easy_km / easy_sessions if easy_sessions else 0.0

        for idx in range(7):
            current_date = self.start_date + timedelta(days=idx)
            label = WEEKDAY_LABELS[current_date.weekday()]
            slot = schedule.get(idx, "Rest")
            if slot == "Long":
                plan = build_long_run_session(
                    current_date,
                    label,
                    stage,
                    long_distance,
                    self.paces[f"long_{stage}"],
                    self.goal_mode,
                )
            elif slot == "Quality":
                plan = self.build_point_session(current_date, label)
            elif slot == "Easy":
                plan = build_easy_session(current_date, label, max(easy_default, 6.0), "기본 Easy", self.paces["easy"])
            elif slot == "Strides":
                plan = build_strides_session(current_date, label, self.paces["easy"])
            else:
                plan = DayPlan(current_date, label, "Rest / Mobility", 0.0, "-", "Mobility & Stretch", "안전 회복")

            plans.append(plan)

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



def generate_week_plan(config: PlanConfig, *, start_date: Optional[date] = None) -> Dict[str, Any]:
    planner = Planner(config, start_date=start_date)
    result = planner.build_week()
    quality_sessions = sum(1 for plan in result.plans if plan.session_type.startswith('Quality'))
    long_run = next((plan for plan in result.plans if plan.session_type.startswith('Long')), None)
    long_distance = long_run.distance_km if long_run else 0.0
    long_stage = ''
    if long_run and 'Stage' in long_run.session_type:
        long_stage = long_run.session_type.split('Stage')[-1].strip(' )')
    summary = {
        'phase': result.phase,
        'goal_mode': result.goal_mode,
        'target_weekly_km': result.target_weekly_km,
        'planned_weekly_km': result.total_planned_km,
        'quality_sessions': quality_sessions,
        'long_run_distance': long_distance,
        'long_run_stage': long_stage,
    }
    notes = list(result.notes)
    recent_km = config.recent_weekly_km
    planned_km = result.total_planned_km
    if recent_km > 0:
        ratio = planned_km / recent_km
        if ratio >= 1.25:
            # 지난 주 대비 과도한 주간 거리 증가 시 경고 메모를 추가한다.
            notes.append("지난 주 대비 주간 거리가 25% 이상 증가했습니다. 피로도·통증을 점검하고 필요 시 거리를 줄여 주세요.")
    phase_focus = {
        'BASE': "BASE Phase: 에어로빅 베이스와 Easy 러닝 비율을 충분히 확보하는 주입니다. 페이스보다는 거리와 주간 리듬에 집중해 주세요.",
        'BUILD': "BUILD Phase: 품질 세션 후 회복일을 충분히 확보하면서, 롱런 후반 집중도를 점차 올리는 주입니다.",
        'PEAK': "PEAK Phase: 레이스 페이스 감각을 키우는 것이 핵심입니다. 롱런과 포인트 훈련에서 식이·보급·페이스 전략을 리허설해 보세요.",
        'TAPER': "TAPER Phase: 볼륨을 줄이고 회복을 극대화하는 구간입니다. 수면·영양·스트레스 관리를 우선시해 주세요.",
    }
    phase_note = phase_focus.get(result.phase)
    if phase_note:
        notes.append(phase_note)
    if quality_sessions == 0:
        notes.append("이번 주는 품질 세션 없이 회복 중심 주간입니다. Easy 페이스에서 부상 신호를 체크해 주세요.")
    elif quality_sessions >= 2:
        notes.append("품질 세션이 2회 이상인 주간입니다. 세션 사이 회복일의 수면·영양 관리에 특히 신경 써 주세요.")
    if long_stage in {'3', '4'} and long_distance >= 28.0:
        notes.append(f"이번 롱런은 Stage{long_stage} 단계로, 레이스 시뮬레이션에 가까운 강도입니다. 보급 계획과 페이스 전략을 미리 연습해 보세요.")
    days = [
        {
            'date': plan.date.isoformat(),
            'weekday': plan.weekday,
            'session_type': plan.session_type,
            'distance_km': plan.distance_km,
            'pace_range': plan.pace_range,
            'structure': plan.structure,
            'notes': plan.notes,
        }
        for plan in result.plans
    ]
    return {'summary': summary, 'days': days, 'notes': notes}


def generate_week_plan_v1_2(
    config: PlanConfig,
    *,
    start_date: Optional[date] = None,
    override_recent_weekly_km: Optional[float] = None,
) -> Dict[str, Any]:
    recent = config.recent_weekly_km
    if override_recent_weekly_km is not None and override_recent_weekly_km > 0:
        recent = override_recent_weekly_km
    config_override = replace(config, recent_weekly_km=recent)
    return generate_week_plan(config_override, start_date=start_date)


def generate_multi_week_plan_v1_2(
    base_config: PlanConfig,
    *,
    start_date: date,
    race_date: date,
    actual_weekly_km: Optional[List[float]] = None,
) -> Dict[str, Any]:
    if start_date > race_date:
        raise ValueError("start_date must be on or before race_date")
    actual_weekly_km = actual_weekly_km or []
    weeks: List[Dict[str, Any]] = []
    idx = 0
    current_start = start_date
    recent = base_config.recent_weekly_km
    while current_start <= race_date:
        current_end = min(current_start + timedelta(days=6), race_date)
        week_config = replace(base_config, recent_weekly_km=recent)
        week_plan = generate_week_plan(week_config, start_date=current_start)
        actual_this_week = actual_weekly_km[idx] if idx < len(actual_weekly_km) else None
        weeks.append(
            {
                'index': idx,
                'start_date': current_start,
                'end_date': current_end,
                'summary': week_plan['summary'],
                'days': week_plan['days'],
                'notes': week_plan['notes'],
                'recent_weekly_km_used': recent,
                'actual_weekly_km': actual_this_week,
            }
        )
        if actual_this_week is not None:
            recent = actual_this_week
        else:
            recent = week_plan['summary']['planned_weekly_km']
        current_start += timedelta(days=7)
        idx += 1
    config_snapshot = {
        'race_date': base_config.race_date,
        'start_date': start_date,
        'recent_weekly_km': base_config.recent_weekly_km,
        'recent_long_km': base_config.recent_long_km,
        'goal_marathon_time': base_config.goal_marathon_time,
    }
    return {'weeks': weeks, 'config_snapshot': config_snapshot}
