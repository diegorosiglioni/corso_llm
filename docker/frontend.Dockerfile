# Front-end (python -m frontend): pagina statica e /config.js con l'indirizzo del back-end visto
# dal browser (BACKEND_URL). Usa la configurazione del pacchetto assistant, quindi lo copia.
# Contesto di build: la radice della repository.

# Le prime istruzioni sono identiche nei tre Dockerfile: il livello delle dipendenze si costruisce
# una volta e si riusa.
FROM python:3.13.18-slim-trixie@sha256:ae14d4ce8771606477a81446e7ef429edd6762305fc50c84507c1041fa8285d1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 1000 app
WORKDIR /app

# Prima le dipendenze: il livello resta in cache finché requirements.txt e constraints.txt non cambiano.
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY assistant/ assistant/
COPY frontend/ frontend/

# Raggiungibile da fuori del container (il predefinito del servizio è 127.0.0.1).
ENV FRONTEND_HOST=0.0.0.0

USER app
EXPOSE 8080
CMD ["python", "-m", "frontend"]
