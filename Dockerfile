# ==============================================================================
# ProfitSense Multi-Stage Production Dockerfile
# Stage 1: Build React 18 + Vite Frontend
# Stage 2: Python 3.11 Runtime with FastAPI, ML Engine, and Telegram Poller
# ==============================================================================

# ----------------- Stage 1: Frontend Build -----------------
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ----------------- Stage 2: Production Python Backend -----------------
FROM python:3.11-slim AS production

# Prevent Python from writing .pyc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install build dependencies for scientific packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python backend dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend source code & pre-trained ML models
COPY backend/ ./backend/

# Copy built frontend assets from Stage 1 into the container
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure data directory exists for persistent SQLite database
RUN mkdir -p /app/backend/data

EXPOSE 8000

# Health check to ensure service is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start FastAPI server via Uvicorn
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
