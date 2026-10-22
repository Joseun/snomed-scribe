.PHONY: install test run

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

test:
	cd backend && .venv/bin/pytest

run:
	docker compose up
