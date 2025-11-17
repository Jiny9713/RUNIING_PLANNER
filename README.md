# Running Planner v1.0

Streamlit 기반 마라톤 주간 훈련 플래너입니다. `planner_core.py`의 엔진은 Coach.md에 정리된 철학과 `planner_v7.py`의 로직을 그대로 따르며, `app_streamlit.py`는 이를 웹에서 손쉽게 확인할 수 있도록 구성한 UI입니다. **이 버전의 플래너는 안전 스위치를 자동 적용하지 않으며, 러너가 Coach.md(코치노트)를 참고해 수동으로 조정해야 합니다.**

## 폴더 구조
```
Running_Planner/
├── planner_core.py          # PlanConfig, Planner, generate_week_plan을 포함한 핵심 엔진
├── app_streamlit.py         # Streamlit UI (사이드바 입력 → 주간 요약/테이블)
├── tests/
│   └── test_planner_core.py # 시나리오 기반 기본 동작 테스트
├── Coach.md                 # 훈련 철학 및 안전 스위치 체크리스트
├── requirements.txt         # 최소 의존성 (streamlit, pytest)
├── AGENTS.md                # 작업 지침
├── legacy_versions/         # app.py, planner_v*.py 등 이전 버전 보관
└── README.md
```

## 실행 방법
Windows PowerShell 기준:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app_streamlit.py
```
브라우저가 열리면 사이드바에서 아래 항목을 입력한 뒤 **주간 플랜 생성** 버튼을 누르면 됩니다.

## 필요한 입력 (PlanConfig)
| 필드 | 설명 |
| --- | --- |
| `race_date` | 레이스 날짜 (`datetime.date`) |
| `recent_weekly_km` | 최근 주간 총 주행 거리 (km) |
| `recent_long_km` | 최근 롱런 거리 (km) |
| `goal_marathon_time` | 목표 마라톤 기록 (HH:MM 또는 HH:MM:SS) |
| `current_mp` | 현재 마라톤 페이스 (MM:SS) |

`generate_week_plan`은 위 값을 바탕으로 주간 목표 거리, 품질 세션 수, 롱런 단계/거리, 일자별 세션 정보를 담은 dict를 반환합니다. Streamlit UI도 동일한 엔진을 호출하므로 CLI·웹 어디서든 일관된 플랜을 확인할 수 있습니다.

## 예시 입력/출력
```
start_date          : 2025-01-06
race_date           : 2025-03-31
recent_weekly_km    : 60
recent_long_km      : 24
goal_marathon_time  : 03:30:00
current_mp          : 05:10
```
요약 결과(예):
```
Phase=BUILD, Goal Mode=G2
Target Weekly KM=66.0, Planned KM=65.3
Quality Sessions=1, Long Run=28.0 km (Stage 3)
```
일자별 세션은 `days` 리스트에 날짜/세션 타입/거리/페이스/메모 형태로 정리됩니다.

## 테스트
```bash
pytest
```
`tests/test_planner_core.py`에는 기본 플랜 생성, Goal Mode에 따른 품질 세션, TAPER 주 회복 등 4가지 시나리오가 포함되어 있습니다.

## 참고 사항
- 안전 스위치(피로도·고도·통증 등)는 코드에 자동 적용되어 있지 않으므로 반드시 Coach.md의 체크리스트를 참고해 수동으로 조정해 주세요.
- `legacy_versions/` 폴더에 과거 CLI 및 실험 버전을 보관하고 있으므로 필요 시 참고할 수 있습니다.***
