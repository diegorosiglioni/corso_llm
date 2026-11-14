"""Dockerfiles of the three services, checked as text: no image is built (spec of Step 9, §7)."""

import importlib.util
import json
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
