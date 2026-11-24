# CHANGELOG

Formato ispirato a "Keep a Changelog". Date in formato AAAA-MM-GG.

## [Non rilasciato]
### Aggiunto
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
