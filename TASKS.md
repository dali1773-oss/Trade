# TASKS — Checklist permanente

> Da consultare **all'inizio di ogni sessione** (Claude e Danish). Aggiornare a ogni passo.
> Ultimo aggiornamento: 24/11/2026.

## ✅ Completate

- [x] Analisi dell'idea e del repository (repository vuoto al 24/11/2026)
- [x] Punti di forza e debolezze (README.md §Analisi)
- [x] Ricerca verificata di skill, MCP, librerie, framework, servizi (SKILLS.md)
- [x] Architettura degli agenti con risk manager non aggirabile (ARCHITECTURE.md, AGENTS.md)
- [x] Confronto chain/piattaforme e costi infrastruttura (ROADMAP.md §1–2)
- [x] Regole di rischio proposte (RISK_MANAGEMENT.md)
- [x] Regole di sicurezza e permessi di Claude Code (SECURITY.md, `.claude/settings.json`)
- [x] Roadmap e ordine delle installazioni (ROADMAP.md)
- [x] Guida installazione Fase 1, passo 1 (INSTALLATION.md)

## 🔄 In corso

- [ ] Revisione e approvazione della PR dei documenti — **Danish**
- [ ] Approvazione dei limiti di rischio proposti (RISK_MANAGEMENT §4–5) — **Danish**
- [x] Fase 1, passo 1: verifica del Mac (24/11/2026, vedi INSTALLATION.md)

## ⏳ Da fare

### Fase 1 — Ambiente
- [x] Strumenti da riga di comando Apple / git (già presenti)
- [ ] Claude Code locale collegato al repository
- [x] `uv` 0.13.9 e Python 3.12.16 installati (24/11/2026)
- [x] Repository clonato sul Mac in `~/tradd/Trade`
- [x] Scheletro progetto (`pyproject.toml`, `src/trade/`, `tests/`) — 33 test passano nel cloud
- [x] Verifica sul Mac: `uv run pytest` passa (33/33, 24/11/2026)
- [x] Hook `PreToolUse` di sicurezza (`.claude/hooks/protect_secrets.py`) con test
- [ ] Verifica sul Mac: Claude non riesce a leggere un `.env` di prova (primo tentativo 24/11 annullato: sessione aperta in `tradd` invece che in `tradd/Trade`)
- [ ] Regole di divieto anche in `~/.claude/settings.json` sul Mac (valgono in ogni cartella)
- [ ] `gitleaks` e `pip-audit` in CI (GitHub Actions)
- [x] Subagent di sviluppo in `.claude/agents/` (security-reviewer, backtest-analyst, docs-keeper)

### Fase 2 — Data Recorder
- [ ] Modelli Pydantic dei messaggi
- [ ] Client DexScreener con rate limit
- [ ] Client GeckoTerminal (chiave Demo)
- [ ] Client Helius (Free) + WebSocket nuovi pool
- [ ] Database SQLite + tabella eventi append‑only
- [ ] 7 giorni di registrazione stabile

### Fase 3 — Scam Detection
- [ ] Controlli mint/freeze/Token‑2022
- [ ] Simulazione vendita via Jupiter
- [ ] Concentrazione holder
- [ ] Integrazione RugCheck e GoPlus
- [ ] Etichettatura 24 h / 7 giorni e report falsi negativi

### Fase 4 — Strategia e backtest
- [ ] Modello costi completo
- [ ] Strategy Engine v1
- [ ] Backtest fuori campione

### Fase 5 — Shadow
- [ ] Risk Manager (processo separato)
- [ ] Execution simulata con quotazioni reali
- [ ] Notifier Telegram + kill switch
- [ ] ≥ 100 trade shadow

### Fase 6 — Devnet
- [ ] Signer separato con allowlist e limiti propri
- [ ] Test duplicati, errori, kill switch

### Fase 7 — Pilota reale (solo con approvazione esplicita)
- [ ] Wallet dedicato, max 100 €
- [ ] ≥ 50 trade reali e confronto con lo shadow

### Fase 8–9
- [ ] Social Intelligence (Reddit/Telegram/X autorizzati)
- [ ] Base/EVM, modulo CEX, dashboard, VPS

### Dalle idee di TradingAgents (approvate per la progettazione il 24/11/2026)
- [ ] Campo `invalidation[]` nei `TradeIntent` e controllo nell'Execution (Fase 4–5)
- [ ] Skill di Claude Code: `token-due-diligence`, `post-trade-review`, `thesis-review` (Fase 1–3)
- [ ] Thesis Reviewer nel report settimanale (Fase 8)
- [ ] Regola "ogni numero con la sua fonte" nei report (Fase 5)

## 💡 Idee e proposte da valutare
- Usare la registrazione dei dati anche per misurare quanto spesso i token "in tendenza" su DexScreener sono scam.
- Valutare se un modulo su asset liquidi (SOL/BTC/ETH spot) dia risultati più stabili delle meme.
