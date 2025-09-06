# Use the official Python image.
FROM python:3.11-slim-bookworm
WORKDIR /app

# Install system dependencies.
RUN apt-get update && apt-get install -y \
    cron curl wget gnupg && \
    rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install Python packages.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files.
COPY backend /app/backend
COPY frontend /app/frontend

# Make cron scripts executable
RUN chmod +x /app/backend/cron_job_*.sh

# Add cron job
COPY backend/cron_jobs /etc/cron.d/hanaview-cron
RUN chmod 0644 /etc/cron.d/hanaview-cron

# Start services.
CMD cron && cd /app/backend && uvicorn main:app --host 0.0.0.0 --port 8000
