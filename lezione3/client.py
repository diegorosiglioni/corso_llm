"""Client minimo per il server locale di LM Studio.

Chat da terminale: la domanda si scrive da tastiera, la conversazione
resta in memoria finche' il programma e' aperto. La risposta del modello
compare in streaming, mentre viene generata; il ragionamento resta nascosto.
Uscire con "esci" oppure con una riga vuota.
"""

import json
import os

import requests
from dotenv import load_dotenv

# --- Configurazione -------------------------------------------------------
load_dotenv()
base_url = os.environ["LM_BASE_URL"]
model = os.environ["LM_MODEL"]

# --- Messaggi -------------------------------------------------------------
messages = [
    {
        "role": "system",
        "content": "Sei un assistente utile. Rispondi in italiano, in modo chiaro e conciso.",
    }
]

print(f"Chat con {model}. Scrivi 'esci' o premi Invio su una riga vuota per uscire.")

while True:
    domanda = input("\nTu: ").strip()
    if domanda == "" or domanda.lower() == "esci":
        break
    messages.append({"role": "user", "content": domanda})

    # --- Payload ----------------------------------------------------------
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
        "reasoning_effort": "medium",
        "stream": True,
    }

    # --- Chiamata ---------------------------------------------------------
    response = None
    try:
        response = requests.post(
            f"{base_url}/chat/completions", json=payload, timeout=120, stream=True
        )
        response.raise_for_status()

        # Lo stream arriva come righe "data: {...}" e termina con "data: [DONE]".
        # Il ragionamento (reasoning_content) non viene mostrato: si stampa solo
        # la risposta (content), man mano che arriva.
        risposta = ""
        print("\nGemma: ", end="", flush=True)
        for riga in response.iter_lines():
            riga = riga.decode("utf-8")
            if not riga.startswith("data: "):
                continue
            dati = riga[len("data: "):]
            if dati == "[DONE]":
                break
            delta = json.loads(dati)["choices"][0]["delta"]

            if delta.get("content"):
                print(delta["content"], end="", flush=True)
                risposta += delta["content"]

        print()
        # Nella cronologia va solo la risposta, non il ragionamento.
        messages.append({"role": "assistant", "content": risposta})
    except requests.exceptions.Timeout:
        print("Attesa scaduta: controllare server, carico e tempi.")
        messages.pop()
    except requests.exceptions.ConnectionError:
        print("Connessione fallita: controllare server, URL e porta.")
        messages.pop()
    except requests.exceptions.HTTPError:
        print("Errore HTTP:", response.status_code, response.text)
        messages.pop()
