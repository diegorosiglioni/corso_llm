FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home assistente
WORKDIR /app

# Prima le dipendenze: il livello resta in cache finché requirements.txt non cambia.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY assistente/ assistente/

USER assistente
CMD ["python", "-m", "assistente"]
