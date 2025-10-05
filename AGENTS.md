# Repository Guidelines

## Project Structure & Module Organization
- `app.py` hosts the Streamlit layout; keep it declarative and delegate business rules to modules inside `voucher_logic/` (e.g. `voucher_logic/validators.py`).
- Place reusable data helpers and fixtures under `voucher_logic/` to keep logic testable.
- Store tests in `tests/`, mirroring module names (`tests/test_validators.py`).
- Put documentation next to `README.md` and future datasets or static files under `assets/`; reference them with relative paths.

## Build, Test, and Development Commands
- `source env/bin/activate` — activate the local virtual environment before installing or running.
- `pip install -r requirements.txt` — install dependencies; regenerate with `pip freeze > requirements.txt` after updates.
- `streamlit run app.py` or `streamlit run app.py --server.port 8502` — launch the UI locally.
- `python -m pip check` — verify dependency consistency.
- `pytest --cov=app` — execute tests with coverage.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and 88-character lines.
- Use snake_case for variables, functions, and widget keys; PascalCase for classes.
- Group imports: standard library, third-party, then local modules.
- Run `black` and/or `ruff` when available; otherwise format manually.
- Keep side effects inside dedicated functions so Streamlit reruns remain predictable.

## Testing Guidelines
- Use pytest; name tests as `test_<condition>_<result>` for readability.
- Target fixtures for voucher datasets and Streamlit session state to keep deterministic coverage.
- Track coverage with `pytest --cov=app`; aim for ≥80% statements.
- Document manual validation flows when automated checks are missing.

## Commit & Pull Request Guidelines
- Write commit subjects in imperative mood under 72 characters; add bodies when context is not obvious.
- Ensure PRs describe the problem, the solution, and verification steps (e.g. `streamlit run app.py`).
- Attach screenshots or GIFs for UI changes, link related issues, and confirm `requirements.txt` is current.
