FROM python:3.13.18-slim-trixie@sha256:ae14d4ce8771606477a81446e7ef429edd6762305fc50c84507c1041fa8285d1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home assistente
WORKDIR /app

# Prima le dipendenze: il livello resta in cache finché requirements.txt e constraints.txt non cambiano.
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY assistente/ assistente/

USER assistente
CMD ["python", "-m", "assistente"]
