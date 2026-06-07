# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy project files needed for dependency resolution
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Install dependencies with all extras (frozen lockfile)
RUN uv sync --frozen --all-extras --no-dev

# --- Runtime stage ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the installed virtualenv and source from the builder
COPY --from=builder /app /app

# Add the venv to PATH so `opp` is on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Default: show help
ENTRYPOINT ["opp"]
CMD ["--help"]
