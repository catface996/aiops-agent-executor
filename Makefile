.PHONY: help install dev test lint format clean docker-up docker-down migrate run

# Default target
help:
	@echo "Available commands:"
	@echo "  make install     - Install production dependencies"
	@echo "  make dev         - Install all dependencies including dev"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run linting checks"
	@echo "  make format      - Format code"
	@echo "  make clean       - Clean build artifacts"
	@echo "  make docker-up   - Start Docker containers"
	@echo "  make docker-down - Stop Docker containers"
	@echo "  make docker-dev  - Start development Docker containers"
	@echo "  make migrate     - Run database migrations"
	@echo "  make revision    - Create new migration revision"
	@echo "  make run         - Run the application locally"

# Install production dependencies
install:
	pip install -e .

# Install all dependencies including dev
dev:
	pip install -e ".[dev]"

# Run tests
test:
	pytest tests/ -v --cov=src/aiops_agent_executor --cov-report=term-missing

# Run tests with coverage report
test-cov:
	pytest tests/ -v --cov=src/aiops_agent_executor --cov-report=html
	@echo "Coverage report generated in htmlcov/"

# Run linting
lint:
	ruff check src/ tests/
	mypy src/

# Format code
format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Start Docker containers (production-like)
docker-up:
	docker-compose up -d

# Stop Docker containers
docker-down:
	docker-compose down

# Start development Docker containers with hot reload
docker-dev:
	docker-compose -f docker-compose.dev.yml up

# Run database migrations
migrate:
	alembic upgrade head

# Create new migration revision
revision:
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

# Rollback last migration
rollback:
	alembic downgrade -1

# Run the application locally
run:
	uvicorn aiops_agent_executor.main:app --host 0.0.0.0 --port 8000 --reload

# Check if database is ready
db-check:
	@python -c "from aiops_agent_executor.db.session import engine; print('Database connection OK')" 2>/dev/null || echo "Database not available"
