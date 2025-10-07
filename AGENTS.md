# Repository Guidelines

## Project Structure & Module Organization
- UI entrypoint lives in `app.py`; keep it focused on Streamlit layout and event wiring.
- Core logic sits under `voucher_logic/` (e.g., `extraction.py`, `validators.py`, `highlight.py`). Reuse these modules for new rules so they stay testable.
- Session-level helpers, sample fixtures, and persistence stubs are colocated with their runtime counterparts; add new utilities in matching submodules.
- Tests mirror runtime code in `tests/` (for example `tests/test_extraction.py`). Add new cases alongside the feature they verify.
- Place static assets or reference documents in an `assets/` directory and load them via relative paths.

## Build, Test, and Development Commands
- `source env/bin/activate` — activate the project virtualenv before development.
- `pip install -r requirements.txt` — install Python dependencies; regenerate with `pip freeze > requirements.txt` after adding packages.
- `streamlit run app.py` (or `streamlit run app.py --server.port 8502`) — launch the local UI for manual testing.
- `python -m pip check` — validate dependency compatibility.
- `pytest --cov=app` — run the automated test suite with coverage.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation; keep lines ≤88 chars.
- Use snake_case for functions, variables, and Streamlit widget keys; use PascalCase for classes.
- Group imports by standard library, third-party, then local modules.
- Run `black` or `ruff` if available; otherwise format manually before committing.
- Keep Streamlit code declarative—declare widgets top-to-bottom and isolate side effects in helper functions under `voucher_logic/`.

## Testing Guidelines
- Prefer pytest with fixture-based tests that mirror runtime modules (`tests/test_controller.py`, `tests/test_extraction.py`).
- Name tests `test_<condition>_<result>` to clarify intent.
- Target ≥80% statement coverage and review new logic with regression tests (e.g., Japanese/English voucher fixtures).
- Document any manual validation steps when automated coverage is not feasible.

## Commit & Pull Request Guidelines
- Write commit subjects in imperative mood ≤72 characters (e.g., `Improve title extraction scoring`). Add short bodies when context is non-obvious.
- Ensure `requirements.txt` is up to date before review.
- Pull requests should describe the user problem, outline the solution, list verification steps (`streamlit run app.py`, `pytest --cov=app`), and attach UI screenshots or GIFs for layout changes.
- Link related issues and highlight follow-up tasks or known limitations.
