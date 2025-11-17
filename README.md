# Running Planner CLI

러닝 플래너 CLI를 제공합니다. 기존 `planner.py` 로부터 시작하여, 버전별로 관리됩니다.

## 구성
- `planner.py` : 최초 제공된 v2 CLI. 간단한 입력(오늘 날짜, 대회 날짜, 최근 주/롱런, 주간 빈도, 피로도)만으로 계획을 생성합니다.
- `planner_v3.py` : 리팩토링된 v3 CLI. `PlanConfig`/`DayPlan` 데이터 클래스로 구조화했고, Stage3/피크 롱런 추정, 품질 세션 결정, 거리 분배 로직을 개선했습니다.
- `planner_v4.py` : v3 기반 보완 버전. 입력 주간 횟수를 그대로 반영하며, Stage3/피크 자동 추정 결과 안내, 거리 감축 우선순위 적용.
- `planner_v5.py` : 추가 보강 버전. BASE 품질 1회 제한, TAPER 주차별 품질 규칙, 레이스 주 롱런 완화, 피로도 기반 목표 감축, 롱런 히스토리 기반 Stage3 추정을 지원합니다.
- `planner_v6.py` : Coach 철학 v4를 완전히 반영한 목표 기록 기반·강도 자동 조정·안전 스위치 내장형 플래너. Goal Mode(G1/2/3), 페이스 산출, 롱런 Stage 구조, 포인트훈련 구성, 안전 스위치를 포함한 최신 버전입니다.

## 공통 입력 항목
1. 오늘 날짜 (빈 입력 시 `date.today()`)
2. 레이스 날짜 (필수)
3. 최근 1주 총 거리 (km)
4. 최근 롱런 거리 (km)
5. 주간 러닝 횟수 (횟수)
6. 현재 피로도 (0~10)

## 실행 방법
```bash
# v2 실행
python planner.py

# v3 실행
python planner_v3.py

# v4 실행
python planner_v4.py

# v5 실행
python planner_v5.py

# v6 실행
python planner_v6.py

```
