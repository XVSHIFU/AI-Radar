"""Explicit loading of the packaged contract; no ancestor/home/plugin discovery."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .research_guard import ALLOWED_TOOLS, canonical
from .research_tools import load_research_skills

LIMITS = {
    "ip_questions": 20,
    "ip_window_seconds": 172800,
    "model_calls_per_run": 3,
    "business_tool_calls_per_run": 4,
    "skill_loads_per_run": 2,
    "python_calls_per_run": 1,
    "input_tokens_per_run": 24000,
    "output_tokens_per_run": 4800,
    "run_deadline_seconds": 90,
    "automatic_paid_retries": 0,
    "global_concurrent_runs": 2,
}
PYTHON_LIMITS = {
    "network": "none",
    "read_only_rootfs": True,
    "non_root": True,
    "drop_all_capabilities": True,
    "no_new_privileges": True,
    "host_mounts": False,
    "docker_socket": False,
    "cpu_cores": 1,
    "memory_mib": 256,
    "pids": 32,
    "execution_seconds": 10,
    "job_deadline_seconds": 30,
    "scratch_mib": 32,
    "input_bytes": 2097152,
    "dataset_rows": 10000,
    "code_bytes": 16384,
    "stdout_bytes": 65536,
    "artifact_bytes": 1048576,
    "artifact_types": ["application/json", "text/csv", "image/png"],
    "requires_isolation_verification": True,
    "guest_tasks": 2,
}

FORBIDDEN = {
    "shell",
    "host_files",
    "arbitrary_network",
    "database_write",
    "admin_api",
    "container_control",
    "install_packages",
    "install_plugins",
    "self_modify",
    "spawn_agents",
    "background_jobs",
}


@dataclass(frozen=True)
class ResearchPolicy:
    system: str
    skills: dict[str, dict[str, str]]
    contract: dict[str, Any]
    digest: str

    @classmethod
    def load(cls, root: Path) -> ResearchPolicy:
        root = root.resolve(strict=True)
        for name in ("policy.json", "SYSTEM.md"):
            path = root / name
            if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
                raise ValueError("policy must be a packaged file")
        raw = (root / "policy.json").read_bytes()
        system = (root / "SYSTEM.md").read_bytes()
        if len(raw) > 16384 or len(system) > 8192:
            raise ValueError("research policy size limit")
        contract = json.loads(raw)
        if not isinstance(contract, dict):
            raise ValueError("research policy must be an object")
        limits = contract.get("limits")
        memory = contract.get("memory")
        python = contract.get("python")
        forbidden = contract.get("forbidden_capabilities")
        names = contract.get("tools")
        if (
            not isinstance(limits, dict)
            or not isinstance(memory, dict)
            or not isinstance(python, dict)
            or not isinstance(forbidden, list)
            or not isinstance(names, list)
            or any(not isinstance(value, str) for value in [*forbidden, *names])
        ):
            raise ValueError("invalid research policy structure")
        if (
            contract.get("runtime") != "pi-agent-core"
            or contract.get("default_allow") is not False
            or limits != LIMITS
            or any(type(value) is not int for value in limits.values())
            or any(
                memory.get(key) is not False
                for key in ("shared_user_memory", "ip_is_identity", "policy_writable_by_agent")
            )
            or type(memory.get("summary_tokens")) is not int
            or not FORBIDDEN.issubset(contract.get("forbidden_capabilities", []))
            or set(contract.get("tools", [])) != ALLOWED_TOOLS | {"run_python"}
            or type(python.get("enabled")) is not bool
            or canonical({key: value for key, value in python.items() if key != "enabled"})
            != canonical(PYTHON_LIMITS)
            or contract.get("memory", {}).get("server_persistent_transcripts") is not False
            or contract.get("memory", {}).get("summary_tokens") != 1200
        ):
            raise ValueError("research policy does not match the implemented safety gates")
        digest = hashlib.sha256(raw + b"\0" + system).hexdigest()
        return cls(
            system.decode("utf-8"),
            load_research_skills(root, python_enabled=python["enabled"]),
            contract,
            digest,
        )


ANSWER_CONTRACT = """
Use the supplied scope and tools. You have at most 3 model turns and 4 business tool calls.
On the last model turn, summarize available results; no tools remain.
Write the answer directly as readable Markdown, never JSON or a reasoning trace.
For every event fact or database result cite its returned citation_index as [number].
Do not cite UUIDs, invent URLs, or use a previous conversation's citation numbers.
Dataset citations support recorded counts and comparisons, not external event facts.
For greetings or a request to clarify the research scope, a short answer needs no citation.
If there is no source for a factual answer, explain the gap and suggest a narrower question.
Only the last model turn becomes the final answer. Earlier text is a replaceable draft.
""".strip()
