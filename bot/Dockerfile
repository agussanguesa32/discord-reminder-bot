FROM python:3.12-slim

WORKDIR /app

COPY bot/requirements.txt ./bot/requirements.txt
RUN pip install --no-cache-dir -r bot/requirements.txt

COPY shared/ ./shared/
COPY bot/ ./bot/

ENV PYTHONPATH=/app/bot:/app

CMD ["python", "/app/bot/bot.py"]
