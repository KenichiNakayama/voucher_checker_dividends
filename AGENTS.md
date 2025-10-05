# Repository Guidelines

## Project Structure & Module Organization
- `app.py` defines the Streamlit layout and coordinates the analysis workflow; keep UI-only concerns here.
- Core logic lives under `voucher_logic/` (controllers, validators, PDF ingestion, LLM fallbacks). Create new helpers in this package so they remain importable in tests.
- Automated tests mirror the runtime modules in `tests/` (e.g., `tests/test_validators.py`).
- Documentation such as this guide and release notes belongs beside `README.md`. Store datasets or static assets in an `assets/` folder and reference them with relative paths.

## Build, Test, and Development Commands
- `source env/bin/activate` — activate the local virtualenv before installing or running tools.
- `pip install -r requirements.txt` — install dependencies; regenerate with `pip freeze > requirements.txt` after updates.
- `streamlit run app.py` or `streamlit run app.py --server.port 8502` — launch the UI locally (use the alternate port for parallel branches).
- `python -m pip check` — verify dependency metadata for conflicts.
- `pytest --cov=app` — execute the test suite with statement coverage reporting.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and keep lines under 88 characters.
- Use snake_case for variables, functions, and Streamlit widget keys; reserve PascalCase for classes.
- Group imports in the order: standard library, third-party, local.
- Run `black` and/or `ruff` when available; otherwise ensure formatting manually.
- Keep Streamlit callbacks declarative and isolate side effects in helper functions to avoid rerun surprises.

## Testing Guidelines
- Write tests with pytest; name them `test_<condition>_<result>` for clarity.
- Mirror module structure under `tests/` and prefer fixtures for voucher samples and Streamlit session state.
- Maintain ≥80% statement coverage (`pytest --cov=app`) and document any manual validation steps until coverage is achieved.

## Commit & Pull Request Guidelines
- Commit subjects should be imperative and ≤72 characters (e.g., `Handle provider key loading`). Include a short body if context is non-obvious.
- Pull requests must describe the problem, outline the solution, and list verification steps (such as `streamlit run app.py`).
- Attach screenshots or GIFs for UI changes, link related issues, and confirm `requirements.txt` captures new dependencies before requesting review.

## Security & Configuration Tips
- Store sensitive keys outside the repo: use `.envrc` (ignored by Git) for local development and Streamlit App settings → Secrets for deployments.
- Never hard-code API keys or client secrets; rely on `voucher_logic.settings.get_provider_key()` to read them at runtime.
- Review `.gitignore` before adding new files to ensure generated artifacts and local state directories stay untracked.
