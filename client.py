"""Client minimo per il server locale di LM Studio.

Chat da terminale: la domanda si scrive da tastiera, la conversazione
resta in memoria finche' il programma e' aperto. Uscire con "esci"
oppure con una riga vuota.
"""

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
        "max_tokens": 1024,
        "reasoning_effort": "none",
        "stream": False,
    }

    # --- Chiamata ---------------------------------------------------------
    response = None
    try:
        response = requests.post(f"{base_url}/chat/completions", json=payload, timeout=120)
        response.raise_for_status()
        risposta = response.json()["choices"][0]["message"]["content"]
        print("\nGemma:", risposta)
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
