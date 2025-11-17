
# Agent instructions for this repo

## Overview

This repository contains a marathon training planner with:
- A core planning engine in `planner_core.py`
- A Streamlit web UI in `app_streamlit.py`
- Scenario-based tests in `tests/test_planner_core.py`
- A coaching philosophy document in `Coach.md`

The goal is to maintain and extend this system as a **stable, deployable web app** while keeping the training philosophy coherent and versioned.

---

## Stable vs Experimental surfaces

### Stable entry points (v1.0)

The following files define the current **stable v1.0 surface** and must remain usable:

- `planner_core.py`
  - Defines `PlanConfig` and `generate_week_plan`
- `app_streamlit.py`
  - Streamlit UI using the v1.0 engine
- `tests/test_planner_core.py`
  - Scenario tests for the v1.0 engine
- `Coach.md`
  - Training philosophy document
- `README.md`
  - Basic usage and project overview
- `requirements.txt`
  - Minimal dependencies

**Default rule:** do **not** introduce breaking changes to these files unless the user explicitly requests an in-place change.

### Experimental / new versions

When adding new features, alternative engines, or UI variants:

- Do **not** rewrite or delete the existing stable files.
- Create new versioned or experimental files, for example:
  - `planner_core_v1_1.py`
  - `app_streamlit_v1_1.py`
  - `tests/test_planner_core_v1_1.py`
- Or use a dedicated folder:
  - `experiments/engine_v1_1.py`
  - `v1_1/app_streamlit_v1_1.py`

At the top of each new file, include a short comment indicating:
- What it is based on (e.g. “based on `planner_core.py` v1.0”)
- What changed (e.g. “adds HR-based safety switches”, “supports multi-week planning”, etc.)

---

## Training philosophy & scope

- `Coach.md` is the primary source of truth for:
  - Phases (BASE / BUILD / PEAK / TAPER)
  - Goal Mode (G1 / G2 / G3)
  - Volume strategy, long run stages, and quality session patterns
  - Pace model (Easy / Long / MP / Tempo / Interval)

- **Safety switches** (fatigue, elevation, pain, HR, etc.):
  - Are documented in `Coach.md` as a **manual checklist for runners**.
  - Are **not implemented** in the current code.
  - The online planner proposes a **baseline structure only**.
  - Runners are expected to manually adjust using the safety-switch guidance in `Coach.md`.

Do **not** reintroduce automatic safety logic (fatigue/elevation/HR/pain) into the engine or UI unless explicitly instructed.

---

## Core interfaces (do not break by default)

### Engine: `planner_core.py`

The v1.0 engine exposes the following interface:

- `@dataclass PlanConfig` with fields:

  ```python
  @dataclass
  class PlanConfig:
      race_date: date
      recent_weekly_km: float
      recent_long_km: float
      goal_marathon_time: str  # "03:30:00"
      current_mp: str          # "05:10" (minutes:seconds per km)
````

* `generate_week_plan`:

  ```python
  def generate_week_plan(
      config: PlanConfig,
      *,
      start_date: Optional[date] = None,
  ) -> Dict[str, Any]:
      """
      Returns:
          {
              "summary": {...},  # weekly metrics
              "days": [...],     # list of day-level sessions
              "notes": [...],    # list of coach notes
          }
      """
  ```

The engine is responsible for:

* Determining Phase (BASE / BUILD / PEAK / TAPER) from `start_date` and `race_date`.
* Computing Goal Mode (G1 / G2 / G3) from `goal_marathon_time` and `current_mp`.
* Generating a weekly plan (total volume, long run stage/distance, number and type of quality sessions, easy runs) that is consistent with `Coach.md`.

### UI: `app_streamlit.py`

* Uses the v1.0 `PlanConfig` fields as sidebar inputs:

  * Race date
  * Plan start date
  * Recent weekly km
  * Recent long run km
  * Goal marathon time (HH:MM:SS)
  * Current MP (MM:SS per km)
* Calls `generate_week_plan` and renders:

  * Weekly summary metrics:

    * Phase, goal_mode, target_weekly_km, planned_weekly_km,
      long_run_distance, long_run_stage, quality_sessions
  * A day-by-day table:

    * Date, weekday, session type, distance, pace range, notes
  * Optional coach notes section

When extending the UI, keep this basic flow intact for v1.0. New flows should live in new files (e.g. `app_streamlit_v1_1.py`).

---

## Change policy (non-destructive updates)

Unless explicitly requested:

* Do **not** perform large in-place refactors or deletions in:

  * `planner_core.py`
  * `app_streamlit.py`
  * `tests/test_planner_core.py`
  * `Coach.md`
  * `README.md`
* Prefer **additive, versioned** changes:

  * New engines in new modules (e.g. `planner_core_v1_1.py`)
  * New UIs in new modules (e.g. `app_streamlit_v1_1.py`)
  * New tests in new test files.

When adding a new engine variant:

* Keep the original `PlanConfig` unchanged.
* If additional configuration is needed, use a **new** config dataclass
  in the new module, rather than extending the existing one.

The stable v1.0 entry points must remain runnable with:

```bash
pip install -r requirements.txt
streamlit run app_streamlit.py
pytest
```

---

## Testing rules

* Any change to core planning logic or new engine variants should be accompanied by **scenario-based tests**.

* Always ensure that:

  ```bash
  pytest
  ```

  completes **without failures** before considering changes complete.

* For new versions/experiments:

  * Add new tests rather than modifying existing v1.0 tests, where possible.
  * Example:

    * `tests/test_planner_core_v1_1.py` for a new `planner_core_v1_1.py`.

* Tests should at least validate:

  * No runtime errors for typical configurations.
  * Phase / Goal Mode decisions are reasonable.
  * Long run distance and stage follow the intended rules.
  * Taper week / race week patterns remain safe and coherent.

---

## Comments & documentation style

### Comments in code

* For **core algorithms and planning heuristics** (e.g. phase logic, long-run stage selection, quality session patterns):

  * Add **Korean comments** explaining the intent and high-level behaviour.
  * Keep comments concise but meaningful.
  * Example:

    ```python
    # 이 함수는 대회까지 남은 주차를 기준으로 BASE/BUILD/PEAK/TAPER를 결정한다.
    ```

* For docstrings and smaller utility functions:

  * English is acceptable.
  * Use short and clear descriptions with type hints.

### README & new features

* When adding a new feature, module, or UI entry point:

  * Update `README.md` (or add a new section) to describe:

    * What the new entry point is.
    * How to run it.
  * Include **at least one example of input and output**:

    * Example configuration (e.g. race date, goal time, recent weekly km).
    * Example snippet of the generated weekly plan (or a screenshot/link if appropriate).

This ensures that both humans and agents can quickly understand and verify new behaviour.

---

## Coaching philosophy change process

When the training philosophy itself needs to change (e.g. different peak strategy, new Goal Mode rules):

1. **Version the philosophy document first.**

   * Create a new versioned file, e.g.:

     * `Coach_v1.1.md` (copied from the current `Coach.md`)
   * Apply conceptual changes in `Coach_v1.1.md`, and clearly note:

     * What changed vs. the previous version
     * Why it changed (rationale, data, or experience)

2. **Update or create engine variants based on the new philosophy.**

   * Do **not** immediately rewrite the v1.0 engine.
   * Instead, create a new engine module (e.g. `planner_core_v1_1.py`) implementing the updated rules.
   * Add tests that reflect the new philosophy.

3. **Keep `Coach.md` as the canonical “current default” only when you deliberately decide to migrate.**

   * Once a new philosophy version is stable and accepted, you may:

     * Copy `Coach_v1.1.md` back to `Coach.md`, or
     * Make `Coach.md` a short index pointing to the active version.
   * Any migration from v1.0 to v1.1 should be explicit and documented in `README.md`.

This process keeps a clear history of philosophy changes and prevents accidental drift between documentation and implementation.

---

## Dependencies & external libraries

* Keep dependencies minimal and focused:

  * Prefer the Python standard library and the existing dependencies in `requirements.txt`.
  * Do not add heavy libraries unless there is a clear benefit.

* If you add a new dependency:

  * Append it to `requirements.txt`.
  * Update `README.md` to explain:

    * Why it is needed.
    * Any special installation notes.

---

## Typical tasks you may be asked to perform

You may be asked to:

1. **Extend the engine**

   * Implement alternative heuristics in a new module (e.g. `planner_core_v1_1.py`).
   * Add optional configuration fields in a new config dataclass (in the new module), while keeping the existing `PlanConfig` intact.

2. **Improve or fork the UI**

   * Add new views, charts, or export options in a new Streamlit app file (e.g. `app_streamlit_v1_1.py`).
   * Keep `app_streamlit.py` working with the original flow.

3. **Enhance testing**

   * Add new scenario tests for new variants.
   * Ensure `pytest` passes across both stable and experimental modules.

4. **Refine documentation**

   * Update `README.md` to document new entry points and examples.
   * Add comments (especially in Korean) to clarify algorithmic decisions.

Always respect the **stable vs experimental** separation and the **non-destructive update** policy unless instructed otherwise.

```

---
