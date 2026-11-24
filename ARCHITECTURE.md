# ARCHITECTURE — Trade$£

> Stato: **progetto** (nessun codice ancora). Ultimo aggiornamento: 24/11/2026.
> Questo documento descrive *come* è costruito il sistema. Il *perché* delle scelte di rischio è in [RISK_MANAGEMENT.md](RISK_MANAGEMENT.md), la sicurezza in [SECURITY.md](SECURITY.md), i singoli agenti in [AGENTS.md](AGENTS.md).

## 1. Principi non negoziabili

1. **L'AI consiglia, il codice decide, il risk manager autorizza, il signer firma.** Nessun modello linguistico (LLM) può creare, dimensionare o firmare un ordine.
2. **Percorso caldo deterministico.** Tutto ciò che deve essere veloce (scoperta pool, controlli anti‑scam, quotazione, invio, stop loss) è codice Python normale, testabile e ripetibile. L'LLM lavora solo nella "corsia lenta" (social, report, revisione).
3. **Un solo cancello verso il denaro.** L'unico modo per arrivare al signer è un `ApprovedOrder` emesso dal Risk Manager. Gli agenti di analisi non hanno né la chiave né l'indirizzo del signer.
4. **Difesa in profondità.** Il signer ricontrolla da solo i limiti più importanti (importo massimo, budget giornaliero, programmi ammessi), anche se il Risk Manager li ha già controllati.
5. **Fail‑closed.** Se un dato manca, un'API non risponde, un controllo anti‑scam è incerto o un valore è anomalo, la risposta è **NO**.
6. **Tutto è registrato.** Ogni evento (segnale, veto, ordine, transazione, errore) finisce in un log append‑only con ID univoco.
7. **Modalità esplicite.** Il sistema ha una modalità globale e non passa mai a una modalità con denaro reale da solo.

## 2. Modalità operative

| Modalità | Dati | Ordini | Denaro | Chi la attiva |
|---|---|---|---|---|
| `OFF` | – | – | – | default all'avvio |
| `RECORD` | reali, sola lettura | nessuno | nessuno | Danish/Claude |
| `BACKTEST` | storici registrati | simulati | nessuno | Danish/Claude |
| `SHADOW` | reali in tempo reale | simulati con quotazioni reali Jupiter, **non inviati** | nessuno | Danish/Claude |
| `DEVNET` | devnet Solana | reali su devnet | token di test senza valore | Danish/Claude |
| `LIVE_PILOT` | reali | reali, limiti ridotti | max 100 € nel wallet caldo | **solo Danish**, con conferma esplicita |
| `LIVE` | reali | reali | secondo RISK_MANAGEMENT | **solo Danish**, dopo i criteri go/no‑go |

Il passaggio a `LIVE_PILOT`/`LIVE` richiede: (a) file di configurazione firmato/confermato da Danish, (b) comando manuale locale, (c) criteri go/no‑go di [ROADMAP.md](ROADMAP.md) soddisfatti. Il kill switch riporta sempre a `OFF`.

## 3. Vista d'insieme

```
                          ┌───────────────────────────────┐
                          │  ORCHESTRATOR / SUPERVISOR     │
                          │  modalità, salute, kill switch │
                          └──────────────┬────────────────┘
                                         │ controlla tutti
   CORSIA VELOCE (deterministica)        │                 CORSIA LENTA (LLM ammesso)
 ┌───────────────────┐   PoolEvent   ┌───┴──────────────┐   ┌──────────────────────────┐
 │ Discovery Agent    ├─────────────►│  Event Bus        │◄──┤ Social Intelligence Agent│
 │ (DexScreener, Gecko│               │  (code asyncio + │   │ (Reddit/Telegram/X        │
 │  Terminal, Helius) │               │  log su SQLite)  │   │  autorizzati, Claude API)│
 └───────────────────┘               └─┬──────┬──────┬──┘   └──────────────────────────┘
                                        │      │      │            SocialScore (consultivo)
           ┌────────────────────────────┘      │      └─────────────────────┐
           ▼                                   ▼                            ▼
 ┌───────────────────┐            ┌────────────────────────┐     ┌──────────────────────┐
 │ Scam Detection     │ ScamVerdict│ Blockchain Intelligence │     │ Strategy / Signal    │
 │ Agent (VETO)       ├──────────►│ Agent (holder, whale,   ├────►│ Engine (punteggio    │
 │ RugCheck, GoPlus,  │            │ liquidità, Helius)      │     │ deterministico)      │
 │ TokenSniffer, sim. │            └────────────────────────┘     └─────────┬────────────┘
 │ vendita Jupiter    │                                                     │ TradeIntent
 └─────────┬─────────┘                                                     ▼
           │ veto = blocco duro                                  ┌──────────────────────┐
           └────────────────────────────────────────────────────►│ RISK MANAGER          │
                                                                  │ (processo separato,   │
                                                                  │  limiti, budget, kill)│
                                                                  └─────────┬────────────┘
                                                                            │ ApprovedOrder (firmato HMAC)
                                                                            ▼
                                                                  ┌──────────────────────┐
                                                                  │ Execution Agent       │
                                                                  │ quote→simula→invia    │
                                                                  │ (Jupiter + Helius)    │
                                                                  └─────────┬────────────┘
                                                                            │ richiesta di firma
                                                                            ▼
                                                                  ┌──────────────────────┐
                                                                  │ SIGNER (processo      │
                                                                  │ minimo, chiave locale,│
                                                                  │ ricontrolla limiti)   │
                                                                  └──────────────────────┘
```

## 4. Componenti

| Componente | Tipo | Processo | Usa LLM? | Può spendere? |
|---|---|---|---|---|
| Orchestrator/Supervisor | codice | core | no | no (può solo fermare) |
| Discovery Agent | codice | core | no | no |
| Scam Detection Agent | codice (regole) | core | no | no, ma ha **veto** |
| Blockchain Intelligence Agent | codice | core | no | no |
| Social Intelligence Agent | codice + Claude API | worker separato | sì, solo classificazione testo | no |
| Strategy/Signal Engine | codice | core | no | no |
| Risk Manager | codice | **processo separato** | no | autorizza |
| Execution Agent | codice | core | no | prepara transazioni |
| Signer | codice minimo | **processo separato** | no | firma entro limiti propri |
| Notifier | codice | core | no | no |
| Reporter | codice + Claude API | job giornaliero | sì, riassunti | no |

Nota: "agente" qui significa **modulo con ruolo preciso**, non necessariamente un LLM. È una scelta voluta: un LLM nel percorso di esecuzione aggiunge latenza (secondi), costi per chiamata e comportamenti non ripetibili.

## 5. Comunicazione tra agenti

- **MVP (un solo computer):** bus di eventi in‑process con `asyncio.Queue`; ogni messaggio è un modello **Pydantic** versionato, serializzato anche su SQLite (tabella `events`, append‑only).
- **Confine di processo** solo dove serve sicurezza: Risk Manager e Signer comunicano via socket Unix locale con messaggi firmati HMAC (chiave condivisa locale, non la chiave del wallet).
- **Più avanti** (se serve scalare su VPS): Redis Streams o NATS. Non ora: costo e complessità senza beneficio con 500 €.

### Messaggi principali (schema sintetico)

```text
PoolEvent       {event_id, chain, dex, pool, base_mint, quote_mint, created_at, liquidity_usd, source}
ScamVerdict     {event_id, mint, verdict: PASS|FAIL|UNKNOWN, reasons[], checks{...}, sources[], ttl_s}
OnchainProfile  {mint, top10_pct, holders, dev_wallet_pct, lp_locked|burned, whale_flows_1h, ...}
SocialScore     {mint, mentions_1h, growth, organic_score 0..1, bot_suspect 0..1, evidence[], model, prompt_hash}
TradeIntent     {intent_id, mint, side, size_eur_requested, max_slippage_bps, reason_codes[], strategy_version}
RiskDecision    {intent_id, decision: APPROVE|REJECT, size_eur_final, limits_snapshot, reject_reasons[]}
ApprovedOrder   {order_id(idempotency), intent_id, mint, side, amount_in, min_out, expires_at, hmac}
ExecutionReport {order_id, status, signature, filled_in, filled_out, fees{network,priority,pool,platform}, slippage_bps, latency_ms, error}
```

`UNKNOWN` del controllo anti‑scam equivale a `FAIL`.

## 6. Flusso di un acquisto (corsia veloce)

1. Discovery rileva un nuovo pool o un picco di volume → `PoolEvent`.
2. Pre‑filtro economico (liquidità minima, età, chain ammessa). Se fallisce: scarta, logga.
3. Scam Detection esegue i controlli (vedi AGENTS.md) in parallelo con timeout. Un solo `FAIL`/`UNKNOWN` critico → veto.
4. Blockchain Intelligence arricchisce (concentrazione holder, flussi whale).
5. Strategy Engine calcola il punteggio; il SocialScore, se disponibile e fresco, può solo **ridurre** o aumentare di poco il punteggio, mai superare un veto.
6. `TradeIntent` → Risk Manager: controlla budget, esposizione, perdite giornaliere, cooldown, duplicati, costo stimato del giro completo (acquisto + vendita) rispetto al guadagno atteso.
7. `ApprovedOrder` (scade in pochi secondi) → Execution: richiede quotazione Jupiter, **simula** la transazione, verifica `min_out`, e chiede la firma al Signer.
8. Signer verifica HMAC, scadenza, importo, budget giornaliero proprio, programmi ammessi → firma.
9. Invio (Helius Sender / RPC), conferma, `ExecutionReport`, notifica Telegram.
10. Monitor posizione: take profit, stop loss, time stop, uscita d'emergenza se la liquidità crolla o arriva un nuovo segnale di scam.

## 7. Dati e archiviazione

- **SQLite (WAL)** per MVP: eventi, verdetti, ordini, posizioni, snapshot prezzi. Zero costi, un file, backup facile.
- **DuckDB** per analisi e backtest sui dati registrati.
- **PostgreSQL/TimescaleDB** solo se il volume lo richiede (Fase 9).
- **Registrazione propria dei dati dal primo giorno**: i token morti spariscono dalle API, quindi senza un archivio nostro ogni backtest soffre di *survivorship bias*.

## 8. Osservabilità

- Log JSON strutturati (un file per giorno, rotazione).
- Metriche base: latenza per fase, % veti per motivo, tasso di transazioni fallite, PnL netto dopo costi, uso quote API.
- Notifiche Telegram verso **un solo chat id** (quello di Danish). Comandi ammessi: `/status`, `/pause`, `/kill`. **Nessun comando di acquisto via Telegram.**
- Dashboard: in un secondo momento (Grafana o pagina HTML statica), non necessaria per l'MVP.

## 9. Gestione errori

| Errore | Reazione |
|---|---|
| API dati lenta/irraggiungibile | backoff esponenziale; dopo N fallimenti il verdetto è `UNKNOWN` → nessun acquisto |
| Rate limit (HTTP 429) | rallenta, rispetta i limiti documentati, mai rotazione di chiavi per aggirarli |
| Transazione fallita | nessun nuovo tentativo automatico oltre 1 retry con nuova quotazione; l'idempotency key impedisce duplicati; le commissioni di rete si pagano anche se fallisce |
| Slippage oltre soglia | transazione rifiutata on‑chain grazie a `min_out` |
| Stato incoerente (posizione sconosciuta, saldo inatteso) | `PAUSE` immediato + notifica |
| Perdita giornaliera oltre limite | `PAUSE` fino al giorno dopo |
| Drawdown oltre limite globale | `OFF` + revisione manuale con Danish |

## 10. Dove entra Claude

- **Claude Code** (sviluppo): scrive e rivede il codice, esegue test, aggiorna i documenti. Opera con permessi limitati (vedi `.claude/settings.json`), **non** ha accesso alle chiavi.
- **Claude API** (runtime, opzionale): Social Intelligence e report giornalieri. Input social trattato come **non fidato** (prompt injection), output validato con schema JSON, budget mensile massimo impostato nella console.
- **MCP server** (solo durante lo sviluppo/ricerca, sola lettura): CoinGecko, Helius in `--read-only`. Mai nel percorso di esecuzione.

## 11. Stack tecnico proposto

Python 3.12+ gestito con `uv`; `httpx` e `websockets` per le API; `pydantic` per i messaggi; `solders` (+ `solana-py` dove utile) per transazioni Solana; SQLite/DuckDB; `pytest` per i test; `python-telegram-bot` per notifiche; `anthropic` SDK per la corsia lenta. Dettagli, licenze e motivazioni in [SKILLS.md](SKILLS.md).

Perché **non** LangGraph/CrewAI nel cuore del sistema: sono ottimi per orchestrare LLM, ma qui il cuore deve essere deterministico. Potranno servire per il Reporter o per ricerche, non per eseguire ordini.

Perché **non** Freqtrade/Hummingbot come base: Freqtrade lavora con exchange centralizzati (e Hyperliquid), non con meme coin su DEX Solana; Hummingbot Gateway supporta Jupiter/Raydium/Meteora ma è pensato per market making e chiede di custodire la chiave privata nel suo gateway. Restano opzioni valutate in SKILLS.md.
