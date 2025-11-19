# Running Planner (Injury-Aware Default)

Streamlit 기반 마라톤 주간 훈련 플래너입니다. 최신 기본 엔진(`planner_core.py`)은 Coach.md 철학을 따르면서 `injury_flag`를 통한 **부상/질병 기반 주간 볼륨 휴리스틱**, 주간 경고 메모, 그리고 `generate_week_plan_v1_2` / `generate_multi_week_plan_v1_2` API를 포함합니다. 기본 UI(`app_streamlit.py`)는 1주 플랜과 멀티 주간 플랜을 모두 제공하며, 멀티 주간 모드에서는 표에서 직접 “실제 주간 km”를 수정해 재계산할 수 있습니다. 안전 스위치들은 여전히 자동 로직으로 적용되지 않으므로, 러너는 Coach.md의 체크리스트를 참고해 수동 보정을 해야 합니다.

## 폴더 구조
```
Running_Planner/
├── planner_core.py             # 기본 엔진 (injury-aware + v1.2 multi-week API)
├── planner_core_v1_0.py        # v1.0 엔진 (injury flag 없음)
├── planner_core_v1_1.py        # v1.0 엔진 기반 injury-aware 휴리스틱 스냅샷
├── planner_core_v1_2.py        # v1.2 엔진 보존본
├── app_streamlit.py            # 기본 Streamlit UI (1주/멀티 주간 모드 통합)
├── app_streamlit_v1_0.py       # v1.0 전용 UI
├── app_streamlit_v1_1.py       # planner_core_v1_1 전용 UI
├── app_streamlit_v1_2.py       # v1.2 실험 UI 보존본
├── tests/
│   ├── test_planner_core.py    # 기본 엔진 시나리오 + v1.2 멀티 주간 테스트
│   ├── test_planner_core_v1_0.py
│   ├── test_planner_core_v1_1.py
│   └── test_planner_core_v1_2.py
├── Coach.md                    # 훈련 철학 및 체크리스트
├── requirements.txt            # streamlit, pytest 등 최소 의존성
├── AGENTS.md                   # 작업 지침
├── legacy_versions/            # app.py, planner_v* 등 과거 버전 보관
└── README.md
```

## 실행 방법
Windows PowerShell 기준:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 기본 (injury-aware + v1.2 멀티 주간)
streamlit run app_streamlit.py

# 보존된 v1.0 (injury flag 없음)
streamlit run app_streamlit_v1_0.py

# v1.0 엔진 + injury-aware 휴리스틱 스냅샷
streamlit run app_streamlit_v1_1.py
```
브라우저가 열리면 사이드바 입력을 채운 뒤 **1주 플랜 생성** 버튼을 눌러 단일 주차 플랜을 확인하거나, **멀티 주간 플랜 생성** 버튼을 눌러 전체 사이클을 생성할 수 있습니다. 기본 UI에는 “지난주 거리 상태” 라디오가 추가되어 `injury_flag`를 설정할 수 있습니다.

## 필요한 입력 (PlanConfig)
| 필드 | 설명 |
| --- | --- |
| `race_date` | 레이스 날짜 (`datetime.date`) |
| `recent_weekly_km` | 최근 주간 총 주행 거리 (km) |
| `recent_long_km` | 최근 롱런 거리 (km) |
| `goal_marathon_time` | 목표 마라톤 기록 (HH:MM 또는 HH:MM:SS) |
| `current_mp` | 현재 마라톤 페이스 (MM:SS) |
| `injury_flag` | 지난주 감소 원인이 부상/질병인지 여부 (`app_streamlit.py`의 라디오로 설정) |

`generate_week_plan`은 위 값을 바탕으로 주간 목표 거리, 품질 세션 수, 롱런 단계/거리, 일자별 세션 정보를 담은 dict를 반환합니다. `generate_week_plan_v1_2`는 지난 주 실제 km override를 받을 수 있고, `generate_multi_week_plan_v1_2`는 실제 주간 km 리스트를 활용해 멀티 주간 플랜을 생성합니다. Streamlit UI도 동일한 엔진을 호출하므로 CLI·웹 어디서든 일관된 플랜을 확인할 수 있습니다.

## 예시 입력/출력
```
start_date          : 2025-01-06
race_date           : 2025-03-31
recent_weekly_km    : 40
recent_long_km      : 24
goal_marathon_time  : 03:30:00
current_mp          : 05:10
injury_flag         : True  (사이드바에서 "부상·질병" 선택)
```
요약 결과(예):
```
Phase=BASE, Goal Mode=G2
Target Weekly KM=44.0, Planned KM=46.0
Quality Sessions=1, Long Run=24.0 km (Stage 2)
```
예: 월요일 세션 → `Easy 4.0km @ 5:54~6:24/km (기본 Easy, 조정)`  
`notes` 필드를 통해 추가 코치 메모가 포함됩니다.

### 멀티 주간 플랜
1. 사이드바에서 레이스 날짜/플랜 시작일/최근 주간 km/롱런/목표 기록을 입력하고 **멀티 주간 플랜 생성**을 누릅니다.
2. 중앙의 “주차별 요약” 표에서 각 주차의 “실제 주간 km”를 직접 수정할 수 있습니다.
3. 수정 후 **“실제 주간 km로 플랜 업데이트”** 버튼을 누르면 전체 사이클이 실제 기록을 반영하도록 재계산됩니다.
4. 아래 차트와 상세 뷰에서 변경된 플랜을 즉시 확인할 수 있습니다.

## 테스트
```bash
pytest
```
`tests/test_planner_core.py`는 기본 엔진의 페이즈/Goal Mode/테이퍼 시나리오와 injury-aware 볼륨 휴리스틱을 검증합니다. `tests/test_planner_core_v1_0.py`와 `tests/test_planner_core_v1_1.py`는 각각 보존된 버전 전용 시나리오를 제공합니다.

## 참고 사항
- 안전 스위치(피로도·고도·통증 등)는 코드에 자동 적용되어 있지 않으므로 반드시 Coach.md의 체크리스트를 참고해 수동으로 조정해 주세요.
- `legacy_versions/` 폴더에는 과거 CLI 및 실험 버전을 보관하고 있으니 필요 시 참고할 수 있습니다.
