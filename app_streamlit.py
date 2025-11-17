from datetime import date, timedelta
from typing import Dict, List, Union

import streamlit as st

from planner_core import PlanConfig, generate_week_plan


st.set_page_config(page_title="마라톤 주간 훈련 플래너", layout="wide")
st.title("마라톤 주간 훈련 플래너")
st.caption("Coach.md 철학과 planner_v7 로직 기반 v1.0")

default_race = date.today() + timedelta(weeks=10)

with st.sidebar:
    st.header("입력 값")
    race_date = st.date_input("레이스 날짜", value=default_race)
    start_date = st.date_input("플랜 시작일", value=date.today())
    recent_weekly_km = st.number_input("최근 주간 거리 (km)", min_value=10.0, max_value=200.0, value=60.0, step=1.0)
    recent_long_km = st.number_input("최근 롱런 거리 (km)", min_value=10.0, max_value=45.0, value=26.0, step=1.0)
    goal_marathon_time = st.text_input("목표 마라톤 기록 (HH:MM:SS)", value="03:30:00")
    current_mp = st.text_input("현재 마라톤 페이스 (MM:SS)", value="05:10")
    recent_weekly_altitude = st.number_input("최근 주간 누적 고도 (m)", min_value=0.0, max_value=3000.0, value=600.0, step=10.0)
    fatigue_level = st.slider("현재 피로도 (0=상쾌, 10=소진)", min_value=0, max_value=10, value=3)
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
        config = PlanConfig(
            race_date=race_date,
            recent_weekly_km=float(recent_weekly_km),
            recent_long_km=float(recent_long_km),
            goal_marathon_time=goal_marathon_time.strip(),
            current_mp=current_mp.strip(),
            recent_weekly_altitude=float(recent_weekly_altitude),
            fatigue_level=int(fatigue_level),
        )
        plan = generate_week_plan(config, start_date=start_date)
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
    st.info("왼쪽 입력값을 채우고 '주간 플랜 생성' 버튼을 눌러주세요.")
