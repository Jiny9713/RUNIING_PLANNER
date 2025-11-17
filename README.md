# Running Planner v1.0

Coach.md의 코칭 철학과 `planner_v7.py`의 로직을 그대로 유지하면서, 배포 가능한 구조로 정리한 주간 마라톤 훈련 플래너입니다. `planner_core.py`가 모든 계산을 담당하고 `app_streamlit.py`가 Streamlit UI를 맡습니다. 최근 업데이트에서는 코치 지침에 따라 안전 스위치(피로도/고도 기반 제한)와 관련된 입력·로직을 모두 제거했습니다. **이 버전의 플래너는 안전스위치를 자동 적용하지 않으며, 러너가 Coach.md(코치노트)를 참고해 필요 시 수동으로 조정해야 합니다.**

## 디렉터리 개요
```
Running_Planner/
├── planner_core.py        # PlanConfig, Planner, generate_week_plan이 모여 있는 핵심 엔진
├── app_streamlit.py       # Streamlit 웹 앱 (사이드바 입력 → 주간 요약/테이블)
├── tests/
│   └── test_planner_core.py  # 시나리오 기반 기본 동작 검증
├── requirements.txt       # 최소 의존성 (streamlit, pytest)
├── Coach.md               # 코치 철학 및 가이드
├── planner_v*.py          # 기존 CLI 버전 (로직 레퍼런스)
└── README.md
```

### 핵심 구성
- **planner_core.py**
  - `PlanConfig`: 웹/테스트에서 공통으로 사용하는 설정 데이터클래스.
  - `Planner`: phase 판별, 주간 목표 거리 산출, 품질 세션/롱런 배치, 거리 밸런싱 등 모든 로직.
  - `generate_week_plan(config, start_date)`: 요약 정보와 일자별 세션을 dict 형태로 반환하여 UI나 다른 서비스에서 바로 활용 가능.
- **app_streamlit.py**
  - 사이드바 입력(레이스 날짜, 최근 주간 거리 등) → `generate_week_plan` 호출 → 주간 metric과 테이블 렌더링.
  - 코치 메모가 있을 경우 본문 하단에 bullet로 표시.
- **tests/test_planner_core.py**
  - 기본 시나리오, Goal Mode 조건, 레이스 직전 회복 주 등 주요 규칙을 검증.

## 실행 방법
Windows PowerShell 기준:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app_streamlit.py
```
브라우저가 열리면 사이드바 입력을 채우고 “주간 플랜 생성” 버튼을 누르면 됩니다.

## 테스트
```bash
pytest
```

## PlanConfig 입력 값
Streamlit 앱 또는 코드에서 `PlanConfig`를 만들 때는 아래 값만 제공하면 됩니다.

| 필드 | 설명 |
| --- | --- |
| `race_date` | 레이스 예정일 (`datetime.date`) |
| `recent_weekly_km` | 최근 1주 총 주행 거리 (km) |
| `recent_long_km` | 최근 롱런 거리 (km) |
| `goal_marathon_time` | 목표 마라톤 기록 (HH:MM 또는 HH:MM:SS) |
| `current_mp` | 현재 예상 마라톤 페이스 (MM:SS) |

`generate_week_plan`은 위 입력과 Coach 철학을 바탕으로 주간 목표/계획 거리, 품질 세션 수, 롱런 거리/Stage, 일자별 세션 정보를 포함한 dict를 반환합니다. Streamlit UI 역시 동일한 엔진을 호출하므로 CLI·웹 어디서든 일관된 플랜을 확인할 수 있습니다.
