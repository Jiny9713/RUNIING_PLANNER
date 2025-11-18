from collections import Counter
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from planner_core_v1_2 import (
    PlanConfig,
    generate_multi_week_plan_v1_2,
    generate_week_plan_v1_2,
)


def _parse_time(raw: str) -> int:
    parts = raw.strip().split(":")
    if not parts or not all(part.isdigit() for part in parts):
        raise ValueError("Invalid time format")
    values = [int(p) for p in parts]
    if len(values) == 2:
        minutes, seconds = values
        hours = 0
    elif len(values) == 3:
        hours, minutes, seconds = values
    else:
        raise ValueError("Time must be MM:SS or HH:MM:SS")
    return hours * 3600 + minutes * 60 + seconds


def _seconds_to_hhmmss(value: float) -> str:
    total = int(round(value))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _time_to_pace(time_str: str) -> str:
    total_seconds = _parse_time(time_str)
    pace_seconds = total_seconds / 42.195
    minutes = int(pace_seconds // 60)
    seconds = int(round(pace_seconds % 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes:02d}:{seconds:02d}"


def _pace_to_time(pace_str: str) -> str:
    per_km_seconds = _parse_time(pace_str)
    marathon_seconds = per_km_seconds * 42.195
    return _seconds_to_hhmmss(marathon_seconds)


def _init_state() -> None:
    if "goal_time_v1_2" not in st.session_state:
        st.session_state.goal_time_v1_2 = "03:30:00"
    if "goal_pace_v1_2" not in st.session_state:
        st.session_state.goal_pace_v1_2 = _time_to_pace(st.session_state.goal_time_v1_2)
    if "pb_time_v1_2" not in st.session_state:
        st.session_state.pb_time_v1_2 = "03:40:00"
    if "pb_pace_v1_2" not in st.session_state:
        st.session_state.pb_pace_v1_2 = _time_to_pace(st.session_state.pb_time_v1_2)
    st.session_state.setdefault("_sync_goal_v1_2", False)
    st.session_state.setdefault("_sync_pb_v1_2", False)


def _sync_goal_from_time() -> None:
    if st.session_state._sync_goal_v1_2:
        return
    try:
        pace = _time_to_pace(st.session_state.goal_time_v1_2)
    except ValueError:
        return
    st.session_state._sync_goal_v1_2 = True
    st.session_state.goal_pace_v1_2 = pace
    st.session_state._sync_goal_v1_2 = False


def _sync_goal_from_pace() -> None:
    if st.session_state._sync_goal_v1_2:
        return
    try:
        time_str = _pace_to_time(st.session_state.goal_pace_v1_2)
    except ValueError:
        return
    st.session_state._sync_goal_v1_2 = True
    st.session_state.goal_time_v1_2 = time_str
    st.session_state._sync_goal_v1_2 = False


def _sync_pb_from_time() -> None:
    if st.session_state._sync_pb_v1_2:
        return
    try:
        pace = _time_to_pace(st.session_state.pb_time_v1_2)
    except ValueError:
        return
    st.session_state._sync_pb_v1_2 = True
    st.session_state.pb_pace_v1_2 = pace
    st.session_state._sync_pb_v1_2 = False


def _sync_pb_from_pace() -> None:
    if st.session_state._sync_pb_v1_2:
        return
    try:
        time_str = _pace_to_time(st.session_state.pb_pace_v1_2)
    except ValueError:
        return
    st.session_state._sync_pb_v1_2 = True
    st.session_state.pb_time_v1_2 = time_str
    st.session_state._sync_pb_v1_2 = False


def render_summary(summary: Dict[str, float]) -> None:
    st.subheader("주간 요약")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("목표 주간 거리", f"{summary['target_weekly_km']:.1f} km")
    col2.metric("계획 주간 거리", f"{summary['planned_weekly_km']:.1f} km")
    col3.metric("품질 세션 수", summary["quality_sessions"])
    long_stage = summary["long_run_stage"] or "-"
    col4.metric("롱런", f"{summary['long_run_distance']:.1f} km", long_stage)


def render_table(days: List[Dict[str, object]]) -> None:
    st.subheader("주간 일정")
    today_iso = date.today().isoformat()
    rows: List[Dict[str, object]] = []
    for day in days:
        label = f"{day['date']} ({day['weekday']})"
        if day["date"] == today_iso:
            label += " ⭐ 오늘"
        rows.append(
            {
                "날짜": label,
                "세션": day["session_type"],
                "거리(km)": f"{day['distance_km']:.1f}",
                "페이스": day["pace_range"],
                "메모": day["notes"],
            }
        )
    st.dataframe(rows, use_container_width=True)


def render_multi_week_banner(weeks: List[Dict[str, Any]], race_date: date) -> Optional[int]:
    if not weeks:
        return None
    total_weeks = len(weeks)
    counts = Counter(week["summary"]["phase"] for week in weeks)
    phase_order = ["BASE", "BUILD", "PEAK", "TAPER"]
    parts = [f"{name} {counts.get(name, 0)}주" for name in phase_order if counts.get(name, 0)]
    phase_text = " · ".join(parts) if parts else "단계 정보 없음"
    today = date.today()
    current_idx: Optional[int] = None
    for week in weeks:
        if week["start_date"] <= today <= week["end_date"]:
            current_idx = week["index"]
            break
    if current_idx is not None:
        st.markdown(
            f"총 {total_weeks}주 플랜 중 {current_idx + 1}주차 진행 중입니다.\n\n{phase_text} 구성을 따릅니다."
        )
    else:
        st.markdown(f"총 {total_weeks}주 플랜입니다.\n\n{phase_text} 구성을 따릅니다.")
    return current_idx


def render_km_chart(weeks: List[Dict[str, Any]]) -> None:
    if not weeks:
        return
    chart_rows = [
        {
            "주차": week["index"] + 1,
            "계획 km": week["summary"]["planned_weekly_km"],
            "실제 km": week["actual_weekly_km"],
        }
        for week in weeks
    ]
    chart_df = pd.DataFrame(chart_rows).set_index("주차")
    st.line_chart(chart_df, height=280, use_container_width=True)


def render_weeks_table(
    weeks: List[Dict[str, Any]],
    *,
    current_week_index: Optional[int],
    race_date: date,
) -> None:
    rows: List[Dict[str, object]] = []
    previous_planned: Optional[float] = None
    for week in weeks:
        summary = week["summary"]
        planned = summary["planned_weekly_km"]
        actual = week["actual_weekly_km"]
        tag = ""
        if week["start_date"] <= race_date <= week["end_date"]:
            tag = "RACE WEEK"
        elif summary["phase"] == "TAPER":
            tag = "TAPER"
        elif previous_planned is not None and planned < previous_planned * 0.85:
            tag = "CUTBACK"
        elif previous_planned is not None and planned >= previous_planned * 1.25:
            tag = "VOL↑ 25%"
        if current_week_index == week["index"]:
            tag = (tag + " ⭐ 현재 주").strip()
        week_label = f"{week['index'] + 1}주차"
        rows.append(
            {
                "주차": week_label,
                "시작일": week["start_date"].isoformat(),
                "Phase": summary["phase"],
                "목표 km": f"{summary['target_weekly_km']:.1f}",
                "계획 km": f"{planned:.1f}",
                "롱런": f"{summary['long_run_distance']:.1f}",
                "품질 세션": summary["quality_sessions"],
                "사용한 지난주 km": f"{week['recent_weekly_km_used']:.1f}",
                "실제 주간 km": "" if actual is None else f"{actual:.1f}",
                "비고": tag,
            }
        )
        previous_planned = planned
    st.dataframe(rows, use_container_width=True)


st.set_page_config(page_title="마라톤 주간 플래너 v1.2", layout="wide")
st.title("마라톤 주간 플래너 v1.2")
st.caption("Actual mileage & multi-week 시나리오 (실험 버전)")

_init_state()

with st.sidebar:
    st.header("입력 값")
    mode = st.radio("모드 선택", ("1주 플랜 (v1.2)", "멀티 주간 플랜 (v1.2)"))
    race_date = st.date_input("레이스 날짜", value=date(2026, 3, 15))
    start_date = st.date_input("플랜 시작일", value=date.today())
    recent_weekly_km = st.number_input("지난 주 실제 주간 거리 (km)", min_value=0.0, max_value=200.0, value=60.0, step=1.0)
    recent_long_km = st.number_input("최근 롱런 거리 (km)", min_value=10.0, max_value=45.0, value=26.0, step=1.0)

    reduction_reason = st.radio(
        "지난주 거리 상태",
        ["정상/감소 없음", "컷백·스케줄·날씨", "부상·질병"],
        index=0,
    )
    injury_flag = reduction_reason == "부상·질병"

    st.markdown("### 목표 기록")
    st.text_input("목표 마라톤 기록 (HH:MM:SS)", key="goal_time_v1_2", on_change=_sync_goal_from_time)
    st.text_input("목표 페이스 (MM:SS)", key="goal_pace_v1_2", on_change=_sync_goal_from_pace)

    st.markdown("### 마라톤 PB")
    st.text_input("마라톤 PB (HH:MM:SS)", key="pb_time_v1_2", on_change=_sync_pb_from_time)
    st.text_input("마라톤 PB 페이스 (MM:SS)", key="pb_pace_v1_2", on_change=_sync_pb_from_pace)

    completed_weeks = 0
    actual_weekly_entries: Optional[List[float]] = None
    ongoing_label = "진행 중 사이클 재조정 (실제 수행 반영)"
    new_cycle_label = "새 사이클 설계 (처음 플랜 생성)"
    multi_cycle_mode = new_cycle_label
    if mode == "멀티 주간 플랜 (v1.2)":
        multi_cycle_mode = st.radio(
            "멀티 주간 진행 옵션",
            (new_cycle_label, ongoing_label),
            index=0,
        )
        if multi_cycle_mode == ongoing_label:
            completed_weeks = st.slider(
                "이미 완료한 주차 수",
                min_value=0,
                max_value=24,
                value=0,
                step=1,
            )
            actual_weekly_entries = []
            for idx in range(completed_weeks):
                km = st.number_input(
                    f"{idx + 1}주차 실제 주간 거리 (km)",
                    min_value=0.0,
                    max_value=300.0,
                    step=1.0,
                    key=f"actual_week_input_{idx + 1}",
                )
                actual_weekly_entries.append(float(km))
        else:
            actual_weekly_entries = None

config = PlanConfig(
    race_date=race_date,
    recent_weekly_km=float(recent_weekly_km),
    recent_long_km=float(recent_long_km),
    goal_marathon_time=st.session_state.goal_time_v1_2.strip(),
    current_mp=st.session_state.pb_pace_v1_2.strip(),
    injury_flag=injury_flag,
)


if mode == "1주 플랜 (v1.2)":
    generate = st.button("1주 플랜 생성")
    if generate:
        try:
            plan = generate_week_plan_v1_2(config, start_date=start_date, override_recent_weekly_km=None)
        except ValueError as err:
            st.error(f"입력 값을 확인해 주세요: {err}")
        else:
            render_summary(plan["summary"])
            render_table(plan["days"])
            if plan["notes"]:
                st.markdown("**코치 메모**")
                for note in plan["notes"]:
                    st.write(f"- {note}")
    else:
        st.info("왼쪽 입력을 확인한 뒤 '1주 플랜 생성' 버튼을 눌러 주세요.")
else:
    generate_multi = st.button("멀티 주간 플랜 생성")
    if generate_multi:
        if race_date < start_date:
            st.error("레이스 날짜는 플랜 시작일 이후여야 합니다.")
        else:
            plan = generate_multi_week_plan_v1_2(
                config,
                start_date=start_date,
                race_date=race_date,
                actual_weekly_km=actual_weekly_entries,
            )
            weeks = plan["weeks"]
            if not weeks:
                st.warning("생성된 주차가 없습니다. 입력 값을 확인해 주세요.")
            else:
                st.subheader("사이클 개요")
                current_week_index = render_multi_week_banner(weeks, race_date)
                st.subheader("주간 계획 vs 실제 거리")
                render_km_chart(weeks)
                st.subheader("주차별 요약")
                render_weeks_table(
                    weeks,
                    current_week_index=current_week_index,
                    race_date=race_date,
                )
                options = [f"{week['index'] + 1}주차 ({week['start_date'].isoformat()})" for week in weeks]
                selected_label = st.selectbox("상세 확인 주차", options)
                selected_index = options.index(selected_label)
                selected_week = weeks[selected_index]
                st.markdown(f"### {selected_week['index'] + 1}주차 상세")
                render_summary(selected_week["summary"])
                render_table(selected_week["days"])
                actual_value = selected_week["actual_weekly_km"]
                actual_str = "-" if actual_value is None else f"{actual_value:.1f}"
                st.markdown(
                    f"- 사용한 지난 주 km: {selected_week['recent_weekly_km_used']:.1f} / 실제 주간 km: {actual_str}"
                )
                if selected_week["notes"]:
                    st.markdown("**코치 메모**")
                    for note in selected_week["notes"]:
                        st.write(f"- {note}")
    else:
        st.info("완료한 주차가 있다면 위 슬라이더와 입력란을 채우고 '멀티 주간 플랜 생성' 버튼을 눌러 주세요.")
