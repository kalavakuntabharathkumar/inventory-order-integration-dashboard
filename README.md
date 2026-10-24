# Inventory and Order Integration Dashboard

React + TypeScript frontend with FastAPI and MongoDB backend. Includes order search/filtering, stock overview, channel status, sync exception monitor, add-order flow, order and inventory endpoints, Shopify webhook ingestion, Razorpay payment-event ingestion, duplicate order handling, and retry queueing.

## Requirements
Node.js 20+, Python 3.11+, MongoDB 6+.

## Start backend
`cd backend`, create/activate a virtual environment, `pip install -r requirements.txt`, copy `.env.example` to `.env`, then run `uvicorn app.main:app --reload --port 8000`. API docs: `http://localhost:8000/docs`.

## Start frontend
In another terminal: `cd frontend`, `npm install`, copy `.env.example` to `.env`, then `npm run dev`. Open the Vite URL, normally `http://localhost:5173`.

## Integration setup
Set Shopify and Razorpay webhook secrets in environment variables before exposing webhook endpoints publicly. The warehouse CSV integration is represented in the UI but a scheduled spreadsheet importer is not included. Frontend/backend deployment to Vercel/AWS EC2 is not automated. Demo data is shown when API calls fail. Resume metrics in the brief are not benchmarked by this sample.
