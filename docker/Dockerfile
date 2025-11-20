FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY database/ ./database/

# Create necessary directories
RUN mkdir -p /data /var/log/signal-controller

# Create non-root user
RUN useradd --create-home --shell /bin/bash signal && \
    chown -R signal:signal /app /data /var/log/signal-controller

# Switch to non-root user
USER signal

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9000/health || exit 1

# Default command
CMD ["python3", "backend/main.py", "private"]
