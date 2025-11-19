from collections import Counter
from datetime import date
from typing import Any, Dict, List, Optional

import altair as alt
import pandas as pd
import streamlit as st

from planner_core import (
    PlanConfig,
    generate_multi_week_plan_v1_2,
    generate_week_plan_v1_2,
)

WEEKDAY_KR_ORDER = ["월", "화", "수", "목", "금", "토", "일"]


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


def _pace_to_seconds(pace_str: str) -> Optional[float]:
    try:
        return float(_parse_time(pace_str))
    except ValueError:
        return None


def _seconds_to_pace_label(value: Optional[float]) -> str:
    if value is None:
        return "-"
    minutes = int(value // 60)
    seconds = int(round(value % 60))
    return f"{minutes:02d}:{seconds:02d}"


def _derive_goal_mode(goal_pace: Optional[float], current_mp: Optional[float]) -> str:
    if goal_pace is None or current_mp is None:
        return "G2"
    delta = current_mp - goal_pace
    if delta <= 0:
        return "G1"
    if delta <= 20:
        return "G2"
    return "G3"


def _build_pace_zones(goal_mode: str, mp_seconds: Optional[float]) -> Dict[str, str]:
    if mp_seconds is None:
        return {"MP": "-", "E": "-", "L": "-", "T": "-", "I": "-"}
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
    offsets = easy_offsets.get(goal_mode, (55, 85))
    long_offset = long_offsets[2]
    tempo = (-25, -15)
    interval = (-65, -40)
    zones = {
        "MP": f"{_seconds_to_pace_label(mp_seconds)}",
        "E": f"{_seconds_to_pace_label(mp_seconds + offsets[0])} ~ {_seconds_to_pace_label(mp_seconds + offsets[1])}",
        "L": f"{_seconds_to_pace_label(mp_seconds + long_offset[0])} ~ {_seconds_to_pace_label(mp_seconds + long_offset[1])}",
        "T": f"{_seconds_to_pace_label(mp_seconds + tempo[0])} ~ {_seconds_to_pace_label(mp_seconds + tempo[1])}",
        "I": f"{_seconds_to_pace_label(mp_seconds + interval[0])} ~ {_seconds_to_pace_label(mp_seconds + interval[1])}",
    }
    return zones


def render_pace_overview(goal_time: str, goal_pace: str, current_mp: str) -> None:
    st.subheader("목표 페이스 & 훈련 페이스 요약")
    mp_seconds = _pace_to_seconds(goal_pace)
    current_seconds = _pace_to_seconds(current_mp)
    goal_mode = _derive_goal_mode(mp_seconds, current_seconds)
    zones = _build_pace_zones(goal_mode, mp_seconds)
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(
            f"- 목표 기록: **{goal_time}**\n"
            f"- 목표 마라톤 페이스(MP): **{zones['MP']} /km**\n"
            f"- Goal Mode: **{goal_mode}**"
        )
    with col2:
        st.markdown(
            "훈련 페이스 가이드:\n"
            f"- Easy (E): {zones['E']} — 대화 가능한 호흡 유지\n"
            f"- Long (L): {zones['L']} — 초반 여유, 후반 집중\n"
            f"- Tempo (T): {zones['T']} — 30~40분간 지속 가능한 강도\n"
            f"- Interval (I): {zones['I']} — 800m~1km 반복 + 조깅 휴식"
        )


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


def render_detail_summary(summary: Dict[str, float]) -> None:
    st.subheader("주간 요약")
    col1, col2 = st.columns(2)
    col1.metric("목표 주간 거리", f"{summary['planned_weekly_km']:.1f} km")
    long_stage = summary["long_run_stage"] or "-"
    col2.metric("롱런", f"{summary['long_run_distance']:.1f} km", long_stage)


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


def render_training_plan_overview(weeks: List[Dict[str, Any]], race_date: date) -> Optional[int]:
    if not weeks:
        return None
    total_weeks = len(weeks)
    today = date.today()
    current_idx: Optional[int] = None
    for week in weeks:
        if week["start_date"] <= today <= week["end_date"]:
            current_idx = week["index"]
            break
    if current_idx is not None:
        progress = f"총 {total_weeks}주 플랜 중 {current_idx + 1}주차 진행 중입니다."
    elif today < weeks[0]["start_date"]:
        progress = f"총 {total_weeks}주 플랜 (아직 시작 전)입니다."
    else:
        progress = f"총 {total_weeks}주 플랜을 모두 완료했습니다."
    st.markdown(f"**훈련 기간**: {progress}")

    long_counter: Counter[str] = Counter()
    quality_counter: Counter[str] = Counter()
    for week in weeks:
        for day in week.get("days", []):
            weekday = day.get("weekday")
            if not weekday:
                continue
            session_type = day.get("session_type", "")
            if "Long Run" in session_type:
                long_counter[weekday] += 1
            elif session_type.startswith("Quality"):
                quality_counter[weekday] += 1

    def top_weekdays(counter: Counter[str], max_items: int = 2) -> List[str]:
        if not counter:
            return []
        items = list(counter.items())
        items.sort(key=lambda x: (-x[1], WEEKDAY_KR_ORDER.index(x[0]) if x[0] in WEEKDAY_KR_ORDER else 99))
        return [name for name, _ in items[:max_items]]

    def format_days(days: List[str]) -> str:
        if not days:
            return ""
        if len(days) == 1:
            return days[0]
        return "·".join(days)

    long_days = top_weekdays(long_counter)
    quality_days = top_weekdays(quality_counter)
    if quality_days or long_days:
        quality_str = format_days(quality_days)
        long_str = format_days(long_days)
        if quality_days and long_days:
            st.markdown(
                f"**훈련요일 패턴(실제 플랜 기준)**: {quality_str}에 품질훈련, {long_str}에 롱런이 가장 자주 배치됩니다. "
                "그 외 요일은 이지런/회복 조깅 위주로 구성되어 있습니다. 실제 일정에 맞게 요일을 조정해 주세요."
            )
        elif long_days:
            st.markdown(
                f"**훈련요일 패턴(실제 플랜 기준)**: {long_str}에 롱런이 가장 자주 배치됩니다. "
                "나머지 요일은 품질/이지런과 회복 조깅으로 구성되어 있습니다."
            )
        elif quality_days:
            st.markdown(
                f"**훈련요일 패턴(실제 플랜 기준)**: {quality_str}에 품질훈련이 가장 자주 배치됩니다. "
                "롱런과 이지런/회복 조깅은 나머지 요일에 분산되어 있습니다."
            )
    else:
        st.markdown(
            "**훈련요일 안내**: 주중에는 이지런·품질훈련, 주말에는 롱런·회복 조깅을 배치하는 것을 기본 템플릿으로 삼았습니다. "
            "실제 일정에 맞게 자유롭게 조정해 주세요."
        )

    taper_weeks = [week["index"] for week in weeks if week["summary"]["phase"] == "TAPER"]
    if taper_weeks:
        st.markdown(
            f"**테이퍼**: {taper_weeks[0] + 1}주차 ~ {taper_weeks[-1] + 1}주차에 걸쳐 주간 볼륨을 점진적으로 감소합니다."
        )
    race_week = next((week for week in weeks if week["start_date"] <= race_date <= week["end_date"]), None)
    if race_week:
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        race_weekday = weekday_names[race_date.weekday()]
        st.markdown(
            f"**레이스 가정**: {race_week['index'] + 1}주차 {race_weekday}요일에 레이스를 치르는 것으로 설계했습니다."
        )

    counts = Counter(week["summary"]["phase"] for week in weeks)
    phase_map = {
        "BASE": "적응 + 기본기 다지기",
        "BUILD": "본격 빌드업 (롱런·템포·인터벌 강화)",
        "PEAK": "피크 주간 (최고 주간 볼륨 + MP 집중)",
        "TAPER": "테이퍼 & 레이스 준비 (볼륨 감소 + MP 감각 유지)",
    }
    segments: List[str] = []
    start = weeks[0]["index"]
    current_phase = weeks[0]["summary"]["phase"]
    for week in weeks[1:]:
        phase = week["summary"]["phase"]
        if phase != current_phase:
            end = week["index"] - 1
            segments.append(f"{start + 1}~{end + 1}주차: {phase_map.get(current_phase, current_phase)}")
            start = week["index"]
            current_phase = phase
    segments.append(f"{start + 1}~{weeks[-1]['index'] + 1}주차: {phase_map.get(current_phase, current_phase)}")
    st.markdown("**단계별 내러티브**")
    for sentence in segments:
        st.markdown(f"- {sentence}")
    return current_idx


def render_km_chart(weeks: List[Dict[str, Any]]) -> None:
    if not weeks:
        return
    chart_rows = [
        {
            "주차": week["index"] + 1,
            "유형": "계획 km",
            "거리": week["summary"]["planned_weekly_km"],
        }
        for week in weeks
    ]
    chart_rows += [
        {
            "주차": week["index"] + 1,
            "유형": "실제 km",
            "거리": week["actual_weekly_km"],
        }
        for week in weeks
    ]
    chart_df = pd.DataFrame(chart_rows)
    chart_df["거리"] = chart_df["거리"].astype(float)
    chart = (
        alt.Chart(chart_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("주차:Q", axis=alt.Axis(title="주차")),
            y=alt.Y("거리:Q", axis=alt.Axis(title="km")),
            color=alt.Color(
                "유형:N",
                scale=alt.Scale(domain=["계획 km", "실제 km"], range=["#1f77b4", "#ff7f0e"]),
                legend=alt.Legend(title=""),
            ),
            tooltip=["주차", "유형", alt.Tooltip("거리:Q", format=".1f")],
        )
        .properties(height=280)
    )
    st.altair_chart(chart, use_container_width=True)


st.set_page_config(page_title="마라톤 주간 플래너 v1.2", layout="wide")
st.title("마라톤 주간 플래너 v1.2")
st.caption("Actual mileage & multi-week 시나리오 (실험 버전)")

_init_state()
st.session_state.setdefault("multi_plan_v1_2", None)
st.session_state.setdefault("multi_config_v1_2", None)
st.session_state.setdefault("multi_start_date_v1_2", None)
st.session_state.setdefault("multi_race_date_v1_2", None)

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

    weekly_days = st.slider(
        "주간 훈련 일수",
        min_value=2,
        max_value=7,
        value=5,
        step=1,
    )
    if weekly_days >= 7:
        st.warning("주 7일 훈련은 과훈련·부상 위험이 높습니다. 강도를 낮추고 회복 관리를 최우선으로 해 주세요.")
    elif weekly_days == 6:
        st.info("주 6일 훈련은 높은 목표를 위한 선택입니다. 최소 1일 이상 완전 휴식일을 확보해 주세요.")
    elif weekly_days == 5:
        st.info("주 5일 훈련은 체계적인 기록 향상에 적합합니다. 휴식일 2일로 회복 밸런스를 유지하세요.")
    elif weekly_days == 4:
        st.info("주 4일 훈련은 직장인 기준으로 가장 균형 잡힌 선택입니다. 품질·롱런·이지런을 균형 있게 배치합니다.")
    elif weekly_days == 3:
        st.info("주 3일 훈련은 최소 조건입니다. 롱런 1회 + 품질 1회 + 이지런 1회 구성을 권장합니다.")
    else:
        st.warning("주 2일 이하 훈련은 마라톤 준비로는 부족합니다. 최소 주 3일 이상으로 설정해 주세요.")
    effective_weekly_days = max(3, weekly_days)


config = PlanConfig(
    race_date=race_date,
    recent_weekly_km=float(recent_weekly_km),
    recent_long_km=float(recent_long_km),
    goal_marathon_time=st.session_state.goal_time_v1_2.strip(),
    current_mp=st.session_state.pb_pace_v1_2.strip(),
    injury_flag=injury_flag,
    weekly_training_days=effective_weekly_days,
)

render_pace_overview(
    st.session_state.goal_time_v1_2.strip(),
    st.session_state.goal_pace_v1_2.strip(),
    st.session_state.pb_pace_v1_2.strip(),
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
    col_gen, col_reset = st.columns([2, 1])
    with col_gen:
        generate_multi = st.button("멀티 주간 플랜 생성")
    with col_reset:
        if st.button("현재 멀티 플랜 초기화", key="reset_multi_plan_v1_2"):
            st.session_state["multi_plan_v1_2"] = None
            st.session_state["multi_config_v1_2"] = None
            st.session_state["multi_start_date_v1_2"] = None
            st.session_state["multi_race_date_v1_2"] = None
            st.success("저장된 멀티 주간 플랜을 초기화했습니다.")

    if generate_multi:
        if race_date < start_date:
            st.error("레이스 날짜는 플랜 시작일 이후여야 합니다.")
            st.session_state["multi_plan_v1_2"] = None
            st.session_state["multi_config_v1_2"] = None
            st.session_state["multi_start_date_v1_2"] = None
            st.session_state["multi_race_date_v1_2"] = None
        else:
            try:
                plan = generate_multi_week_plan_v1_2(
                    config,
                    start_date=start_date,
                    race_date=race_date,
                    actual_weekly_km=None,
                )
            except ValueError as err:
                st.error(f"플랜 생성 중 오류가 발생했습니다: {err}")
                st.session_state["multi_plan_v1_2"] = None
                st.session_state["multi_config_v1_2"] = None
                st.session_state["multi_start_date_v1_2"] = None
                st.session_state["multi_race_date_v1_2"] = None
            else:
                st.session_state["multi_config_v1_2"] = config
                st.session_state["multi_start_date_v1_2"] = start_date
                st.session_state["multi_race_date_v1_2"] = race_date
                st.session_state["multi_plan_v1_2"] = plan

    plan_in_state = st.session_state.get("multi_plan_v1_2")
    base_config = st.session_state.get("multi_config_v1_2")
    stored_start = st.session_state.get("multi_start_date_v1_2")
    stored_race = st.session_state.get("multi_race_date_v1_2")

    if plan_in_state and plan_in_state.get("weeks"):
        table_race_date = stored_race or race_date
        weeks_for_editor = plan_in_state["weeks"]
        table_rows: List[Dict[str, Any]] = []
        previous_planned: Optional[float] = None
        today = date.today()
        for week in weeks_for_editor:
            summary = week["summary"]
            planned = summary["planned_weekly_km"]
            actual = week["actual_weekly_km"]
            tag = ""
            if week["start_date"] <= table_race_date <= week["end_date"]:
                tag = "RACE WEEK"
            elif summary["phase"] == "TAPER":
                tag = "TAPER"
            elif previous_planned is not None and planned < previous_planned * 0.85:
                tag = "CUTBACK"
            elif previous_planned is not None and planned >= previous_planned * 1.25:
                tag = "VOL↑ 25%"
            if week["start_date"] <= today <= week["end_date"]:
                tag = (tag + " ⭐ 현재 주").strip()
            table_rows.append(
                {
                    "주차": week["index"] + 1,
                    "시작일": week["start_date"].isoformat(),
                    "Phase": summary["phase"],
                    "목표 주간 km": planned,
                    "롱런 km": summary["long_run_distance"],
                    "사용한 지난주 km": week["recent_weekly_km_used"],
                    "실제 주간 km": actual,
                    "비고": tag,
                }
            )
            previous_planned = planned

        table_df = pd.DataFrame(table_rows)
        header_col, btn_col = st.columns([3, 1])
        with header_col:
            st.subheader("주차별 요약")
        with btn_col:
            update_clicked = st.button("실제 주간 km로 플랜 업데이트", key="update_multi_plan_v1_3")
        column_config = {
            "주차": st.column_config.NumberColumn("주차", disabled=True),
            "시작일": st.column_config.TextColumn("시작일", disabled=True),
            "Phase": st.column_config.TextColumn("Phase", disabled=True),
            "목표 주간 km": st.column_config.NumberColumn("목표 주간 km", disabled=True, format="%.1f"),
            "롱런 km": st.column_config.NumberColumn("롱런 km", disabled=True, format="%.1f"),
            "사용한 지난주 km": st.column_config.NumberColumn("사용한 지난주 km", disabled=True, format="%.1f"),
            "실제 주간 km": st.column_config.NumberColumn("실제 주간 km", format="%.1f"),
            "비고": st.column_config.TextColumn("비고", disabled=True),
        }
        edited_df = st.data_editor(
            table_df,
            key="multi_week_table_v1_2",
            hide_index=True,
            num_rows="fixed",
            use_container_width=True,
            column_config=column_config,
        )
        plan = plan_in_state
        if update_clicked:
            actual_values: List[Optional[float]] = []
            if "실제 주간 km" in edited_df.columns:
                for value in edited_df["실제 주간 km"].tolist():
                    if value is None or pd.isna(value):
                        actual_values.append(None)
                    else:
                        actual_values.append(float(value))
            else:
                actual_values = [None] * len(weeks_for_editor)

            if base_config and stored_start and stored_race:
                try:
                    updated_plan = generate_multi_week_plan_v1_2(
                        base_config,
                        start_date=stored_start,
                        race_date=stored_race,
                        actual_weekly_km=actual_values,
                    )
                except ValueError as err:
                    st.error(f"플랜 업데이트 중 오류가 발생했습니다: {err}")
                else:
                    plan = updated_plan
                    st.session_state["multi_plan_v1_2"] = updated_plan
            else:
                st.warning("먼저 멀티 주간 플랜을 생성한 뒤에 실제 주간 km를 업데이트할 수 있습니다.")

        weeks = plan["weeks"]
        snapshot = plan.get("config_snapshot", {})
        snapshot_race = snapshot.get("race_date", stored_race or race_date)
        snapshot_start = snapshot.get("start_date", stored_start or start_date)
        snapshot_recent = snapshot.get("recent_weekly_km", recent_weekly_km)
        snapshot_long = snapshot.get("recent_long_km", recent_long_km)
        snapshot_goal = snapshot.get("goal_marathon_time", st.session_state.goal_time_v1_2.strip())
        st.caption(
            "이 플랜은 생성 시점 기준: "
            f"레이스 {snapshot_race}, "
            f"플랜 시작일 {snapshot_start}, "
            f"지난 주 {snapshot_recent:.1f} km, "
            f"롱런 {snapshot_long:.1f} km, 목표 기록 {snapshot_goal} 기준입니다."
        )
        current_week_index = render_training_plan_overview(weeks, stored_race or race_date)
        st.subheader("주간 계획 vs 실제 거리")
        render_km_chart(weeks)
        options = [f"{week['index'] + 1}주차 ({week['start_date'].isoformat()})" for week in weeks]
        selected_label = st.selectbox("상세 확인 주차", options)
        selected_index = options.index(selected_label)
        selected_week = weeks[selected_index]
        st.markdown(f"### {selected_week['index'] + 1}주차 상세")
        render_detail_summary(selected_week["summary"])
        render_table(selected_week["days"])
        actual_value = selected_week["actual_weekly_km"]
        actual_str = "-" if actual_value is None else f"{actual_value:.1f}"
        st.markdown(f"- 사용한 지난 주 km: {selected_week['recent_weekly_km_used']:.1f} / 실제 주간 km: {actual_str}")
        if selected_week["notes"]:
            st.markdown("**코치 메모**")
            for note in selected_week["notes"]:
                st.write(f"- {note}")
    else:
        st.info("입력을 확인한 뒤 '멀티 주간 플랜 생성' 버튼을 눌러 주세요.")
