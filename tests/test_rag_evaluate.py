"""Evaluation on questions with an expected source: outcome per question, Markdown report, and the
questions file."""

import pytest
from qdrant_client import QdrantClient

from conftest import FakeEmbedder
from rag import evaluate as evaluate_module
from rag.config import load_config
from rag.corpus import Recipe
from rag.evaluate import (
    DEFAULT_QUESTIONS, Question, evaluate_question, format_report, load_questions,
)
from rag.ingest import run_ingest
from rag.search import SearchResult
from rag.store import ChunkPoint, ensure_collection, point_id, upsert_points

VALID = {"LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1", "EMBEDDING_MODEL": "modello-scelto"}


def result(n, score, rank):
    return SearchResult(rank, score, n, f"R{n}", "Zuppe", 0, "t")


def test_found_absent_and_no_answer():
    found = evaluate_question(Question("q", (455, 456)), [result(7, 0.8, 1), result(456, 0.75, 2)])
    assert (found.position, found.source_score, found.best_score) == (2, 0.75, 0.8)
    absent = evaluate_question(Question("q", (208,)), [result(7, 0.72, 1)])
    assert (absent.position, absent.source_score, absent.best_score) == (None, None, 0.72)
    nothing = evaluate_question(Question("q", (208,)), [])
    assert (nothing.position, nothing.source_score, nothing.best_score) == (None, None, None)


def test_first_chunk_of_an_expected_recipe_counts():
    outcome = evaluate_question(Question("q", (89,)), [result(7, 0.9, 1), result(89, 0.8, 2), result(89, 0.85, 3)])
    assert (outcome.position, outcome.source_score) == (2, 0.8)


def test_report():
    outcomes = [evaluate_question(Question("Farina?", (89,)), [result(89, 0.777, 1)]),
                evaluate_question(Question("Vino?", (208,)), [result(7, 0.724, 1)]),
                evaluate_question(Question("Cacciucco?", (455, 456)), [result(456, 0.7, 1)]),
                evaluate_question(Question("Tiramisù?", ()), [result(3, 0.735, 1)])]
    text = format_report({"modello": "m", "k": "5"}, outcomes)
    assert text.splitlines()[:2] == ["- **modello:** m", "- **k:** 5"]
    assert "| Domanda | Fonte attesa | Posizione | Score fonte | Score migliore |" in text
    assert "| Farina? | 89 | 1 | 0,777 | 0,777 |" in text
    assert "| Vino? | 208 | assente | — | 0,724 |" in text
    assert "| Cacciucco? | 455, 456 | 1 | 0,700 | 0,700 |" in text
    assert "| Tiramisù? | — | — | — | 0,735 |" in text
    assert text.rstrip().endswith("Fonte attesa trovata in 2 casi su 3.")
    assert format_report({"modello": "m", "k": "5"}, outcomes) == text      # reproducible


def test_pipe_in_a_question_does_not_break_the_table():
    outcome = evaluate_question(Question("Pollo | fritto?", (1,)), [])
    assert "| Pollo \\| fritto? | 1 | assente | — | — |" in format_report({}, [outcome])


@pytest.mark.parametrize("content", [
    '[{"question": "q"}]', '[{"expected": [1]}]', '[{"question": "", "expected": []}]',
    '[{"question": "q", "expected": [791]}]', '[{"question": "q", "expected": [0]}]',
    '[{"question": "q", "expected": ["89"]}]', '[{"question": "q", "expected": 89}]',
])
def test_invalid_questions(tmp_path, content):
    path = tmp_path / "q.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="domanda 1"):
        load_questions(path)


def test_position_of_the_invalid_question(tmp_path):
    path = tmp_path / "q.json"
    path.write_text('[{"question": "a", "expected": [1]}, {"question": "b", "expected": [999]}]',
                    encoding="utf-8")
    with pytest.raises(ValueError, match="domanda 2"):
        load_questions(path)


@pytest.mark.parametrize("content", ["non json", '{"question": "q", "expected": []}', "[]"])
def test_invalid_file(tmp_path, content):
    path = tmp_path / "q.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="q.json"):
        load_questions(path)


def test_missing_file(tmp_path):
    with pytest.raises(ValueError, match="manca.json"):
        load_questions(tmp_path / "manca.json")


def test_shipped_questions_are_valid():
    questions = load_questions(DEFAULT_QUESTIONS)
    assert len(questions) >= 9 and sum(not q.expected for q in questions) >= 1
    assert Question("Quanta farina serve per 400 grammi di patate negli gnocchi?", (89,)) in questions


@pytest.fixture
def offline(monkeypatch, qdrant):
    monkeypatch.setattr(qdrant, "close", lambda: None)
    monkeypatch.setattr(evaluate_module, "check_embedding_model", lambda *a, **k: None)
    monkeypatch.setattr(evaluate_module, "connect", lambda url: qdrant)
    monkeypatch.setattr(evaluate_module, "create_embedder", lambda config: FakeEmbedder())
    return qdrant


def test_main_prints_a_reproducible_table(tmp_path, capsys, offline):
    recipes = [Recipe(1, "Pollo fritto", "Fritti", "Pollo fritto nell'olio."),
               Recipe(2, "Torta", "Torte e dolci al cucchiaio", "Torta di mandorle.")]
    run_ingest(load_config(VALID), recipes, offline, FakeEmbedder())
    path = tmp_path / "q.json"
    path.write_text('[{"question": "pollo fritto", "expected": [1]}, {"question": "tiramisù", "expected": []}]',
                    encoding="utf-8")
    assert evaluate_module.main(["--questions", str(path), "--k", "2"], VALID) == 0
    first = capsys.readouterr().out
    assert evaluate_module.main(["--questions", str(path), "--k", "2"], VALID) == 0
    assert capsys.readouterr().out == first
    assert first.splitlines()[:9] == [
        "- **modello:** modello-scelto", "- **collezione:** recipes", "- **punti:** 2",
        "- **strategia:** paragraph", "- **dimensione:** 1200", "- **overlap:** 200",
        "- **intestazione dei chunk:** title_chapter", "- **k:** 2", "- **filtro dosi:** no",
    ]
    assert "| pollo fritto | 1 | 1 |" in first and first.rstrip().endswith("Fonte attesa trovata in 1 casi su 1.")


def questions_file(tmp_path, content):
    path = tmp_path / "q.json"
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_header_from_the_index_not_the_session(tmp_path, capsys, offline):
    config = load_config({**VALID, "CHUNK_STRATEGY": "window", "CHUNK_SIZE": "300", "CHUNK_OVERLAP": "50"})
    run_ingest(config, [Recipe(1, "Pollo fritto", "Fritti", "Pollo fritto nell'olio.")], offline, FakeEmbedder())
    path = questions_file(tmp_path, '[{"question": "pollo", "expected": [1]}]')
    assert evaluate_module.main(["--questions", path], VALID) == 0
    out = capsys.readouterr().out
    assert "- **strategia:** window\n- **dimensione:** 300\n- **overlap:** 50\n" in out


def test_header_falls_back_to_the_configuration(tmp_path, capsys, offline):
    text = "Pollo fritto nell'olio."
    ensure_collection(offline, "recipes", FakeEmbedder.DIMENSION, "modello-scelto")
    upsert_points(offline, "recipes", [ChunkPoint(point_id("Ricettario.txt", 1, 0), FakeEmbedder.vector(text), {
        "source": "Ricettario.txt", "recipe_number": 1, "title": "Pollo fritto", "chapter": "Fritti",
        "chunk_index": 0, "text": text, "embedding_model": "modello-scelto", "has_doses": False,
    })])
    path = questions_file(tmp_path, '[{"question": "pollo", "expected": [1]}]')
    assert evaluate_module.main(["--questions", path], VALID) == 0
    out = capsys.readouterr().out
    assert ("- **strategia:** paragraph (dalla configurazione)\n"
            "- **dimensione:** 1200 (dalla configurazione)\n"
            "- **overlap:** 200 (dalla configurazione)\n"
            "- **intestazione dei chunk:** none (indice precedente alla modifica B)\n") in out


def test_header_of_an_index_after_modification_a(tmp_path, capsys, offline):
    text = "Pollo fritto nell'olio."
    ensure_collection(offline, "recipes", FakeEmbedder.DIMENSION, "modello-scelto")
    upsert_points(offline, "recipes", [ChunkPoint(point_id("Ricettario.txt", 1, 0), FakeEmbedder.vector(text), {
        "source": "Ricettario.txt", "recipe_number": 1, "title": "Pollo fritto", "chapter": "Fritti",
        "chunk_index": 0, "text": text, "embedding_model": "modello-scelto", "has_doses": False,
        "chunk_strategy": "window", "chunk_size": 300, "chunk_overlap": 50,
    })])
    path = questions_file(tmp_path, '[{"question": "pollo", "expected": [1]}]')
    assert evaluate_module.main(["--questions", path], VALID) == 0
    out = capsys.readouterr().out
    assert ("- **strategia:** window\n- **dimensione:** 300\n- **overlap:** 50\n"
            "- **intestazione dei chunk:** none (indice precedente alla modifica B)\n") in out


def test_main_with_doses(tmp_path, capsys, offline):
    recipes = [Recipe(1, "Pollo fritto", "Fritti", "Pollo fritto nell'olio.\n\nPollo, N. 1.\nOlio, grammi 100."),
               Recipe(2, "Pollo lesso", "Lesso", "Pollo lesso nel brodo.")]
    run_ingest(load_config(VALID), recipes, offline, FakeEmbedder())
    path = questions_file(tmp_path, '[{"question": "pollo fritto", "expected": [1]}, '
                                    '{"question": "pollo lesso", "expected": [2]}]')
    assert evaluate_module.main(["--questions", path, "--doses"], VALID) == 0
    out = capsys.readouterr().out
    assert "- **filtro dosi:** sì" in out
    assert "| pollo fritto | 1 | 1 |" in out and "| pollo lesso | 2 | assente |" in out
    assert evaluate_module.main(["--questions", path], VALID) == 0
    assert "| pollo lesso | 2 | 1 |" in capsys.readouterr().out


def test_main_invalid_questions_file(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(evaluate_module, "check_embedding_model", lambda *a, **k: None)
    monkeypatch.setattr(evaluate_module, "connect", lambda url: QdrantClient(":memory:"))
    assert evaluate_module.main(["--questions", str(tmp_path / "manca.json")], VALID) == 1
    assert "manca.json" in capsys.readouterr().err


def test_main_k_out_of_range(capsys):
    assert evaluate_module.main(["--k", "21"], VALID) == 1
    assert "20" in capsys.readouterr().err
