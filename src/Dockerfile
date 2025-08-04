FROM python:3.10-slim

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create volume directory with full permissions
RUN mkdir -p /app/data && chmod 777 /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Command to run with intentional delay to ensure filesystem is ready
CMD ["sh", "-c", "sleep 2 && python main.py"]