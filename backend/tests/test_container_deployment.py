"""Guard deployment trust boundaries; actual container acceptance is separate."""

import json
from pathlib import Path

import pytest

from radar import container_entry
from radar.config import Settings

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = json.loads((ROOT / "compose.agent.json").read_text(encoding="utf-8"))


@pytest.fixture
def credentials(monkeypatch):
    seen = []

    def read(path):
        seen.append(path.name)
        return "x" * 64

    monkeypatch.setattr(container_entry, "private_value", read)
    return seen


def test_api_uses_frozen_service_identity_and_separate_mounted_credentials(credentials):
    env = container_entry.environment(
        "api",
        {
            "DATABASE_URL": "postgresql://superuser:secret@unapproved/database",
            "DB_HOST": "unapproved",
            "DB_USER": "postgres",
            "LLM_API_KEY": "not-in-container",
            "MODEL_CONFIG_PATH": "/host/model.json",
            "RESEARCH_AGENT_ENABLED": "false",
            "RADAR_RUNTIME_TOKEN": "wrong",
            "HTTP_PROXY": "http://unapproved",
        },
    )
    assert env["DB_USER"] == "radar_api"
    assert env["DB_HOST"] == "db"
    assert "DATABASE_URL" not in env
    assert "LLM_API_KEY" not in env
    assert "HTTP_PROXY" not in env
    assert "RADAR_RUNTIME_TOKEN" not in env
    assert env["MODEL_CONFIG_PATH"] == "/var/lib/radar-model/model.json"
    assert set(credentials) == {"db_password", *container_entry.API_SECRETS.values()}
    # Verify the actual Settings field names rather than only checking strings.
    settings = Settings(_env_file=None, **{key.lower(): value for key, value in env.items()})
    assert settings.public_assistant_secret == "x" * 64
    assert settings.research_runtime_url == "http://pi-runtime:8081"
    assert settings.research_agent_enabled is False


@pytest.mark.parametrize(
    "role", ["worker", "scheduler", "quota-cleaner", "migrate", "register-sources"]
)
def test_background_roles_read_no_model_or_identity_secret(credentials, role):
    env = container_entry.environment(role, {"RESEARCH_AGENT_ENABLED": "true"})
    assert credentials == ["db_password"]
    assert env["RESEARCH_AGENT_ENABLED"] == "false"
    assert "ADMIN_TOKEN" not in env
    assert "PUBLIC_ASSISTANT_SECRET" not in env


def test_unknown_role_never_reads_credentials(credentials):
    with pytest.raises(ValueError):
        container_entry.environment("shell", {})
    with pytest.raises(ValueError):
        container_entry.command("shell")
    assert credentials == []


def test_only_gateway_publishes_loopback_port_and_proxy_trust_is_exact():
    services = COMPOSE["services"]
    assert [name for name, item in services.items() if item.get("ports")] == ["gateway"]
    assert services["gateway"]["ports"][0].startswith("127.0.0.1:")
    command = container_entry.command("api")
    trusted = command[command.index("--forwarded-allow-ips") + 1]
    assert services["gateway"]["networks"]["front"]["ipv4_address"] == trusted
    assert trusted != "*"
    assert command[command.index("--workers") + 1] == "1"


def test_model_runtime_cannot_reach_database_or_mount_host_or_provider_configuration():
    service = COMPOSE["services"]["pi-runtime"]
    assert service["networks"] == ["broker"]
    assert COMPOSE["networks"]["broker"]["internal"] is True
    assert service.get("volumes", []) == []
    assert service["secrets"] == [{"source": "runtime_token", "target": "runtime_token"}]
    assert not service.get("environment")


def test_only_trusted_control_plane_mounts_docker_socket():
    owners = []
    for name, service in COMPOSE["services"].items():
        if any(
            isinstance(mount, dict) and mount.get("target") == "/run/docker.sock"
            for mount in service.get("volumes", [])
        ):
            owners.append(name)
    assert sorted(owners) == ["sandbox-controller", "sandbox-watchdog"]
    for name in owners:
        service = COMPOSE["services"][name]
        assert "database" not in service["networks"]
        assert all(not item["source"].startswith("db_") for item in service["secrets"])


def test_standby_cannot_start_a_writer_and_public_python_is_not_enabled():
    services = COMPOSE["services"]
    assert [name for name, item in services.items() if not item.get("profiles")] == ["db"]
    assert services["api"]["environment"]["RESEARCH_AGENT_ENABLED"] == "false"
    policy = json.loads((ROOT / "agent/research/policy.json").read_text(encoding="utf-8"))
    assert policy["python"]["enabled"] is False
    for service in services.values():
        assert service["read_only"] is True
        assert service["user"] == "10001:10001"
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert "host" != service.get("network_mode")
        assert not service.get("privileged")


def test_same_host_writers_share_external_persistent_lock_volume():
    assert COMPOSE["volumes"]["service_locks"]["external"] is True
    for role in ["api", "worker", "scheduler", "quota-cleaner", "migrate"]:
        assert "service_locks:/run/radar-service-locks" in COMPOSE["services"][role]["volumes"]
