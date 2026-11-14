# Agente come servizio HTTP (python -m assistant.service), con il server MCP stdio come
# sottoprocesso nello stesso container. La stessa immagine avvia anche la CLI (servizio assistant
# di compose.yaml, comando python -m assistant). Contesto di build: la radice della repository.

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

# Cartella delle note: il volume notes-data, alla prima creazione, ne eredita il proprietario.
RUN mkdir /app/data && chown app /app/data

# Raggiungibile da fuori del container (il predefinito del servizio è 127.0.0.1).
ENV AGENT_HOST=0.0.0.0

USER app
EXPOSE 8000
CMD ["python", "-m", "assistant.service"]
