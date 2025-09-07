# Use the official Python image.
FROM python:3.11-slim-bookworm
WORKDIR /app

# Install system dependencies including Chrome and ChromeDriver.
RUN apt-get update && apt-get install -y \
    cron curl wget gnupg unzip && \
    # Add Chrome repository
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    # Install Chrome
    apt-get install -y google-chrome-stable && \
    # Install ChromeDriver
    CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | awk -F. '{print $1}') && \
    wget -q -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}/chromedriver_linux64.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    rm /tmp/chromedriver.zip && \
    chmod +x /usr/local/bin/chromedriver && \
    # Cleanup
    apt-get clean && \
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