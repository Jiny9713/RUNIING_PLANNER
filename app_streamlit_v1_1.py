from datetime import date
from typing import Dict, List, Union

import streamlit as st

from planner_core_v1_1 import PlanConfigV11, generate_week_plan_v1_1


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
    if "goal_time_v1_1" not in st.session_state:
        st.session_state.goal_time_v1_1 = "03:30:00"
    if "goal_pace_v1_1" not in st.session_state:
        st.session_state.goal_pace_v1_1 = _time_to_pace(st.session_state.goal_time_v1_1)
    if "pb_time_v1_1" not in st.session_state:
        st.session_state.pb_time_v1_1 = "03:40:00"
    if "pb_pace_v1_1" not in st.session_state:
        st.session_state.pb_pace_v1_1 = _time_to_pace(st.session_state.pb_time_v1_1)
    st.session_state.setdefault("_sync_goal_v1_1", False)
    st.session_state.setdefault("_sync_pb_v1_1", False)


def _sync_goal_from_time() -> None:
    if st.session_state._sync_goal_v1_1:
        return
    try:
        pace = _time_to_pace(st.session_state.goal_time_v1_1)
    except ValueError:
        return
    st.session_state._sync_goal_v1_1 = True
    st.session_state.goal_pace_v1_1 = pace
    st.session_state._sync_goal_v1_1 = False


def _sync_goal_from_pace() -> None:
    if st.session_state._sync_goal_v1_1:
        return
    try:
        time_str = _pace_to_time(st.session_state.goal_pace_v1_1)
    except ValueError:
        return
    st.session_state._sync_goal_v1_1 = True
    st.session_state.goal_time_v1_1 = time_str
    st.session_state._sync_goal_v1_1 = False


def _sync_pb_from_time() -> None:
    if st.session_state._sync_pb_v1_1:
        return
    try:
        pace = _time_to_pace(st.session_state.pb_time_v1_1)
    except ValueError:
        return
    st.session_state._sync_pb_v1_1 = True
    st.session_state.pb_pace_v1_1 = pace
    st.session_state._sync_pb_v1_1 = False


def _sync_pb_from_pace() -> None:
    if st.session_state._sync_pb_v1_1:
        return
    try:
        time_str = _pace_to_time(st.session_state.pb_pace_v1_1)
    except ValueError:
        return
    st.session_state._sync_pb_v1_1 = True
    st.session_state.pb_time_v1_1 = time_str
    st.session_state._sync_pb_v1_1 = False


st.set_page_config(page_title="마라톤 주간 훈련 플래너 v1.1", layout="wide")
st.title("마라톤 주간 훈련 플래너 v1.1")
st.caption("Injury-aware volume heuristic (Coach.md 기반)")

_init_state()

with st.sidebar:
    st.header("입력 값")
    race_date = st.date_input("레이스 날짜", value=date(2026, 3, 15))
    start_date = st.date_input("플랜 시작일", value=date.today())
    recent_weekly_km = st.number_input("최근 주간 거리 (km)", min_value=10.0, max_value=200.0, value=60.0, step=1.0)
    recent_long_km = st.number_input("최근 롱런 거리 (km)", min_value=10.0, max_value=45.0, value=26.0, step=1.0)

    reduction_reason = st.radio(
        "지난주 거리 상태",
        ["정상/감소 없음", "컷백·스케줄·날씨", "부상·질병"],
        index=0,
    )
    injury_flag = reduction_reason == "부상·질병"

    st.markdown("### 목표 기록")
    st.text_input("목표 마라톤 기록 (HH:MM:SS)", key="goal_time_v1_1", on_change=_sync_goal_from_time)
    st.text_input("목표 페이스 (MM:SS)", key="goal_pace_v1_1", on_change=_sync_goal_from_pace)

    st.markdown("### 마라톤 PB")
    st.text_input("마라톤 PB (HH:MM:SS)", key="pb_time_v1_1", on_change=_sync_pb_from_time)
    st.text_input("마라톤 PB 페이스 (MM:SS)", key="pb_pace_v1_1", on_change=_sync_pb_from_pace)

    generate = st.button("주간 플랜 생성")


def render_summary(summary: Dict[str, Union[float, str]]) -> None:
    st.subheader("주간 요약")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("목표 주간 거리", f"{summary['target_weekly_km']:.1f} km")
    col2.metric("계획 주간 거리", f"{summary['planned_weekly_km']:.1f} km")
    col3.metric("품질 세션 수", summary["quality_sessions"])
    long_stage = summary["long_run_stage"] or "-"
    col4.metric("롱런", f"{summary['long_run_distance']:.1f} km", long_stage)


def render_table(days: List[Dict[str, object]]) -> None:
    st.subheader("주간 일정")
    rows = [
        {
            "날짜": f"{day['date']} ({day['weekday']})",
            "세션": day["session_type"],
            "거리(km)": f"{day['distance_km']:.1f}",
            "페이스": day["pace_range"],
            "메모": day["notes"],
        }
        for day in days
    ]
    st.dataframe(rows, use_container_width=True)


if generate:
    try:
        config = PlanConfigV11(
            race_date=race_date,
            recent_weekly_km=float(recent_weekly_km),
            recent_long_km=float(recent_long_km),
            goal_marathon_time=st.session_state.goal_time_v1_1.strip(),
            current_mp=st.session_state.pb_pace_v1_1.strip(),
            injury_flag=injury_flag,
        )
        plan = generate_week_plan_v1_1(config, start_date=start_date)
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
    st.info("왼쪽 입력값과 지난주 상황을 선택하고 '주간 플랜 생성' 버튼을 눌러주세요.")
