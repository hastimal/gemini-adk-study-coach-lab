# Dockerfile for Gemini ADK Study Coach Lab Workshop UI

FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8501

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv using official installer
COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /uvx /bin/

# Copy dependency definition files
COPY pyproject.toml uv.lock ./

# Install locked dependencies into system environment
RUN uv export --frozen --no-dev --no-editable --no-hashes -o requirements.txt \
    && sed -i '/^\.$/d' requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source code and assets
COPY src/ /app/src/
COPY ui/ /app/ui/

# Set Python path to find app root (ui package) and src package
ENV PYTHONPATH=/app:/app/src

# Create a non-root application user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose Streamlit default port and Prometheus metrics port
EXPOSE 8501 8001

# Configure healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Launch Streamlit application with observability initialized
ENTRYPOINT ["python", "ui/server.py"]
