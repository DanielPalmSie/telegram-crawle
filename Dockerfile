FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system crawler \
    && adduser --system --ingroup crawler crawler

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /app/session \
    && chown -R crawler:crawler /app

USER crawler

CMD ["python", "-m", "app.main"]
