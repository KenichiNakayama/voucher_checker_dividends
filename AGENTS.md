# Repository Guidelines

## Project Structure & Module Organization
Keep `app.py` dedicated to Streamlit layout and event wiring; move reusable parsing, validation, and state logic into `voucher_logic/` (e.g., `voucher_logic/controller.py`, `voucher_logic/validators.py`). Add new datasets or static assets under `assets/` and reference them with relative paths. Mirror runtime modules under `tests/` using matching filenames (`voucher_logic/highlight.py` → `tests/test_highlight.py`). Documentation such as this guide and release notes lives beside `README.md`.

## Build, Test, and Development Commands
Activate the environment before working: `source env/bin/activate`. Install dependencies with `pip install -r requirements.txt`; regenerate the lockfile via `pip freeze > requirements.txt` after upgrades. Run the UI using `streamlit run app.py` (use `--server.port 8502` when running multiple branches). Confirm dependencies with `python -m pip check`. Execute the suite and coverage using `pytest --cov=app`.

## Coding Style & Naming Conventions
Follow PEP 8, 4-space indentation, and keep lines ≤88 characters. Use snake_case for variables, functions, and Streamlit widget keys; reserve PascalCase for classes. Group imports by standard library, third-party, then local modules. Keep Streamlit code declarative: define widgets top-to-bottom and isolate side effects inside helpers. Run `black` and `ruff` when available; otherwise format manually before committing.

## Testing Guidelines
Tests use pytest; name cases `test_<condition>_<result>` to communicate intent. Create fixtures for voucher PDFs and Streamlit session state to keep behaviour deterministic. Target ≥80% statement coverage with `pytest --cov=app`, and note any manual verification steps in issue descriptions until automation is added.

## Commit & Pull Request Guidelines
Write commit subjects in the imperative mood under 72 characters (e.g., `Handle provider key loading`) and add a short body when context is unclear. Pull requests should describe the problem, summarize the fix, and list verification steps such as `streamlit run app.py`. Attach screenshots or GIFs for UI updates, link related issues, and verify `requirements.txt` is up to date before requesting review.

## Security & Configuration Tips
Never hard-code keys. For local work, store secrets in `.envrc` (ignored by Git) using lines like `export OPENAI_API_KEY="sk-..."`. For deployments, add the same keys under Streamlit App settings → Secrets. Load credentials through `voucher_logic.settings.get_provider_key()` so the app falls back gracefully when keys are absent.
