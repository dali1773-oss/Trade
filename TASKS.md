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

- [ ] **Fase 1 completata il 24/11/2026** tranne la CI su GitHub; prossima: Fase 2 (Data Recorder)
- [ ] Rendere privato il repository GitHub (consigliato) — **Danish**
- [ ] Liberare spazio su disco prima della Fase 2 (23 GB liberi) — **Danish**

- [ ] Revisione e approvazione della PR dei documenti — **Danish**
- [x] Approvazione dei limiti principali di rischio — **Danish**, 25/11/2026 (scheda nel thread)
- [x] Conto Bitvavo aperto (deposito di prova 5 €) — **Danish**, 25/11/2026
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
- [x] Verifica sul Mac: Claude non riesce a creare né leggere un `.env` (5/5 prove bloccate, 24/11/2026)
- [x] Regole di divieto e hook anche in `~/.claude/settings.json` sul Mac (installate da Danish il 24/11/2026)
- [ ] `gitleaks` e `pip-audit` in CI (GitHub Actions)
- [x] Subagent di sviluppo in `.claude/agents/` (security-reviewer, backtest-analyst, docs-keeper)

### Fase 2 — Data Recorder
- [x] Modelli dei dati (`TokenProfile`, `PoolSnapshot`) — 24/11/2026
- [x] Client DexScreener con limite di frequenza (senza chiave)
- [x] Client GeckoTerminal senza chiave (20 s tra le chiamate); chiave Demo: da fare
- [x] Database SQLite con eventi append‑only, token e snapshot
- [x] Comando `uv run trade-record` (`--once`, `--interval`)
- [x] Primo giro di registrazione sul Mac (24/11/2026: 44 token, 42 snapshot, 0 errori)
- [ ] Registrazione continua sul Mac (`caffeinate -i uv run trade-record --interval 60`) — avvio da parte di Danish
- [ ] Client Helius (Free) + WebSocket nuovi pool
- [ ] 7 giorni di registrazione stabile

### Fase 3 — Scam Detection
- [x] Regole deterministiche con veto (`src/trade/scam.py`): liquidità, età pool, mint/freeze, Token‑2022, concentrazione, vendibilità, nomi imitati. Dato mancante = blocco
- [x] Chiavi gratuite Helius e Jupiter salvate in `.env` e verificate (`uv run trade-check-keys`)
- [x] Registrazione continua avviata sul Mac in sottofondo (log in `data/recorder.log`, stop con `pkill -INT -f trade-record`)
- [x] Client Helius (sola lettura): mint/freeze, Token‑2022 (tassa, hook, delegato permanente), concentrazione top 10 escluso il pool
- [x] Prova di rivendibilità via quotazioni Jupiter (giro compra→rivendi, nessuno swap)
- [x] Comando `uv run trade-scan <token>`: verdetto anti‑truffa completo
- [x] Verifica con risposte reali di Helius/Jupiter sul Mac (BONK e un token pump.fun)
- [x] Quota del creatore: primo firmatario della prima transazione del mint (Helius); oltre 3000 transazioni resta sconosciuta → blocca
- [x] Esclusi dal top 10 i conti di pool e curve (Raydium, Orca, Meteora, PumpSwap, pump.fun)
- [ ] Exchange centralizzati nel top 10 (rilevante solo per token vecchi come BONK)
- [ ] Integrazione RugCheck e GoPlus
- [x] Verdetti automatici: `trade-record --scan` controlla ogni token dopo 15 minuti e salva il verdetto (tabella `scam_checks`)
- [x] Etichettatura: `uv run trade-label` (24 h) e `--horizon 168` (7 giorni), tabella verdetto × esito e falsi negativi
- [ ] Prima etichettatura reale (25/11/2026 sera) e decisione sulle soglie

### Fase 4 — Strategia e backtest
- [x] Modello costi del giro completo (`src/trade/costs.py`): perdita quotata da Jupiter + rete + rent + margine slippage, regola 2× e tasse 33%
- [ ] Stima della priority fee con l'API di Helius al posto del valore fisso
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
