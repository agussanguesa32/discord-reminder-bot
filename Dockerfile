FROM python:3.12-slim

WORKDIR /app

# Create non-root user so the data volume is owned consistently
RUN useradd -m -u 1000 botuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=botuser:botuser . .

# Ensure data directory exists with correct ownership before switching user
RUN mkdir -p /app/data && chown botuser:botuser /app/data

USER botuser

CMD ["python", "bot.py"]
