FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create volume for data
VOLUME /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV DB_PATH=/app/data/transit-calendar.sqlite
ENV LOG_FILE=/app/data/transit-calendar.log
ENV PYTHONUNBUFFERED=1

# Run as non-root user
RUN addgroup --system appgroup && adduser --system appuser --ingroup appgroup
RUN chown -R appuser:appgroup /app
USER appuser

# Command to run
CMD ["python", "-m", "script.main"]