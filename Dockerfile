FROM python:3.12-slim

ARG LOCAL_WHISPER=0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt requirements-local.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$LOCAL_WHISPER" = "1" ]; then pip install --no-cache-dir -r requirements-local.txt; fi

COPY app ./app
RUN useradd --create-home --uid 1000 bot && mkdir -p logs data && chown -R bot:bot /app
USER bot

EXPOSE 8787
CMD ["sh", "-c", "uvicorn --factory app.main:app_factory --host 0.0.0.0 --port ${PORT:-8787} --workers 1 --no-access-log"]
