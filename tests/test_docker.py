"""Dockerfiles and compose.yaml, checked without building images (spec of Step 9, §7)."""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

from assistant.config import DEFAULT_AGENT_PORT
from backend.config import DEFAULT_BACKEND_PORT
from frontend.config import DEFAULT_FRONTEND_PORT

ROOT = Path(__file__).resolve().parent.parent
DOCKER_DIR = ROOT / "docker"

# service -> (packages copied besides the requirements, host variable, port, module of CMD)
SERVICES = {
    "agent": (["assistant"], "AGENT_HOST", DEFAULT_AGENT_PORT, "assistant.service"),
    "backend": (["assistant", "backend"], "BACKEND_HOST", DEFAULT_BACKEND_PORT, "backend"),
    "frontend": (["assistant", "frontend"], "FRONTEND_HOST", DEFAULT_FRONTEND_PORT, "frontend"),
}

# Instructions shared by the three files, in this order: the dependency layer is built once.
COMMON_PREFIX = 6


def instructions(path: Path) -> list[tuple[str, str]]:
    """(INSTRUCTION, arguments) of a Dockerfile, with comments removed and continuations joined."""
    result: list[tuple[str, str]] = []
    pending = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line[:-1].strip() + " "
            continue
        line = pending + line
        pending = ""
        keyword, _, arguments = line.partition(" ")
        result.append((keyword.upper(), " ".join(arguments.split())))
    assert not pending, f"{path.name}: continuazione senza fine"
    return result


def dockerfile(service: str) -> list[tuple[str, str]]:
    return instructions(DOCKER_DIR / f"{service}.Dockerfile")


def values(steps: list[tuple[str, str]], keyword: str) -> list[str]:
    return [arguments for name, arguments in steps if name == keyword]


def test_there_is_one_dockerfile_per_service_and_none_in_the_root():
    assert sorted(path.name for path in DOCKER_DIR.glob("*.Dockerfile")) == [
        "agent.Dockerfile", "backend.Dockerfile", "frontend.Dockerfile",
    ]
    assert not (ROOT / "Dockerfile").exists()


def test_parser_joins_continuations_and_skips_comments(tmp_path):
    path = tmp_path / "x.Dockerfile"
    path.write_text('# commento\nENV A=1 \\\n    B=2\n\ncmd ["python"]\n', encoding="utf-8")
    assert instructions(path) == [("ENV", "A=1 B=2"), ("CMD", '["python"]')]


def test_the_three_images_share_base_and_dependency_layers():
    prefixes = {service: dockerfile(service)[:COMMON_PREFIX] for service in SERVICES}
    agent = prefixes["agent"]
    assert prefixes["backend"] == agent and prefixes["frontend"] == agent
    assert agent[-2:] == [
        ("COPY", "requirements.txt constraints.txt ./"),
        ("RUN", "pip install --no-cache-dir -r requirements.txt"),
    ]


@pytest.mark.parametrize("service", SERVICES)
def test_base_image_is_pinned_by_digest(service):
    (base,) = values(dockerfile(service), "FROM")
    image, _, digest = base.partition("@sha256:")
    assert image.startswith("python:3.13.") and image.endswith("-slim-trixie")
    assert len(digest) == 64 and all(char in "0123456789abcdef" for char in digest)


def test_requirements_use_the_verified_constraints():
    assert "-c constraints.txt" in (ROOT / "requirements.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("service", SERVICES)
def test_only_the_packages_of_the_service_are_copied(service):
    packages, _, _, _ = SERVICES[service]
    copies = values(dockerfile(service), "COPY")
    assert copies == ["requirements.txt constraints.txt ./"] + [
        f"{package}/ {package}/" for package in packages
    ]
    for package in packages:
        assert (ROOT / package / "__init__.py").is_file()


@pytest.mark.parametrize("service", SERVICES)
def test_service_listens_on_all_interfaces_on_its_default_port(service):
    _, host_variable, port, _ = SERVICES[service]
    steps = dockerfile(service)
    assert f"{host_variable}=0.0.0.0" in values(steps, "ENV")
    assert values(steps, "EXPOSE") == [str(port)]


@pytest.mark.parametrize("service", SERVICES)
def test_service_runs_as_a_non_root_user(service):
    steps = dockerfile(service)
    names = [name for name, _ in steps]
    assert values(steps, "USER") == ["app"]
    assert ("RUN", "useradd --create-home --uid 1000 app") in steps
    # Nothing after USER runs as root or changes files: only metadata and the command.
    assert set(names[names.index("USER") + 1:]) <= {"EXPOSE", "CMD"}


@pytest.mark.parametrize("service", SERVICES)
def test_default_command_starts_the_service_module(service):
    _, _, _, module = SERVICES[service]
    (command,) = values(dockerfile(service), "CMD")
    assert json.loads(command) == ["python", "-m", module]
    assert importlib.util.find_spec(module) is not None


def test_agent_image_has_a_notes_folder_owned_by_the_user():
    steps = dockerfile("agent")
    assert "mkdir /app/data && chown app /app/data" in values(steps, "RUN")
    # The folder must exist before USER: the notes-data volume inherits its owner.
    assert steps.index(("RUN", "mkdir /app/data && chown app /app/data")) < steps.index(("USER", "app"))


def test_dockerignore_keeps_secrets_and_local_data_out_of_the_context():
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for entry in (".env", ".venv/", "data/", ".git", "tests/"):
        assert entry in ignored


# compose.yaml, read by Docker itself with `docker compose config` (no daemon, no images).

FAKE_ENV = "POSTGRES_USER=utente\nPOSTGRES_PASSWORD=segreta\nPOSTGRES_DB=chatdb\n"
MAIN_SERVICES = {"frontend", "backend", "agent", "postgres", "qdrant"}


def compose_config(tmp_path: Path, env_text: str = FAKE_ENV, profiles: tuple[str, ...] = ()):
    """`docker compose config --format json` on a copy of compose.yaml with its own .env."""
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("CLI di Docker non installata")
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    (tmp_path / "compose.yaml").write_text(text, encoding="utf-8")
    (tmp_path / ".env").write_text(env_text, encoding="utf-8")
    # Variables interpolated by compose.yaml ($$ excluded): in the shell they would win over .env.
    interpolated = set(re.findall(r"(?<!\$)\$\{(\w+)", text))
    env = {
        name: value for name, value in os.environ.items()
        if name not in interpolated and not name.startswith("COMPOSE_")
    }
    command = [docker, "compose", "--file", str(tmp_path / "compose.yaml")]
    for profile in profiles:
        command += ["--profile", profile]
    return subprocess.run(
        command + ["config", "--format", "json"],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=60,
    )


@pytest.fixture
def compose(tmp_path):
    result = compose_config(tmp_path)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_compose_up_starts_exactly_the_five_services(compose):
    assert set(compose["services"]) == MAIN_SERVICES
    assert set(compose["volumes"]) == {"notes-data", "postgres-data", "qdrant-data"}


def test_cli_is_only_in_the_cli_profile(tmp_path):
    result = compose_config(tmp_path, profiles=("cli",))
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    assert set(services) == MAIN_SERVICES | {"assistant"}
    cli = services["assistant"]
    assert cli["profiles"] == ["cli"]
    assert cli["build"]["dockerfile"] == "docker/agent.Dockerfile"
    assert cli["command"] == ["python", "-m", "assistant"]
    assert cli["environment"]["AGENT_URL"] == "http://agent:8000"
    assert cli["depends_on"]["agent"]["condition"] == "service_healthy"
    assert cli["stdin_open"] and cli["tty"]


@pytest.mark.parametrize("service", SERVICES)
def test_each_service_is_built_from_its_dockerfile(compose, service):
    assert compose["services"][service]["build"]["dockerfile"] == f"docker/{service}.Dockerfile"


def test_agent_and_postgres_are_not_published(compose):
    for service in ("agent", "postgres"):
        assert "ports" not in compose["services"][service]


@pytest.mark.parametrize(
    "service, port", [("backend", DEFAULT_BACKEND_PORT), ("frontend", DEFAULT_FRONTEND_PORT)]
)
def test_backend_and_frontend_are_published_only_on_localhost(compose, service, port):
    (published,) = compose["services"][service]["ports"]
    assert published["host_ip"] == "127.0.0.1"
    assert published["target"] == port and published["published"] == str(port)


@pytest.mark.parametrize("service, variable", [
    ("agent", "AGENT_HOST"), ("backend", "BACKEND_HOST"), ("frontend", "FRONTEND_HOST"),
])
def test_services_listen_on_all_interfaces_even_with_a_local_env(compose, service, variable):
    assert compose["services"][service]["environment"][variable] == "0.0.0.0"


@pytest.mark.parametrize(("mcp", "model", "code"), [
    ("ok", "ok", 0), ("ok", "unavailable", 0), ("unavailable", "ok", 1),
])
def test_agent_healthcheck_follows_mcp(compose, monkeypatch, mcp, model, code):  # R-B3
    test = compose["services"]["agent"]["healthcheck"]["test"]
    assert test[:3] == ["CMD", "python", "-c"]
    body = {"mcp": {"status": mcp}, "model": {"status": model}}
    fake = types.SimpleNamespace(get=lambda url, timeout: types.SimpleNamespace(json=lambda: body))
    monkeypatch.setitem(sys.modules, "httpx", fake)
    with pytest.raises(SystemExit) as stopped:
        exec(test[3], {})
    assert int(stopped.value.code) == code


def test_postgres_uses_the_official_image_a_volume_and_a_healthcheck(compose):
    postgres = compose["services"]["postgres"]
    assert postgres["image"] == "postgres:18.6"
    assert postgres["environment"] == {
        "POSTGRES_USER": "utente", "POSTGRES_PASSWORD": "segreta", "POSTGRES_DB": "chatdb",
    }
    (volume,) = postgres["volumes"]
    assert (volume["type"], volume["source"], volume["target"]) == (
        "volume", "postgres-data", "/var/lib/postgresql",
    )
    test = postgres["healthcheck"]["test"]
    assert test[0] == "CMD-SHELL" and "pg_isready" in test[1]


def test_qdrant_has_a_pinned_image_a_local_port_and_a_volume(compose):
    qdrant = compose["services"]["qdrant"]
    assert qdrant["image"] == "qdrant/qdrant:v1.20.0"
    (published,) = qdrant["ports"]
    assert (published["host_ip"], published["published"], published["target"]) == (
        "127.0.0.1", "6333", 6333,
    )
    (volume,) = qdrant["volumes"]
    assert (volume["type"], volume["source"], volume["target"]) == (
        "volume", "qdrant-data", "/qdrant/storage",
    )


def test_no_service_depends_on_qdrant(compose):
    for name, service in compose["services"].items():
        assert "qdrant" not in service.get("depends_on", {}), name


def test_backend_waits_for_the_database_and_uses_internal_addresses(compose):
    backend = compose["services"]["backend"]
    assert backend["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert backend["depends_on"]["agent"]["condition"] == "service_started"
    environment = backend["environment"]
    assert environment["DATABASE_URL"] == "postgresql://utente:segreta@postgres:5432/chatdb"
    assert environment["AGENT_URL"] == "http://agent:8000"


def test_database_credentials_stay_out_of_the_frontend(compose):
    assert not any("POSTGRES" in name or "DATABASE" in name
                   for name in compose["services"]["frontend"]["environment"])


def test_unset_optional_variables_leave_the_service_defaults(compose):
    # Empty values: the services use their defaults (BACKEND_URL, CORS_ORIGINS, LOG_LEVEL INFO).
    assert compose["services"]["frontend"]["environment"]["BACKEND_URL"] == ""
    assert compose["services"]["backend"]["environment"]["CORS_ORIGINS"] == ""
    assert compose["services"]["backend"]["environment"]["LOG_LEVEL"] == "INFO"


def test_user_and_database_have_defaults(tmp_path):
    result = compose_config(tmp_path, "POSTGRES_PASSWORD=segreta\n")
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    assert services["backend"]["environment"]["DATABASE_URL"] == (
        "postgresql://lab:segreta@postgres:5432/assistente"
    )


def test_missing_password_stops_compose_with_a_message(tmp_path):
    result = compose_config(tmp_path, "POSTGRES_USER=utente\n")
    assert result.returncode != 0
    assert "Manca POSTGRES_PASSWORD nel file .env" in result.stderr


def test_env_example_has_the_postgres_credentials():
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    for name in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        assert any(line.startswith(f"{name}=") for line in lines)


def test_readme_publishes_docker_ports_only_on_localhost():  # R-C1
    lines = [line for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
             if line.lstrip().startswith("docker run")]
    ports = [p for line in lines for p in re.findall(r"-p (\S+)", line)]
    assert ports and all(p.startswith("127.0.0.1:") for p in ports), ports


def test_every_published_port_is_on_localhost(compose):  # R-C1
    for service in compose["services"].values():
        assert all(p["host_ip"] == "127.0.0.1" for p in service.get("ports", [])), service


def test_postgres_is_ready_only_on_tcp_and_the_backend_restarts(compose):  # R-C2
    assert "-h 127.0.0.1" in compose["services"]["postgres"]["healthcheck"]["test"][1]
    assert compose["services"]["backend"]["restart"] == "unless-stopped"


def test_database_password_stays_out_of_agent_and_cli(tmp_path):  # R-B10
    result = compose_config(tmp_path, profiles=("cli",))
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    for name in ("agent", "assistant"):
        assert services[name]["environment"]["POSTGRES_PASSWORD"] == "", name
    assert "segreta" in services["backend"]["environment"]["DATABASE_URL"]

