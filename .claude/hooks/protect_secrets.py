#!/usr/bin/env python3
"""Hook PreToolUse di Claude Code: blocca l'accesso ai segreti del progetto.

Riceve su stdin il JSON della chiamata allo strumento. Esce con codice 2
(blocco) se la chiamata tocca file o comandi sensibili, altrimenti 0.
Solo libreria standard, compatibile con il Python 3.9 di macOS.
"""
import json
import re
import sys

# Percorsi sensibili (confronto sul percorso normalizzato).
PATH_PATTERNS = [
    r"(^|/)\.env$",
    r"(^|/)\.env\.(?!example$)[^/]+$",
    r"(^|/)\.trade-secrets(/|$)",
    r"(^|/)\.config/solana(/|$)",
    r"(^|/)\.ssh(/|$)",
    r"keypair[^/]*\.json$",
    r"(^|/)secrets(/|$)",
]

# Comandi shell vietati o che citano percorsi sensibili.
COMMAND_PATTERNS = [
    r"\bsolana\s+transfer\b",
    r"\bsolana-keygen\b",
    r"\bspl-token\s+transfer\b",
    r"\.trade-secrets",
    r"\.config/solana",
    r"keypair[^\s]*\.json",
    r"(^|[\s/'\"=<])\.env(?!\.example)(\b|$)",
    r"\bprintenv\b",
    r"\bgit\s+push\s+(-f|--force)\b",
]


def is_blocked(payload):
    """Restituisce il motivo del blocco, oppure None se la chiamata è ammessa."""
    tool_input = payload.get("tool_input") or {}
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str):
            norm = value.replace("\\", "/")
            for pattern in PATH_PATTERNS:
                if re.search(pattern, norm):
                    return "percorso protetto: %s" % value
    command = tool_input.get("command")
    if isinstance(command, str):
        for pattern in COMMAND_PATTERNS:
            if re.search(pattern, command):
                return "comando protetto (regola %s)" % pattern
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        # Input illeggibile: per sicurezza si blocca.
        print("Bloccato: input del hook non valido", file=sys.stderr)
        return 2
    reason = is_blocked(payload)
    if reason:
        print("Bloccato dalla politica di sicurezza di Trade: %s. "
              "I segreti non devono mai essere letti da Claude." % reason,
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
