# Revenue Recovery Agent

**Revenue Recovery Agent** is an automated, AI-driven platform designed to help subscription-based businesses reduce customer churn and recover lost revenue. By integrating directly with payment gateways like Razorpay, the system automatically detects failed payments, evaluates customer risk profiles, and executes personalized follow-up actions (such as targeted emails or SMS) based on customizable merchant policies.

## Key Features

- **Automated Dunning Workflows:** Configurable policies that trigger specific actions based on the age and amount of the failed payment.
- **Real-time Event Ingestion:** Secure webhook integration with Razorpay for live tracking of invoices, subscriptions, and payment events.
- **Risk & Promise Tracking:** Built-in systems to categorize customer risk and track "promises to pay" with scheduled due dates.
- **Financial Ledger:** A dedicated recovery ledger to accurately attribute and track every cent of recovered revenue.
- **Agent Actions:** Automated system to interact with customers intelligently to maximize payment recovery while maintaining good customer relations.

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy, Celery (Background Tasks)
- **Frontend:** React, TypeScript, Vite
- **Database:** PostgreSQL (with pgvector/UUID support)
- **Cache & Message Broker:** Redis
- **Orchestration:** Docker & Docker Compose
- **Integrations:** Razorpay, Anthropic API (for AI actions)

## Prerequisites

- [Docker](https://www.docker.com/get-started) and Docker Compose
- Node.js (if running frontend locally outside Docker)
- Python 3.10+ (if running backend locally outside Docker)

## Getting Started

### 1. Environment Setup

Copy the example environment file and configure your API keys:

```bash
cp .env.example .env
```

Ensure you update the following keys in your `.env` file:
- `SECRET_KEY`
- `ANTHROPIC_API_KEY`
- `SEED_RAZORPAY_KEY_ID`
- `SEED_RAZORPAY_KEY_SECRET`
- `SEED_RAZORPAY_WEBHOOK_SECRET`

### 2. Run with Docker Compose

The easiest way to run the entire stack (Database, Redis, Backend API, Celery Worker, and Frontend) is using Docker Compose:

```bash
docker-compose up --build
```

### 3. Access the Services

Once the containers are running, you can access the services at:
- **Frontend Dashboard:** [http://localhost:5173](http://localhost:5173)
- **Backend API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)

## Project Structure

- `/backend` - The FastAPI application, SQLAlchemy models, API routers, and Celery workers.
- `/frontend` - The React/Vite dashboard for merchants to configure policies and view recovery metrics.
- `docker-compose.yml` - Orchestrates the multi-container environment.

## License

MIT License
