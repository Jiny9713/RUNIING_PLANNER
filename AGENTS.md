# Agent instructions for this repo

Goal:
- Turn this marathon training planner into a deployable v1.0 web app.
- Keep the existing training philosophy in `Coach.md` and logic in `planner_v7.py` as the source of truth.
- Do not add new complex features for now; focus on packaging and cleaning up for deployment.

Core requirements:
1. Create a core engine module:
   - File: `planner_core.py`
   - Define a `PlanConfig` dataclass (race_date, recent_weekly_km, recent_long_km, goal_marathon_time, current_mp, recent_weekly_altitude, fatigue_level).
   - Implement `generate_week_plan(config: PlanConfig)` which returns a structured week plan.
   - Move logic from `planner_v7.py` into this module with minimal behavioral changes.

2. Streamlit app:
   - File: `app_streamlit.py`
   - Sidebar input fields for PlanConfig.
   - Call `generate_week_plan` and render:
     - Weekly summary (total distance, number of quality sessions, long run distance and stage).
     - A table: day, session type, distance, pace range, notes.

3. Tests:
   - Folder: `tests/`
   - Create simple scenario-based tests (3–5 cases) to ensure no errors and basic rules are respected.

4. Packaging:
   - `requirements.txt` with only needed libraries (e.g. streamlit, pandas if used).
   - `README.md` with short description and how to run locally:
     - `pip install -r requirements.txt`
     - `streamlit run app_streamlit.py`

Conventions:
- Keep function and variable names clear and Pythonic.
- Prefer small, well-named functions over very large ones.
- Do not change the training logic unless necessary for refactoring.
