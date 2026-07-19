PYTHON := apps/api/.venv/Scripts/python.exe
PNPM := pnpm

.PHONY: api-install api-test api-lint api-run web-install web-test web-run

api-install:
	cd apps/api && .venv/Scripts/python.exe -m pip install -e ".[dev]"

api-test:
	cd apps/api && .venv/Scripts/python.exe -m pytest -q

api-lint:
	cd apps/api && .venv/Scripts/ruff.exe check .
	cd apps/api && .venv/Scripts/mypy.exe src

api-run:
	cd apps/api && .venv/Scripts/uvicorn.exe fruit_agent.app:app --reload

web-install:
	cd apps/web && $(PNPM) install

web-test:
	cd apps/web && $(PNPM) test

web-run:
	cd apps/web && $(PNPM) dev
