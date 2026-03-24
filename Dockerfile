FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user and switch to it
RUN useradd --no-create-home --shell /bin/false botuser \
    && mkdir -p data \
    && chown -R botuser:botuser /app

USER botuser

ENTRYPOINT ["python", "main.py"]
