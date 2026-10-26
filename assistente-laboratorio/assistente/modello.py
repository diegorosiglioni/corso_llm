"""Collegamento al modello servito da LM Studio tramite l'API compatibile OpenAI."""

from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from assistente.config import Configurazione


def crea_modello(config: Configurazione, strumenti: list[BaseTool]) -> Runnable:
    return ChatOpenAI(
        base_url=config.base_url,
        model=config.modello,
        api_key="lm-studio",  # segnaposto: LM Studio non richiede chiavi
        temperature=0,  # risposte più ripetibili e tool calling più stabile
        timeout=120,  # il primo caricamento di un modello locale può essere lento
        max_retries=1,  # con LM Studio spento l'errore arriva in pochi secondi
    ).bind_tools(strumenti)
