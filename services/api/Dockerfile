# Base image optimized for Python 3.12
FROM python:3.12-slim

# Set environment variables for non-interactive installs and Python optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000

# Set the working directory
WORKDIR /app

# Install system dependencies required for uv and Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (blazing fast Python package installer)
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# Copy the pyproject.toml first to cache dependency installation
COPY pyproject.toml ./

# Install Python dependencies globally via uv (Railway provides an isolated container anyway)
RUN uv pip install --system .

# Install Playwright browsers and their system dependencies (Chromium only to save space)
RUN playwright install --with-deps chromium

# Copy the rest of the application codebase
COPY . .

# Expose the Railway port
EXPOSE $PORT

# Run the FastAPI server via Uvicorn (Railway automatically sets the $PORT environment variable)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
