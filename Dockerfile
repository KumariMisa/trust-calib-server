# Use a lightweight official Python runtime
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for compiling python packages (like bcrypt)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application files
COPY . .

# Expose port (Northflank dynamically allocates PORT via env)
EXPOSE 8000

ENV PORT=8000
ENV HOST=0.0.0.0

# Start FastAPI application bound to dynamic port
CMD uvicorn app.main:app --host $HOST --port $PORT
