# AGENTS — Schede degli agenti

> Stato: **progetto**. Ultimo aggiornamento: 24/11/2026.
> Ogni agente è un modulo con ruolo, permessi e contratti di input/output precisi. "Agente" non significa "LLM": solo Social Intelligence e Reporter usano un modello linguistico, e nessuno dei due può spendere.
> Distinzione importante: questi sono gli **agenti runtime** del sistema di trading. I **subagent di Claude Code** (che aiutano a sviluppare) sono descritti in fondo, sezione 11.

Legenda permessi: `R` lettura dati pubblici · `DB-W` scrittura nel proprio spazio del database · `BUS` pubblica eventi · `VETO` può bloccare · `SIGN` può firmare.

---

## 1. Orchestrator / Supervisor

- **Ruolo:** avvia e ferma gli agenti, tiene la modalità globale (`OFF … LIVE`), controlla la salute, esegue il kill switch.
- **Competenze:** gestione ciclo di vita, heartbeat, watchdog.
- **Strumenti:** codice Python (asyncio), SQLite, Notifier.
- **Permessi:** `R`, `DB-W`, `BUS`, può solo **ridurre** il rischio (pausa/stop), mai aumentarlo. Non può cambiare modalità verso `LIVE_*` senza il comando locale di Danish.
- **Input:** heartbeat, `ExecutionReport`, metriche, comandi `/status` `/pause` `/kill`.
- **Output:** `ModeChanged`, `HealthAlert`.
- **Regole:** se un agente critico (Scam Detection, Risk Manager, Signer) non risponde → `PAUSE`.
- **Monitoraggio:** uptime per agente, ritardo dei messaggi in coda.
- **Errori:** riavvio controllato al massimo 3 volte, poi `PAUSE` e notifica.

## 2. Meme Coin Discovery Agent

- **Ruolo:** trovare nuovi token/pool e picchi di volume.
- **Competenze:** nuovi pool, token in tendenza, aumenti improvvisi di volume, monitoraggio DEX.
- **Fonti dati (MVP gratuito):**
  - DexScreener API: `/token-profiles/latest/v1`, `/token-boosts/latest/v1`, `/latest/dex/pairs/...`, `/token-pairs/v1/...` (60 richieste/min per i profili; limiti degli altri endpoint da confermare nella pagina ufficiale).
  - GeckoTerminal API: `/networks/new_pools`, `/networks/{network}/trending_pools` (senza chiave ~5 chiamate/min, non per produzione; chiave Demo gratuita per limiti più alti).
  - Helius (piano Free): WebSocket per nuovi pool sui programmi DEX (PumpSwap, Raydium, Meteora).
- **Permessi:** `R`, `DB-W`, `BUS`.
- **Output:** `PoolEvent`.
- **Regole:** deduplica per `(chain, pool)`; pre‑filtro su liquidità minima ed età; rispetta i rate limit; mai scraping di siti che lo vietano.
- **Monitoraggio:** eventi/ora, latenza dalla creazione del pool alla nostra scoperta, errori per fonte.
- **Errori:** se una fonte cade si continua con le altre; se cadono tutte → nessun nuovo segnale.

## 3. Scam Detection Agent (con potere di VETO)

- **Ruolo:** decidere se un token è **acquistabile e rivendibile** in sicurezza. Il suo `FAIL` o `UNKNOWN` blocca qualsiasi operazione; nessun altro agente può scavalcarlo.
- **Controlli (Solana):**
  1. Autorità di **mint** ancora attiva → FAIL.
  2. Autorità di **freeze** attiva → FAIL.
  3. Token‑2022 con **transfer fee** / transfer hook / permanent delegate → FAIL (o soglia molto bassa).
  4. **Simulazione di vendita**: quotazione Jupiter token→SOL per l'importo che compreremmo; se non esiste rotta o l'impatto è oltre soglia → FAIL (protezione honeypot).
  5. **Liquidità reale** in SOL/USDC nel pool e stato LP (bloccata/bruciata) → soglie minime.
  6. **Concentrazione**: top 10 holder (escludendo pool e burn) oltre soglia → FAIL; wallet del creatore oltre soglia → FAIL.
  7. Report esterni: RugCheck (endpoint pubblici), GoPlus (piano Free 150K CU/mese), TokenSniffer (a pagamento, solo se servirà). Usati come **segnali aggiuntivi**, mai come unica fonte.
  8. Metadati sospetti (nome che imita token noti, link mancanti) → penalità.
- **Controlli (EVM, fase futura):** honeypot/sell tax via GoPlus, proprietario del contratto, funzioni di blacklist/pausa.
- **Permessi:** `R`, `DB-W`, `BUS`, `VETO`.
- **Input:** `PoolEvent`. **Output:** `ScamVerdict {PASS|FAIL|UNKNOWN, reasons[]}`.
- **Regole:** timeout per controllo; dati mancanti = `UNKNOWN` = blocco. Le soglie stanno in un file di configurazione versionato e modificabile solo con approvazione.
- **Monitoraggio:** dopo 24 h e 7 giorni si verifica cosa è successo ai token (rug o no) per misurare falsi positivi e falsi negativi.
- **Errori:** fail‑closed.

## 4. Blockchain Intelligence Agent

- **Ruolo:** analisi on‑chain: distribuzione token, wallet grandi, movimenti whale, liquidità, attività sospette (wallet collegati al creatore, acquisti coordinati nel primo blocco).
- **Fonti:** Helius RPC/API (Free: 1M crediti/mese, 10 richieste/s), DAS API, transazioni parse.
- **Permessi:** `R`, `DB-W`, `BUS`.
- **Output:** `OnchainProfile`, `WhaleAlert`, `SuspiciousActivity` (quest'ultimo può far scattare un nuovo controllo dello Scam Detection o un'uscita).
- **Regole:** budget di crediti Helius per token; niente `getProgramAccounts` costosi nel percorso caldo.
- **Errori:** dati incompleti → profilo marcato `partial`; la strategia ne tiene conto in modo prudente.

## 5. Social Intelligence Agent (corsia lenta, usa LLM)

- **Ruolo:** misurare menzioni, crescita, viralità; distinguere interesse organico da bot/campagne pagate; notizie rilevanti.
- **Fonti autorizzate (fase 8):**
  - Reddit API ufficiale (OAuth, termini d'uso Reddit da rispettare).
  - Telegram **Bot API**: solo canali/gruppi dove il bot è stato aggiunto legittimamente. Niente account utente automatizzati (Telethon è archiviato e comunque contrario allo spirito delle regole).
  - X API a consumo (lettura post 0,005 $ cadauno, verificato 24/11/2026): solo se il budget lo consente.
  - Discord: solo bot invitati nei server, nel rispetto delle regole del server.
- **Strumenti:** Claude API (modello piccolo ed economico) per classificare testi con output JSON validato.
- **Permessi:** `R`, `DB-W`, `BUS`. **Nessun** accesso a wallet, Risk Manager o Execution.
- **Output:** `SocialScore` (consultivo, con scadenza).
- **Regole anti prompt‑injection:** il testo dei social e i metadati dei token sono **dati non fidati**; il prompt di sistema lo dichiara; l'output deve rispettare lo schema o viene scartato; il modello non ha strumenti.
- **Monitoraggio:** costo API/giorno (tetto massimo), correlazione tra punteggio e risultato reale.
- **Errori:** se manca, la strategia lavora senza social (il punteggio social è opzionale).

## 6. Strategy / Signal Engine

- **Ruolo:** trasformare profili e verdetti in un `TradeIntent` con punteggio e motivazioni (`reason_codes`).
- **Regole:** strategia versionata (`strategy_version`); nessuna modifica automatica con denaro reale (vedi RISK_MANAGEMENT §8). Prima di proporre un trade stima il **costo del giro completo** (acquisto + vendita) e scarta se il guadagno atteso non lo copre con margine.
- **Permessi:** `R`, `BUS`. Non può parlare con l'Execution direttamente.

## 7. Risk Manager (processo separato)

- **Ruolo:** unico cancello verso l'esecuzione. Applica tutti i limiti di [RISK_MANAGEMENT.md](RISK_MANAGEMENT.md).
- **Input:** `TradeIntent`, stato posizioni, PnL, saldo reale letto on‑chain.
- **Output:** `RiskDecision`, `ApprovedOrder` firmato HMAC con scadenza breve e idempotency key.
- **Permessi:** `R`, `DB-W`; unico titolare della chiave HMAC che il Signer accetta.
- **Regole:** i limiti sono costanti in configurazione con valori massimi non superabili da codice; ogni modifica richiede approvazione di Danish e un commit.
- **Errori:** qualsiasi eccezione → `REJECT`.

## 8. Meme Coin Execution Agent

- **Ruolo:** eseguire `ApprovedOrder`, monitorare le posizioni, gestire uscite.
- **Competenze:** quotazione Jupiter, controllo slippage (`min_out`), stima commissioni (base 5.000 lamport per firma + priority fee via Helius Priority Fee API + eventuale tip), simulazione prima dell'invio, gestione transazioni fallite, prevenzione duplicati (idempotency key), protezione MEV quando possibile (slippage stretto, invio tramite Helius Sender o bundle Jito in fase successiva).
- **Permessi:** `R`, `DB-W`, `BUS`; può *chiedere* una firma al Signer, non firma da solo.
- **Output:** `ExecutionReport` con costi reali separati (rete, priority, pool, piattaforma, slippage).
- **Uscite:** take profit a scaglioni, stop loss, time stop, uscita immediata su `SuspiciousActivity` o crollo di liquidità.

## 9. Signer (processo minimo)

- **Ruolo:** firmare solo transazioni valide. È l'unico componente che può leggere la chiave del wallet caldo.
- **Controlli propri:** HMAC valido, ordine non scaduto, importo ≤ massimo per transazione, budget giornaliero proprio non superato, solo programmi in allowlist (Jupiter, System, Token, ATA, Compute Budget), nessun trasferimento verso indirizzi non in allowlist.
- **Permessi:** `SIGN`. Nessuna rete in ingresso, socket Unix locale.

## 10. Notifier e Reporter

- **Notifier:** Telegram verso un solo chat id. Messaggi: acquisti, vendite, veti importanti, errori, pause, report giornaliero.
- **Reporter:** ogni sera riassume PnL netto dopo costi, veti, errori; può usare Claude API per un testo leggibile, ma i numeri vengono dal database, non dal modello.

---

## 11. Subagent di Claude Code (per lo sviluppo, non per il trading)

Da creare in `.claude/agents/` quando inizierà il codice (formato ufficiale: file Markdown con frontmatter `name`, `description`, `tools`):

| Subagent | Compito | Strumenti consentiti |
|---|---|---|
| `security-reviewer` | rivede ogni nuova dipendenza e ogni modifica a Signer/Risk Manager | Read, Grep, Glob |
| `backtest-analyst` | analizza risultati di backtest e shadow, cerca overfitting | Read, Grep, Glob, Bash (solo script di analisi) |
| `docs-keeper` | aggiorna TASKS.md, CHANGELOG.md, TEST_REPORT.md | Read, Edit |

Nessun subagent riceve permessi su file di chiavi o sul processo Signer.
