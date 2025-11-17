import streamlit as st
from planner_v7 import Planner, PlanConfig  # 실제 이름에 맞게 수정

st.set_page_config(page_title="마라톤 훈련 플래너", layout="wide")

st.title("🏃‍♀️ 코치 v7 기반 마라톤 훈련 플래너")
st.caption("목표 기록과 최근 훈련 상태를 기반으로 이번 주 훈련 계획을 자동 생성합니다.")

# --- 1) 입력 폼 영역 ---
st.sidebar.header("입력값 설정")

col1, col2 = st.sidebar.columns(2)
with col1:
    mp_target_str = st.text_input("목표 MP (예: 4:30)", value="4:30")
with col2:
    mp_current_str = st.text_input("현재 MP 추정 (예: 4:40)", value="4:40")

recent_weekly_km = st.sidebar.slider("최근 주간 거리 (km)", 10, 140, 80)
recent_long_run = st.sidebar.slider("최근 롱런 거리 (km)", 10, 42, 28)
weekly_freq = st.sidebar.slider("주당 러닝 횟수", 2, 7, 5)
fatigue = st.sidebar.slider("현재 피로도 (0=상쾌, 10=완전 피곤)", 0, 10, 3)
weeks_left = st.sidebar.slider("레이스까지 남은 주", 0, 24, 8)
weekly_altitude = st.sidebar.slider("최근 주간 고도 합 (m)", 0, 2000, 600)

pain_flag = st.sidebar.checkbox("최근 48시간 내 통증/부상 있음", value=False)

st.sidebar.markdown("---")
generate = st.sidebar.button("이번 주 훈련 계획 생성")


# --- 2) 헬퍼: '4:30' 문자열을 페이스(초/킬로)로 변환할 함수 예시 ---
def pace_str_to_float(pace_str: str) -> float:
    # "4:30" → 4*60+30 → 270초 → 270/60=4.5 로 km당 분 단위 float
    try:
        minute, second = pace_str.split(":")
        total_sec = int(minute) * 60 + int(second)
        return total_sec / 60.0
    except Exception:
        return 0.0  # 아주 단순 예외 처리


# --- 3) 버튼 눌렀을 때 계획 생성 ---
if generate:
    # 3-1) 입력값 가공
    mp_target = pace_str_to_float(mp_target_str)
    mp_current = pace_str_to_float(mp_current_str)

    if mp_target == 0 or mp_current == 0:
        st.error("목표/현재 페이스를 '분:초' 형식으로 정확히 입력해 주세요. 예: 4:30")
    else:
        # 3-2) PlanConfig 생성 (실제 필드명에 맞게 수정 필요)
        config = PlanConfig(
            recent_weekly_km=recent_weekly_km,
            recent_long_run=recent_long_run,
            weekly_frequency=weekly_freq,
            fatigue_level=fatigue,
            mp_target=mp_target,
            mp_current=mp_current,
            weeks_left=weeks_left,
            weekly_altitude_sum=weekly_altitude,
            pain_flag=pain_flag,
        )

        planner = Planner(config)
        week_plan = planner.build_week()  # 예: List[DayPlan] 반환

        st.subheader("📅 이번 주 훈련 계획")

        # --- 3-3) 표 형태로 정리해서 출력 ---
        rows = []
        for day in week_plan:
            # DayPlan에 있는 실제 필드명에 맞게 수정
            rows.append({
                "요일": day.day_name,
                "유형": day.session_type,
                "거리(km)": day.distance_km,
                "페이스": day.pace_desc,
                "구성": day.structure,
                "비고": day.notes,
            })

        import pandas as pd
        df = pd.DataFrame(rows)

        st.dataframe(df, use_container_width=True)

        # --- 3-4) 각 요일별 카드형 출력 (선택사항) ---
        for day in week_plan:
            with st.expander(f"{day.day_name} – {day.session_type} / {day.distance_km} km"):
                st.write(f"**페이스:** {getattr(day, 'pace_desc', '')}")
                st.write(f"**구성:** {getattr(day, 'structure', '')}")
                if getattr(day, "notes", ""):
                    st.info(day.notes)
else:
    st.info("왼쪽 사이드바에 값을 입력하고 **'이번 주 훈련 계획 생성'** 버튼을 눌러 주세요.")
