# Use lightweight official Python runtime
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy scheduler source files
COPY config.py scheduler.py ./

# Set environment variable defaults
ENV PING_INTERVAL_MIN=10
ENV PING_INTERVAL_MAX=14

# Run scheduler service
CMD ["python", "scheduler.py"]
