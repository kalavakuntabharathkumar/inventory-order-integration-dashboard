# Inventory API
FastAPI + MongoDB backend for orders, stock, provider webhooks, metrics, and retry queueing. Install requirements, copy `.env.example` to `.env`, then run `uvicorn app.main:app --reload --port 8000`. MongoDB is required for data routes. API docs: `/docs`. Configure webhook secrets before exposing endpoints publicly.
