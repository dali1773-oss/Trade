"""Verifica che l'hook di Claude Code blocchi l'accesso ai segreti."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "protect_secrets.py"


def run_hook(tool_name, tool_input):
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode


@pytest.mark.parametrize(
    "tool, tool_input",
    [
        ("Read", {"file_path": "/Users/x/tradd/Trade/.env"}),
        ("Read", {"file_path": ".env.local"}),
        ("Edit", {"file_path": "/Users/x/.trade-secrets/hmac.key"}),
        ("Read", {"file_path": "/Users/x/.config/solana/id.json"}),
        ("Read", {"file_path": "wallet-keypair.json"}),
        ("Read", {"file_path": "/Users/x/.ssh/id_ed25519"}),
        ("Bash", {"command": "cat .env"}),
        ("Bash", {"command": "grep KEY ./.env"}),
        ("Bash", {"command": "solana transfer abc 1"}),
        ("Bash", {"command": "solana-keygen new"}),
        ("Bash", {"command": "ls ~/.trade-secrets"}),
        ("Bash", {"command": "printenv"}),
        ("Bash", {"command": "git push --force origin main"}),
    ],
)
def test_blocks_sensitive_access(tool, tool_input):
    assert run_hook(tool, tool_input) == 2


@pytest.mark.parametrize(
    "tool, tool_input",
    [
        ("Read", {"file_path": "README.md"}),
        ("Read", {"file_path": ".env.example"}),
        ("Edit", {"file_path": "src/trade/modes.py"}),
        ("Bash", {"command": "uv run pytest"}),
        ("Bash", {"command": "cat .env.example"}),
        ("Bash", {"command": "git status"}),
    ],
)
def test_allows_normal_work(tool, tool_input):
    assert run_hook(tool, tool_input) == 0


def test_invalid_input_is_blocked():
    result = subprocess.run(
        [sys.executable, str(HOOK)], input="non json", capture_output=True, text=True, check=False
    )
    assert result.returncode == 2
