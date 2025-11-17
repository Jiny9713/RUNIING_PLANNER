# Running Planner v1.0

Coach.md의 훈련 철학과 `planner_v7.py` 로직을 그대로 옮겨온 주간 마라톤 훈련 플래너입니다. `planner_core.py`가 엔진 역할을 하고, `app_streamlit.py`를 통해 간단히 웹에서 입력하고 결과를 확인할 수 있습니다.

## 구성
- `planner_core.py` – `PlanConfig` 및 `generate_week_plan`을 제공하는 핵심 모듈
- `app_streamlit.py` – Streamlit 기반 UI, 사이드바 입력 → 주간 요약/테이블 출력
- `tests/` – 시나리오 기반 기본 동작 테스트
- `planner_v*.py` – 참고용 기존 CLI 버전 (로직 출처)

## 로컬 실행
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
streamlit run app_streamlit.py
```

## 테스트
```bash
pytest
```

## 입력 값
앱 사이드바 또는 코드에서 `PlanConfig`를 만들 때 다음을 제공하면 됩니다.
- `race_date` : 레이스 예정일
- `recent_weekly_km` : 최근 1주 총 주행 거리
- `recent_long_km` : 최근 롱런 거리
- `goal_marathon_time` : 목표 기록 (HH:MM 또는 HH:MM:SS)
- `current_mp` : 현재 예상 마라톤 페이스 (MM:SS)
- `recent_weekly_altitude` : 최근 주간 누적 고도
- `fatigue_level` : 현재 피로도 (0~10)

이 값을 기반으로 `generate_week_plan`이 주간 거리, 품질 세션 수, 롱런 스테이지가 반영된 플랜을 반환합니다.
