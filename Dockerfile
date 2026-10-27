# Base image with Python 3.11 slim
FROM python:3.11-slim

# Install system dependencies: FFmpeg, fontconfig, and standard TrueType fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fontconfig \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for high-speed package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy dependency configuration
COPY pyproject.toml .

# Install dependencies using uv into system environment
RUN uv pip install --system -r pyproject.toml

# Copy application source code
COPY app/ ./app/
COPY .env.example ./.env

# Create directories for persistent media storage and scratch rendering
RUN mkdir -p /app/storage /app/temp_renders

# Expose API port
EXPOSE 8000

# Default entry point
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
