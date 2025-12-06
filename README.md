# AIOps Agent Executor

Agent executor for AIOps project - LLM configuration management and dynamic agent team orchestration.

## Features

- **LLM Configuration Management**: Unified management for multiple LLM providers (OpenAI, Anthropic, AWS Bedrock, Azure, etc.)
- **Dynamic Agent Team Creation**: Create agent teams from topology configurations
- **Streaming Execution**: Real-time SSE streaming of agent execution
- **Structured Output**: Generate structured outputs based on JSON Schema

## Tech Stack

- **Framework**: Python 3.11+ / FastAPI
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Agent Framework**: LangChain / LangGraph
- **Authentication**: JWT
- **Encryption**: AES-256 for credential storage

## Project Structure

```
aiops-agent-executor/
├── src/
│   └── aiops_agent_executor/
│       ├── api/                    # API layer
│       │   └── v1/
│       │       ├── endpoints/      # Route handlers
│       │       └── router.py       # API router
│       ├── core/                   # Core utilities
│       │   ├── config.py          # Configuration management
│       │   ├── logging.py         # Structured logging
│       │   └── security.py        # Encryption utilities
│       ├── db/                     # Database layer
│       │   ├── models/            # SQLAlchemy models
│       │   ├── base.py            # Base model classes
│       │   └── session.py         # Session management
│       ├── schemas/               # Pydantic schemas
│       ├── services/              # Business logic
│       ├── agents/                # LangChain/LangGraph agents
│       ├── utils/                 # Utility functions
│       └── main.py               # Application entry point
├── tests/                         # Test suites
├── alembic/                       # Database migrations
├── doc/                           # Documentation
├── pyproject.toml                # Project configuration
├── Dockerfile                    # Production Docker image
├── docker-compose.yml            # Docker Compose for deployment
└── Makefile                      # Development commands
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Docker & Docker Compose (optional)

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd aiops-agent-executor
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   make dev
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Start PostgreSQL** (if not using Docker)
   ```bash
   # Ensure PostgreSQL is running and create database
   createdb aiops_agent_executor
   ```

6. **Run migrations**
   ```bash
   make migrate
   ```

7. **Start the application**
   ```bash
   make run
   ```

### Using Docker

```bash
# Start all services (app + PostgreSQL)
make docker-up

# Or for development with hot reload
make docker-dev
```

## API Documentation

When running in development mode, API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Main Endpoints

#### Provider Management
- `POST /api/v1/providers` - Create provider
- `GET /api/v1/providers` - List providers
- `GET /api/v1/providers/{id}` - Get provider details

#### Agent Teams
- `POST /api/v1/teams` - Create team from topology
- `POST /api/v1/teams/{id}/execute` - Execute team (SSE streaming)
- `POST /api/v1/teams/{id}/structured-output` - Get structured output

## Development

### Running Tests

```bash
# Run all tests
make test

# Run with coverage report
make test-cov
```

### Code Quality

```bash
# Run linting
make lint

# Format code
make format
```

### Database Migrations

```bash
# Create new migration
make revision

# Apply migrations
make migrate

# Rollback last migration
make rollback
```

## Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://...` |
| `SECRET_KEY` | Application secret key | - |
| `ENCRYPTION_KEY` | 32-byte key for credential encryption | - |
| `DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

See `.env.example` for all configuration options.

## License

MIT
