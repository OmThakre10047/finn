.PHONY: refresh backend frontend test

refresh:
	cd backend && .venv/bin/python scripts/refresh_snapshot.py

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/python scripts/test_fixes.py
