# ROADMAP — Trade$£

> Ultimo aggiornamento: 24/11/2026. Stato attuale: **Fase 0 completata (documenti), Fase 1 in attesa** della verifica del computer di Danish.
> Regola: non si passa alla fase successiva finché la precedente non è verificata (criteri "Fatto quando").

## 1. Confronto blockchain e piattaforme (per 500 €)

| Opzione | Costo tipico per swap | Meme coin | Strumenti anti‑scam | Pro | Contro | Giudizio |
|---|---|---|---|---|---|---|
| **Solana** (Jupiter, PumpSwap, Raydium, Meteora) | base 0,000005 SOL per firma + priority fee; pool ~0,25% | attività molto alta (pump.fun/PumpSwap) | RugCheck, GoPlus, TokenSniffer, controlli mint/freeze nativi | commissioni basse, ottimi strumenti (Helius, Jupiter), piani gratuiti | moltissimi scam, bot e MEV, rent ~0,002 SOL per ogni nuovo token (recuperabile) | ✅ **primo candidato** |
| **Base** (Uniswap, Aerodrome) | gas ~0,01 $ (Portals, mag 2026) | attività presente, minore di Solana | GoPlus molto forte su EVM (honeypot, tasse) | ecosistema EVM, Coinbase | approvazioni token rischiose, liquidità meme più bassa | 🟡 seconda chain (Fase 9) |
| **Arbitrum** | ~0,01–0,03 $ | poca attività meme | GoPlus | economico | poco adatto alle meme | ❌ |
| **BNB Chain** | ~0,10–0,30 $ | attiva | GoPlus | liquidità | costi più alti, molti scam | ❌ per ora |
| **Ethereum L1** | ~3–15 $ (picchi oltre 30 $) | sì | buoni | liquidità | il gas mangia posizioni da 5–10 € | ❌ |
| **Exchange centralizzato** (es. Kraken Pro) | Kraken Pro livello base: maker 0,40%, taker 0,80% | solo meme già quotate (dopo la salita) | l'exchange filtra | regolamentato, niente rug pull di contratto | commissioni alte a basso volume, conto e KYC | 🟡 eventuale modulo "major" (Fase 9) |
| **Hyperliquid / perpetui** | — | — | — | — | leva: **vietata** dalla configurazione iniziale | ❌ |

**Conclusione:** Solana è la scelta più sensata *per iniziare a misurare*, non perché sia "la migliore" in assoluto. L'architettura resta indipendente dalla chain (interfacce `ChainAdapter`) per aggiungere Base più avanti se i dati lo giustificano.

## 2. Costi infrastruttura

| Voce | Fasi 1–6 (sviluppo + shadow) | Pilota | Opzionale (solo se dimostrato utile) |
|---|---|---|---|
| Computer | Mac di Danish: 0 € | Mac acceso o VPS piccolo (prezzo da verificare, indicativamente pochi €/mese) | VPS dedicato |
| Dati DEX | DexScreener + GeckoTerminal Demo: 0 € | 0 € | Birdeye Lite 39 $/mese |
| RPC Solana | Helius Free: 0 € | Helius Free: 0 € | Helius Developer 49 $/mese |
| Swap | Jupiter Free (chiave): 0 € | 0 € | Jupiter Developer 25 $/mese |
| Anti‑scam | GoPlus Free + RugCheck: 0 € | 0 € | TokenSniffer 99 $/mese |
| Social | 0 € (non attivo) | 0 € | X API a consumo (1.000 post letti = 5 $), Claude API con tetto (proposta 5 €/mese) |
| Notifiche | Telegram: 0 € | 0 € | — |
| **Totale** | **0 €/mese** | **0 € – pochi €/mese** | da decidere con i dati |

Claude Code è lo strumento di sviluppo: il suo abbonamento non è conteggiato qui (dipende dal piano di Danish).

## 3. Configurazione iniziale sostenibile

- Sviluppo e test sul Mac di Danish, solo piani gratuiti.
- Solo Solana, solo spot, niente leva.
- Prima settimane: **registrare dati** e misurare i filtri anti‑scam, non fare trading.
- Denaro reale solo dopo i criteri go/no‑go (RISK_MANAGEMENT §9), partendo da max 100 € e 5 € per trade.

## 4. Fasi

### Fase 0 — Fondamenta ✅
Analisi, ricerca verificata, architettura, documenti, regole di sicurezza per Claude Code.
*Fatto quando:* PR dei documenti approvata e unita da Danish.

### Fase 1 — Ambiente di lavoro sul Mac
Verifica del sistema, installazione guidata di: strumenti da riga di comando Apple (git), Homebrew (se serve), `uv` + Python, Claude Code collegato al repository, scheletro del progetto (`pyproject.toml`, cartelle, test vuoti che passano), hook di sicurezza, `gitleaks`.
*Fatto quando:* `uv run pytest` passa sul Mac e Claude Code non riesce a leggere un file `.env` di prova.

### Fase 2 — Data Recorder (sola lettura)
Discovery Agent + registrazione su SQLite di nuovi pool, prezzi, liquidità, holder (DexScreener, GeckoTerminal, Helius Free). Rispetto dei rate limit.
*Fatto quando:* 7 giorni di registrazione continua senza errori non gestiti; almeno 2–4 settimane di dati prima della Fase 4.

### Fase 3 — Scam Detection
Controlli mint/freeze/Token‑2022, simulazione di vendita con Jupiter, concentrazione, RugCheck, GoPlus. Etichettatura automatica a 24 h/7 giorni (il token è crollato o no).
*Fatto quando:* report con tasso di falsi negativi misurato (token passati che poi sono stati rug) e soglie approvate.

### Fase 4 — Strategia e backtest
Strategy Engine + backtest sui dati registrati con il modello di costi completo (commissioni, slippage, priority fee, rent, latenza).
*Fatto quando:* risultato netto dopo costi su dati fuori campione documentato in TEST_REPORT.md.

### Fase 5 — Risk Manager, Execution simulata e Shadow trading
Risk Manager separato, Execution con quotazioni reali Jupiter **senza invio**, Notifier Telegram, kill switch.
*Fatto quando:* ≥ 100 trade shadow e i criteri go/no‑go misurati.

### Fase 6 — Devnet
Signer separato, transazioni reali su devnet, test di limiti, duplicati, errori, kill switch.
*Fatto quando:* tutti i test di sicurezza del Signer passano.

### Fase 7 — Pilota con denaro reale (richiede approvazione esplicita di Danish)
Wallet dedicato con max 100 €, 5 € per trade, limiti stretti. Valutare invio con Helius Sender/Jito.
*Fatto quando:* ≥ 50 trade reali, costi reali confrontati con lo shadow.

### Fase 8 — Social e Blockchain Intelligence avanzata
Reddit/Telegram/X autorizzati, Claude API con tetto di spesa, analisi whale.
*Fatto quando:* il punteggio social migliora i risultati in backtest/shadow (altrimenti si spegne).

### Fase 9 — Estensioni
Base/EVM, modulo exchange centralizzato (CCXT/Freqtrade) per asset più liquidi, dashboard, VPS, PostgreSQL.

## 5. Installazioni necessarie in ordine di priorità

| # | Cosa | Perché | Fase |
|---|---|---|---|
| 1 | Verifica sistema (macOS, chip, programmi presenti) | evitare comandi sbagliati | 1 |
| 2 | Strumenti da riga di comando Apple (include git) | scaricare e salvare il codice | 1 |
| 3 | Claude Code nel terminale (se non già presente) + collegamento al repo | lavorare sul codice in locale | 1 |
| 4 | `uv` (gestisce Python e dipendenze) | ambiente Python isolato e ripetibile | 1 |
| 5 | Dipendenze del progetto (`uv sync`) | httpx, pydantic, websockets, pytest | 1–2 |
| 6 | `gitleaks`, `pip-audit` | sicurezza | 1 |
| 7 | Account e chiavi gratuite: Helius, Jupiter, CoinGecko Demo, GoPlus | dati | 2 |
| 8 | Bot Telegram (BotFather) | notifiche | 5 |
| 9 | MCP read‑only (CoinGecko, Helius `--read-only`) | ricerca durante lo sviluppo | 2 (opzionale) |
| 10 | `solders`, `solana-py`, wallet devnet | esecuzione | 6 |
| 11 | Wallet dedicato mainnet | pilota | 7, solo con approvazione |
