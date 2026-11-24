# CHANGELOG

Formato ispirato a "Keep a Changelog". Date in formato AAAA-MM-GG.

## [Non rilasciato]
### Aggiunto
- Fase 2, registratore dati in sola lettura: `src/trade/sources/` (DexScreener, GeckoTerminal), `store.py` (SQLite), `recorder.py` e comando `trade-record`. Dipendenze: httpx, pydantic.
- Test con risposte reali delle API registrate il 24/11/2026 (`tests/fixtures/`).
- Scheletro del progetto Python (`pyproject.toml`, `uv.lock`, `src/trade/`, `tests/`).
- `src/trade/modes.py`: modalità operative; il sistema parte in OFF e le modalità con denaro reale richiedono l'approvazione esplicita di Danish.
- Hook `PreToolUse` che blocca l'accesso di Claude Code ai segreti, registrato in `.claude/settings.json`, con test.
- Subagent di sviluppo: security-reviewer, backtest-analyst, docs-keeper.
- Registro installazioni sul Mac: uv 0.13.9, Python 3.12.16, repository clonato, test 33/33, protezioni dei segreti verificate dal vivo.
- `user-settings/`: regole da copiare in `~/.claude/settings.json` perché le protezioni valgano in ogni cartella.
### Corretto
- Rimosse da `.claude/settings.json` le regole `Write(...)`, che Claude Code non applica (si usa `Edit(...)`).
- Valutazione di TradingAgents (TauricResearch) in SKILLS.md: idee adottate, installazione rimandata.
- ARCHITECTURE.md §11: idee adottate (condizioni di invalidazione, Thesis Reviewer, fonte per ogni numero, skill in Markdown).
- AGENTS.md: nuovo Thesis Reviewer (consultivo) e campo `invalidation[]` nei `TradeIntent`.

## [0.0.1] — 2026-11-24
### Aggiunto
- Documenti di progetto: CLAUDE.md, README.md, ROADMAP.md, ARCHITECTURE.md, AGENTS.md, SKILLS.md, INSTALLATION.md, TASKS.md, SECURITY.md, RISK_MANAGEMENT.md, TEST_REPORT.md, CHANGELOG.md.
- Analisi dell'idea (punti di forza, debolezze, correzioni) e ricerca verificata di strumenti al 24/11/2026.
- Architettura multi‑agente con Risk Manager e Signer separati, esecuzione deterministica.
- `.claude/settings.json` con divieti di lettura dei segreti e di comandi rischiosi per Claude Code.
- `.gitignore` e `.env.example` (solo nomi delle variabili, nessun valore).
