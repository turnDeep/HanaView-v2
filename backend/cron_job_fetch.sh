#!/bin/bash
LOG_DIR="/app/logs"
echo "$(date): Starting data fetch..." >> $LOG_DIR/cron.log
cd /app/backend
python data_fetcher.py fetch >> $LOG_DIR/fetch.log 2>&1
echo "$(date): Data fetch completed" >> $LOG_DIR/cron.log
