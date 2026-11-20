"""Configuration of the recipe pipeline (lesson 7): required variables, defaults, invalid values."""

import re
from pathlib import Path

import pytest

from rag.config import ConfigError, load_config

VALID = {"LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1", "EMBEDDING_MODEL": "modello-scelto"}


def test_defaults():
    config = load_config(VALID)
    assert (config.base_url, config.embedding_model) == ("http://127.0.0.1:1234/v1", "modello-scelto")
    assert (config.qdrant_url, config.collection, config.corpus_file) == (
        "http://127.0.0.1:6333", "recipes", "data/Ricettario.txt")
    assert (config.chunk_strategy, config.chunk_size, config.chunk_overlap, config.batch_size) == (
        "paragraph", 1200, 200, 32)
    assert config.chunk_header == "title_chapter"
    assert config.log_level == "INFO"


def test_values_from_the_environment():
    config = load_config({
        **VALID, "QDRANT_URL": "http://qdrant.test:6333", "QDRANT_COLLECTION": "prova",
        "CORPUS_FILE": "altro.txt", "CHUNK_STRATEGY": "window", "CHUNK_SIZE": "500",
        "CHUNK_OVERLAP": "0", "EMBEDDING_BATCH_SIZE": "8", "LOG_LEVEL": "debug",
    })
    assert (config.qdrant_url, config.collection, config.corpus_file) == (
        "http://qdrant.test:6333", "prova", "altro.txt")
    assert (config.chunk_strategy, config.chunk_size, config.chunk_overlap, config.batch_size) == (
        "window", 500, 0, 8)
    assert config.log_level == "DEBUG"


def test_required_variables_are_all_listed():
    with pytest.raises(ConfigError) as error:
        load_config({"EMBEDDING_MODEL": "  "})
    assert "LMSTUDIO_BASE_URL" in str(error.value) and "EMBEDDING_MODEL" in str(error.value)


@pytest.mark.parametrize("name, value", [
    ("CHUNK_STRATEGY", "sentence"), ("CHUNK_SIZE", "99"), ("CHUNK_SIZE", "mille"),
    ("CHUNK_OVERLAP", "-1"), ("CHUNK_OVERLAP", "601"), ("EMBEDDING_BATCH_SIZE", "0"),
    ("QDRANT_URL", "127.0.0.1:6333"), ("LMSTUDIO_BASE_URL", "localhost:1234"), ("LOG_LEVEL", "TRACE"),
    ("CHUNK_HEADER", "titolo"),
])
def test_invalid_values(name, value):
    with pytest.raises(ConfigError, match=name):
        load_config({**VALID, name: value})


def test_chunk_header_values():
    assert load_config({**VALID, "CHUNK_HEADER": " None "}).chunk_header == "none"
    assert load_config({**VALID, "CHUNK_HEADER": "TITLE_CHAPTER"}).chunk_header == "title_chapter"


def test_chunk_header_error_lists_the_allowed_values():
    with pytest.raises(ConfigError) as error:
        load_config({**VALID, "CHUNK_HEADER": "titolo"})
    assert "CHUNK_HEADER deve essere uno tra title_chapter, none, ricevuto 'titolo'." in str(error.value)


def test_overlap_limit_follows_the_size():
    assert load_config({**VALID, "CHUNK_SIZE": "400", "CHUNK_OVERLAP": "200"}).chunk_overlap == 200
    with pytest.raises(ConfigError, match="CHUNK_OVERLAP"):
        load_config({**VALID, "CHUNK_SIZE": "400", "CHUNK_OVERLAP": "201"})


def test_no_import_from_the_other_packages():
    source = "\n".join(p.read_text(encoding="utf-8") for p in Path("rag").glob("*.py"))
    assert source
    assert not re.search(r"^\s*(from|import)\s+(assistant|backend|frontend)\b", source, re.M)
