"""Lettura delle impostazioni locali (file .env nella cartella del progetto).

Regola: i valori segreti non vengono mai stampati né scritti nei log.
Il file viene letto solo dal programma; Claude non lo apre.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_FILE = Path(".env")


def load_settings(path: Path = DEFAULT_FILE) -> dict[str, str]:
    """Legge righe NOME=valore. Ignora righe vuote, commenti e valori vuoti."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if value:
            values[name.strip()] = value
    return values


def redact(text: str, secrets: list[str]) -> str:
    """Sostituisce ogni segreto con *** (per messaggi d'errore sicuri)."""
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return text
