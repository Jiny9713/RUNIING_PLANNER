# Agent instructions for this repo

## Overview

This repository contains a marathon training planner with:

- A core planning engine in `planner_core.py` (current default)
- A Streamlit web UI in `app_streamlit.py` (current default UI)
- Scenario-based tests in `tests/`
- A coaching philosophy document in `Coach.md`

The goal is to maintain and extend this system as a **stable, deployable web app** while keeping the training philosophy coherent and versioned.

---

## Versioning model: “default = latest, suffix = archived”

### Current default (no suffix)

- The files **without any version suffix** are always considered the **latest accepted default**:

  - `planner_core.py`  → latest engine
  - `app_streamlit.py` → latest UI entry point (used by Streamlit Cloud)
  - `tests/test_planner_core.py` (and related default tests)
  - `Coach.md`
  - `README.md`
  - `requirements.txt`

- These files should always be runnable with:

  ```bash
  pip install -r requirements.txt
  streamlit run app_streamlit.py
  pytest
````

### Versioned snapshots (archived or experimental)

* Older or experimental versions are kept as **versioned copies** with suffixes:

  * `planner_core_v1_0.py`
  * `planner_core_v1_1.py`
  * `app_streamlit_v1_0.py`
  * `app_streamlit_v1_1.py`
  * `tests/test_planner_core_v1_1.py`
  * Or under folders like `legacy_versions/`, `experiments/`, `v1_1/`, etc.

* These snapshots must **not** be deleted or heavily rewritten unless explicitly requested.

* At the top of each versioned file, include a short comment describing:

  * What it is based on (e.g. “based on `planner_core.py` as of v1.0”)
  * What changed (e.g. “adds injury-aware weekly volume heuristic”)

---

## Promotion flow: making a new version the default

When a new engine/UI variant has been validated and the user explicitly asks to “make this the default”:

1. **Archive the current default**

   * If `planner_core_v1_0.py` does not exist yet:

     * Copy (or rename) the current `planner_core.py` to `planner_core_v1_0.py`.
   * If `app_streamlit_v1_0.py` does not exist yet:

     * Copy (or rename) the current `app_streamlit.py` to `app_streamlit_v1_0.py`.
   * If needed, archive current default tests as:

     * `tests/test_planner_core_v1_0.py`.

2. **Promote the new version**

   * If the new engine is in `planner_core_v1_1.py` (for example):

     * Copy (or rename) it to `planner_core.py` so that the default engine uses the new logic.
   * If the new UI is in `app_streamlit_v1_1.py`:

     * Copy (or rename) it to `app_streamlit.py` so that `streamlit run app_streamlit.py` uses the new UI.
   * Update or create tests so that:

     * `tests/test_planner_core.py` targets the new default behaviour.
     * Versioned tests (e.g. `test_planner_core_v1_0.py`, `test_planner_core_v1_1.py`) remain as historical references if needed.

3. **Update documentation**

   * Update `README.md` to reflect:

     * Which version is now the default.
     * How to run any archived versions (if they should still be usable).
   * If relevant, note the promotion in a changelog or “Release notes” section.

4. **Do not break archived versions**

   * Avoid editing the historical files (`*_v1_0.py`, `*_v1_1.py`) in ways that change their original behaviour.
   * If a bug is found in a historical version, either:

     * Document it as a known issue, or
     * Add a separate `*_v1_0_fix.py` variant, instead of silently changing the original.

---

## Training philosophy & scope

* `Coach.md` is the primary source of truth for:

  * Phases (BASE / BUILD / PEAK / TAPER)
  * Goal Mode (G1 / G2 / G3)
  * Volume strategy, long run stages, and quality session patterns
  * Pace model (Easy / Long / MP / Tempo / Interval)

* **Safety switches** (fatigue, elevation, pain, HR, etc.):

  * Are documented in `Coach.md` as a **manual checklist for runners**.
  * Are **not implemented** as automatic logic in the default engine.
  * The online planner proposes a **baseline structure only**.
  * Runners are expected to manually adjust using the safety-switch guidance in `Coach.md`.

Do **not** introduce automatic fatigue/elevation/HR/pain safety logic into the default engine or UI unless explicitly instructed.

---

## Core interfaces (default engine & UI)

### Engine: `planner_core.py` (default)

The default engine exposes a `PlanConfig`-style dataclass and a `generate_week_plan`-style function (names may evolve, but the shape should stay consistent unless the user approves a breaking change).

Typical example:

```python
@dataclass
class PlanConfig:
    race_date: date
    recent_weekly_km: float
    recent_long_km: float
    goal_marathon_time: str  # "03:30:00"
    current_mp: str          # "05:10" (minutes:seconds per km)
    # Optional: flags such as injury/illness, etc., depending on current default version.
```

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

Responsibilities:

* Determine Phase (BASE / BUILD / PEAK / TAPER) from `start_date` and `race_date`.
* Compute Goal Mode (G1 / G2 / G3) from `goal_marathon_time` and `current_mp`.
* Generate a weekly plan (volume, long run stage/distance, number and type of quality sessions, easy runs) consistent with `Coach.md`.
* Apply any currently accepted heuristics (e.g. injury-aware volume) for the **default** behaviour.

### UI: `app_streamlit.py` (default)

* Uses the default engine’s config fields as sidebar inputs:

  * Race date
  * Plan start date
  * Recent weekly km
  * Recent long run km
  * Goal marathon time (HH:MM:SS)
  * Current MP (MM:SS per km)
  * Additional flags (e.g. last week’s reduction reason / injury flag) if they are part of the current default.

* Calls the default `generate_week_plan` and renders:

  * Weekly summary metrics:

    * Phase, goal_mode, target_weekly_km, planned_weekly_km,
      long_run_distance, long_run_stage, quality_sessions
  * A day-by-day table:

    * Date, weekday, session type, distance, pace range, notes
  * Optional coach notes section.

When adding new UIs:

* Use versioned filenames (`app_streamlit_vX_Y.py`) until promotion.
* Do not break `app_streamlit.py` unless performing an explicit promotion.

---

## Change policy (non-destructive by default)

Unless explicitly requested:

* Do **not** perform large in-place refactors or deletions in:

  * `planner_core.py`
  * `app_streamlit.py`
  * `tests/test_planner_core.py`
  * `Coach.md`
  * `README.md`

* For new engine experiments, create **new, versioned files**:

  * `planner_core_v1_2.py`, `planner_core_experiment.py`, etc.
  * Matching UI files if needed, e.g. `app_streamlit_v1_2.py`.
  * Matching tests, e.g. `tests/test_planner_core_v1_2.py`.

* Only after the user approves, follow the **promotion flow** to move the new version into the default filenames.

---

## Testing rules

* Any change to core planning logic or new engine variants should be accompanied by **scenario-based tests**.

* Always ensure:

  ```bash
  pytest
  ```

  completes **without failures** before considering changes complete.

* For new versions/experiments:

  * Add new tests rather than modifying existing default tests, where possible.
  * Examples:

    * `tests/test_planner_core_v1_1.py` for a new injury-aware volume heuristic.
    * `tests/test_planner_core_v1_2.py` for a multi-week planner, etc.

* Tests should at least validate:

  * No runtime errors for typical configurations.
  * Phase / Goal Mode decisions are reasonable.
  * Long run distance and stage follow the intended rules.
  * Taper week / race week patterns remain safe and coherent.
  * For injury-aware logic: volume progression behaves as specified across different R/MIN/injury_flag combinations.

---

## Comments & documentation style

### Comments in code

* For **core algorithms and planning heuristics** (phase logic, long-run stage selection, quality session patterns, volume heuristics):

  * Add **Korean comments** explaining the intent and high-level behaviour.
  * Keep them concise but meaningful.

  Example:

  ```python
  # 이 함수는 지난 주 거리와 부상 여부를 기반으로 이번 주 목표 주간 거리를 결정한다.
  ```

* For docstrings and smaller utility functions:

  * English is acceptable.
  * Use short and clear descriptions with type hints.

### README & new features

* When adding a new feature, module, or UI entry point:

  * Update `README.md` (or add a new section) to describe:

    * What the new entry point is.
    * How to run it (e.g. `streamlit run app_streamlit_v1_1.py`).
  * Include **at least one example of input and output**:

    * Example configuration (race date, goal time, recent weekly km).
    * Example of the generated weekly plan (summary and one or two days).

This keeps both humans and agents able to quickly understand and verify new behaviour.

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

   * Do **not** immediately rewrite the default engine.
   * Instead, create a new engine module (e.g. `planner_core_v1_2.py`) implementing the updated rules.
   * Add tests that reflect the new philosophy.

3. **Promote the new philosophy only when ready.**

   * Once the new philosophy + engine/UI are stable and accepted:

     * Option A: Copy `Coach_v1.1.md` back to `Coach.md` and follow the promotion flow to make the new engine/UI the defaults.
     * Option B: Make `Coach.md` a short index that points to the active version.
   * Document any migration in `README.md` or a changelog.

This keeps a clear history of philosophy changes and prevents accidental drift between documentation and implementation.

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

   * Implement alternative heuristics (e.g. injury-aware volume, multi-week plans) in new versioned modules.
   * Once validated, follow the promotion flow to make them the default.

2. **Improve or fork the UI**

   * Add new views, charts, or export options in new Streamlit files.
   * Promote them to `app_streamlit.py` when approved.

3. **Enhance testing**

   * Add new scenario tests for new variants.
   * Keep `pytest` passing for both the default engine and any important historical versions.

4. **Refine documentation**

   * Update `README.md` to document new entry points and examples.
   * Add Korean comments to clarify algorithmic decisions.

Always respect the **“default = latest, suffix = archived”** model and the **non-destructive update** policy unless the user explicitly asks for a different behaviour.

```

---

