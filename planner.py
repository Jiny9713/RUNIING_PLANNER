#!/usr/bin/env python3
"""
지니님 개인 러닝 플래너 v2 (CLI 버전)

- 코치 철학 v3.1 기반
- 입력: 레이스 날짜, 최근 주간 볼륨, 최근 롱런, 피로도 등
- 출력: 이번 주 요일별 훈련 계획 텍스트
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional


# -----------------------------
# 데이터 구조
# -----------------------------

@dataclass
class DayPlan:
    date: date
    label: str          # Mon / Tue ...
    type: str           # "EASY" / "QUALITY" / "LONG" / "REST"
    description: str    # 간단 설명
    planned_km: float   # 예상 거리


# -----------------------------
# 유틸 함수
# -----------------------------

def parse_date(s: str) -> date:
    """YYYY-MM-DD 문자열을 date로 변환"""
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def start_of_week(d: date) -> date:
    """월요일 기준 주 시작일"""
    return d - timedelta(days=d.weekday())


def round_km(x: float) -> float:
    """킬로 수소점 한 자리 반올림"""
    return round(x, 1)


# -----------------------------
# 1. Phase 결정
# -----------------------------

def determine_phase(today: date, race_date: date) -> str:
    days_left = (race_date - today).days
    weeks_left = days_left / 7.0

    if weeks_left >= 10:
        return "BASE"
    elif 6 <= weeks_left < 10:
        return "BUILD"
    elif 3 <= weeks_left < 6:
        return "PEAK"
    else:
        return "TAPER"


# -----------------------------
# 2. 목표 주간 볼륨 계산
# -----------------------------

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
    else:  # TAPER
        # weeks_left 는 0~3 범위
        if weeks_left > 1.5:      # 대략 -2주
            target = recent_weekly_km * 0.8
        elif weeks_left > 0.5:    # 대략 -1주
            target = recent_weekly_km * 0.6
        else:                     # 레이스 주
            target = recent_weekly_km * 0.4
        # 너무 낮게 떨어지는 것 방지용
        target = max(target, 25.0)

    return round_km(target)


# -----------------------------
# 3. 롱런 거리 결정
# -----------------------------

def select_long_run_distance(
    phase: str,
    weeks_left: float,
    recent_long_run: float,
    peak_long_done: bool,
    stage3_count: int,
) -> float:
    """
    코치 철학 v3.1 롱런 단계 로직을 간단화해서 반영
    """
    # TAPER 구간: 롱런 축소 또는 생략
    if phase == "TAPER":
        if weeks_left > 1.5:  # -2주
            # 옵션: 0 또는 20~22km -> 여기서는 21km로
            return 21.0
        elif weeks_left > 0.5:  # -1주
            return 14.0
        else:  # 레이스 주
            return 10.0

    # BASE: Stage1~2
    if phase == "BASE":
        if recent_long_run < 18:
            return 18.0
        elif recent_long_run < 22:
            return 20.0
        elif recent_long_run < 24:
            return 22.0
        else:
            return 24.0

    # BUILD: Stage2~3
    if phase == "BUILD":
        if recent_long_run < 20:
            return 20.0
        elif recent_long_run < 22:
            return 22.0
        elif recent_long_run < 24:
            return 24.0
        elif recent_long_run < 26:
            # Stage3로 진입
            if stage3_count >= 2:
                return 24.0
            return 26.0
        else:
            # 이미 26 이상이면 유지 또는 소폭 감소
            return min(recent_long_run, 28.0)

    # PEAK: Stage3~4
    if phase == "PEAK":
        if not peak_long_done:
            # 단 한 번의 피크 롱런: 30~35 중간값으로 32km
            return 32.0
        else:
            # 피크 이후에는 Stage3 수준에서 유지/감소
            if recent_long_run >= 30:
                return 26.0
            elif recent_long_run >= 26:
                return recent_long_run
            else:
                return 24.0

    # 기본값 방어
    return max(18.0, recent_long_run)


# -----------------------------
# 4. 강도훈련(QUALITY) 횟수/유형 결정
# -----------------------------

def decide_quality_sessions(
    phase: str,
    fatigue_level: int,
    recent_long_run: float,
    target_weekly_km: float,
) -> int:
    """Return how many quality workouts fit current load."""
    if fatigue_level >= 7:
        return 0

    phase_allows_two = phase in {"BUILD", "PEAK"}
    mileage_supports_two = target_weekly_km >= 60 and fatigue_level <= 4
    long_run_supports_two = recent_long_run >= 24 and fatigue_level <= 3

    if phase_allows_two and (mileage_supports_two or long_run_supports_two):
        return 2

    if phase == "TAPER":
        return 1 if fatigue_level <= 5 else 0

    if phase == "BASE" and target_weekly_km < 45:
        return 1 if fatigue_level <= 5 else 0

    return 1


def quality_type_for_phase(phase: str) -> str:
    if phase == "BASE":
        return "업힐 + 가벼운 템포"
    elif phase == "BUILD":
        return "템포 또는 간단 인터벌"
    elif phase == "PEAK":
        return "마라톤 페이스 지속주"
    else:  # TAPER
        return "400~1000m 짧은 인터벌(스피드 유지)"


# -----------------------------
# 5. 주간 플랜 생성
# -----------------------------

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def generate_week_plan(
    today: date,
    race_date: date,
    recent_weekly_km: float,
    recent_long_run: float,
    weekly_frequency: int,
    fatigue_level: int,
    peak_long_done: bool = False,
    stage3_count: int = 0,
) -> List[DayPlan]:
    start = start_of_week(today)
    phase = determine_phase(today, race_date)
    days_left = (race_date - today).days
    weeks_left = days_left / 7.0

    target_weekly_km = compute_target_weekly_km(
        phase, recent_weekly_km, weeks_left
    )

    # 롱런 세팅
    long_run_km = select_long_run_distance(
        phase, weeks_left, recent_long_run, peak_long_done, stage3_count
    )

    # QUALITY 횟수
    quality_count = decide_quality_sessions(
        phase, fatigue_level, recent_long_run, target_weekly_km
    )
    quality_desc = quality_type_for_phase(phase)

    # 거칠게: Quality 한 번당 8~12km 정도로 가정 (여기선 10km)
    quality_km_each = 10.0 if quality_count > 0 else 0.0
    total_quality_km = quality_km_each * quality_count

    # 남는 거리 = Easy로 분배
    remaining_km = max(target_weekly_km - long_run_km - total_quality_km, 0.0)

    # 러닝 횟수: 롱런 1 + Quality(0~2) + Easy(N)
    run_days = max(weekly_frequency, 1)  # 사용자 입력을 제한된 범위 내에서 사용
    easy_sessions = max(run_days - 1 - quality_count, 0)

    easy_km_each = remaining_km / easy_sessions if easy_sessions > 0 else 0.0

    # 요일 배치: Quality 화/목, 롱런 일
    long_run_day_index = 6  # Sun
    quality_day_indices: List[int] = []
    if quality_count >= 1:
        quality_day_indices.append(1)  # Tue
    if quality_count == 2:
        quality_day_indices.append(3)  # Thu

    plans: List[DayPlan] = []

    easy_used = 0

    for i in range(7):
        d = start + timedelta(days=i)
        label = WEEKDAY_LABELS[i]

        if i == long_run_day_index:
            plan_type = "LONG"
            desc = f"롱런 {long_run_km:.1f}km (단계형 롱런)"
            km = long_run_km
        elif i in quality_day_indices:
            if quality_count > 0:
                plan_type = "QUALITY"
                desc = f"{quality_desc} ~{quality_km_each:.1f}km"
                km = quality_km_each
            else:
                plan_type = "EASY"
                desc = "Easy 조깅"
                km = easy_km_each
                easy_used += 1
        else:
            # 쉬는 날 또는 이지런
            if easy_used < easy_sessions:
                plan_type = "EASY"
                desc = "Easy 조깅"
                km = easy_km_each
                easy_used += 1
            else:
                plan_type = "REST"
                desc = "휴식 또는 아주 가벼운 걷기"
                km = 0.0

        plans.append(
            DayPlan(
                date=d,
                label=label,
                type=plan_type,
                description=desc,
                planned_km=round_km(km),
            )
        )

    return plans


# -----------------------------
# 6. CLI 인터페이스
# -----------------------------

def print_week_plan(plans: List[DayPlan], target_weekly_km: float):
    print("\n===== 이번 주 훈련 플랜 =====")
    total = 0.0
    for p in plans:
        date_str = p.date.strftime("%Y-%m-%d")
        print(
            f"{date_str} ({p.label}) | {p.type:7} | "
            f"{p.planned_km:4.1f} km | {p.description}"
        )
        total += p.planned_km

    print("----------------------------")
    print(f"합계: {total:.1f} km (목표 약 {target_weekly_km:.1f} km)")


def main():
    print("=== 지니님 개인 러닝 플래너 v2 (Python CLI) ===")

    today_str = input("오늘 날짜를 입력하세요 (YYYY-MM-DD, 엔터 시 오늘 기준): ").strip()
    if today_str:
        today = parse_date(today_str)
    else:
        today = date.today()

    race_str = input("A 레이스 날짜를 입력하세요 (YYYY-MM-DD): ").strip()
    race_date = parse_date(race_str)

    recent_weekly_km = float(input("최근 7일 총 거리(km): ").strip())
    recent_long_run = float(input("최근 가장 긴 롱런 거리(km): ").strip())
    weekly_freq = int(input("최근 7일 러닝 횟수(예: 4,5): ").strip())
    fatigue_level = int(input("현재 피로도 (0~10): ").strip())
    stage3_str = input("Stage3 문화 횟수를 알려주세요 (0~3, Enter=0): ").strip()
    try:
        stage3_count = int(stage3_str) if stage3_str else 0
    except ValueError:
        stage3_count = 0
    stage3_count = max(0, min(stage3_count, 3))
    peak_long_done_input = input("스테이지 3 후 킹 로드 (30km 이상)를 완료하셨나요? (y/N): ").strip().lower()
    peak_long_done = peak_long_done_input.startswith("y")

    # 입력 값을 통해 peak_long_done/Stage3 카운트를 사용
    plans = generate_week_plan(
        today=today,
        race_date=race_date,
        recent_weekly_km=recent_weekly_km,
        recent_long_run=recent_long_run,
        weekly_frequency=weekly_freq,
        fatigue_level=fatigue_level,
        peak_long_done=peak_long_done,
        stage3_count=stage3_count,
    )

    # target_weekly_km 재계산 (출력용)
    phase = determine_phase(today, race_date)
    weeks_left = (race_date - today).days / 7.0
    target = compute_target_weekly_km(phase, recent_weekly_km, weeks_left)

    print_week_plan(plans, target)


if __name__ == "__main__":
    main()
