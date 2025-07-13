FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create volume directory with full permissions
RUN mkdir -p /app/data && chmod 777 /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV DB_PATH=/app/data/transit-calendar.sqlite
ENV LOG_FILE=/app/data/transit-calendar.log
ENV PYTHONUNBUFFERED=1

# Command to run with intentional delay to ensure filesystem is ready
CMD ["sh", "-c", "sleep 2 && python -m script.main"]