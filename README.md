# knock knock AI - Content Marketing Automation Platform

AIエージェント駆動型コンテンツマーケティング自動生成システム

## Overview

knock knock AI is an AI-powered content marketing automation platform designed for the real estate and PropTech industry. It uses a multi-agent architecture to automatically generate, edit, localize, and publish SEO-optimized articles across multiple platforms.

### Architecture

The system employs a **6+1 Agent Architecture** that mirrors a human content team:

| Agent | Role | Model |
|-------|------|-------|
| **Orchestrator** | Pipeline supervision & quality gates | Claude Opus |
| **Researcher** | Market data & competitor analysis | Claude Sonnet + Tavily |
| **Planner** | Article structure & SEO strategy | Claude Sonnet |
| **Writer** | Long-form content generation | Claude Opus |
| **Editor** | Quality assurance (5-dimension scoring) | Claude Sonnet |
| **Localizer** | Multi-language cultural adaptation | Claude Sonnet |
| **Publisher** | Platform formatting & distribution | Claude Haiku |

### Content Pipeline

```
Calendar Entry → Researcher → Planner → Writer → Editor → (Localizer) → Publisher
                                          ↑                    |
                                          └── retry on fail ───┘
```

Each step includes quality gates with automatic retry (max 3 attempts).

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy (async), Celery
- **Frontend**: Next.js 14, React 18, TypeScript, Tailwind CSS
- **Database**: PostgreSQL 16, Redis 7
- **Vector DB**: Pinecone (RAG knowledge base)
- **AI Models**: Anthropic Claude (Opus/Sonnet/Haiku), OpenAI embeddings
- **Deployment**: Docker Compose, ready for AWS/GCP Kubernetes

## Quick Start

### Prerequisites

- Docker & Docker Compose
- API keys: Anthropic (required), Tavily (for research), OpenAI (for embeddings)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Panaki0831/knock-knock-AI.git
   cd knock-knock-AI
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. Start all services:
   ```bash
   docker compose up -d
   ```

4. Access the dashboard:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API docs: http://localhost:8000/docs

### Development (without Docker)

**Backend:**
```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/dashboard/overview` | Dashboard metrics |
| GET | `/api/v1/articles` | List articles |
| GET | `/api/v1/articles/{id}` | Get article detail |
| PATCH | `/api/v1/articles/{id}` | Update article |
| POST | `/api/v1/articles/{id}/approve` | Approve article |
| GET | `/api/v1/calendar` | List calendar entries |
| POST | `/api/v1/calendar` | Create calendar entry |
| POST | `/api/v1/pipeline/trigger` | Trigger content pipeline |
| GET | `/api/v1/pipeline/runs` | List pipeline runs |

## Quality Framework

The Editor agent scores each article across 5 dimensions:

1. **Readability** (0-100): Sentence variety, paragraph length, clarity
2. **SEO Score** (0-100): Keyword placement, heading structure, meta description
3. **AI Detection** (0-100): Human-likeness, pattern diversity, burstiness
4. **Factual Accuracy** (0-100): Source-backed claims, no fabrication
5. **Brand Consistency** (0-100): Tone alignment, actionability

Pass criteria: All scores >= 70, average >= 75.

## Supported Platforms

- **Japanese**: note, Zenn, Hatena Blog
- **Global**: Medium, WordPress
- **SNS**: Twitter/X, LinkedIn
- **Email**: Newsletter summaries

## Project Structure

```
knock-knock-AI/
├── backend/
│   ├── app/
│   │   ├── agents/          # AI agents (7 agents)
│   │   ├── api/routes/      # FastAPI endpoints
│   │   ├── db/              # Database setup
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── services/        # Business logic
│   │   ├── config.py        # Settings from env vars
│   │   └── main.py          # FastAPI application
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js pages
│   │   ├── components/      # React components
│   │   └── lib/             # API client & types
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

## License

Confidential - SAMURAI ARCHITECTS Inc.
