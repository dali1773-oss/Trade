# TEST_REPORT — Risultati dei test

> Ultimo aggiornamento: 24/11/2026.

## Stato attuale

Fasi 1–2 completate, Fase 3 in corso. Ultimo risultato (25/11/2026): 114 test passati, 0 falliti (nuovi: `tests/test_backtest.py`, controlla anche che il backtest non usi prezzi futuri). Precedente: 106 test passati, 0 falliti (nuovi: `tests/test_check_keys.py`, verifica anche che la chiave non compaia mai nell'output).

### 2026-11-25 — Registratore con verdetti automatici (commit 25a367b), prime 16,5 ore
- 3.749 token, 8.824 snapshot, 564 verdetti: FAIL 333, UNKNOWN 231, PASS 0.
- Motivi più frequenti: liquidità (546), vendibilità (315), concentrazione top 10 (271), quota creatore (147).
- 189 cicli, 48 errori temporanei delle fonti (DexScreener 44, GeckoTerminal 4), mai bloccanti.
- Il Mac ha dormito da 00:05 a 11:55 (20 buchi da 11 a 70 minuti): serve impedire lo stop con l'alimentatore collegato.
- Database 6,7 MB + 4,2 MB WAL; disco 21 GB liberi.
Nota: nessun PASS perché i token appena nati non hanno ancora liquidità ≥ 20.000 $ né un pool stabile; da valutare nella Fase 4 (strategia), senza abbassare le soglie senza approvazione.

### 2026-11-24 — Terza prova (commit 022d830) e registratore
- Autorità Meteora DBC confermata: su Optimus FhVo3m… ora risulta "escluso (liquidità)".
- ATX: proprietario del 100% = ALwtAcW5jWJDVJC1frveLQA51CT7hWfbrnH1Gao8rUiY, senza account (PDA di un programma non ancora identificato) → resta contato, quindi blocca.
- Registratore: 273 token e 605 snapshot alle 21:15. Il Mac è andato in stop tra le 20:58 e le 21:15 (coperchio chiuso: `caffeinate -i` non lo impedisce); errori di rete durante lo stop, poi ripresa automatica.

### 2026-11-24 — Seconda prova reale di trade-scan (commit 14e48bb)
Risultato: 4 token nuovi, tutti FAIL.
- Quota del creatore ora calcolata anche sulle transazioni "versione 1" (pump.fun).
- Optimus (WK9K…): in 2 minuti il pool PumpSwap è sparito dai grandi possessori, il creatore detiene il 17,58% e la perdita di rivendita è passata a 99,93% → probabile rug pull, bloccato correttamente.
- Huss e Optimus: il conto FhVo3m… (autorità dei pool Meteora DBC) era contato come "balena" (94% e 80%) → aggiunto all'elenco delle autorità di liquidità.
- ATX: grande possessore ALwtAc… senza account (probabile PDA di una curva di lancio non ancora riconosciuta) → resta contato, quindi blocca (prudente).
Decisione: correggere l'elenco delle autorità e ripetere la prova.

### 2026-11-24 — Prova reale di trade-scan sul Mac (commit 9322ac3)
Comando: `uv run trade-scan <token>`; sola lettura, nessuna chiave nell'output.
Risultato:
- BONK (DezXAZ8z…B263): FAIL. Autorità, Token‑2022, liquidità, età e vendibilità ok; top 10 = 40,55% (probabilmente exchange e pool non esclusi: possibile falso allarme); quota creatore sconosciuta.
- Token pump.fun di 2 minuti (2DU8Lu…pump): FAIL. Pool troppo giovane, liquidità sconosciuta (curva pump.fun), Jupiter senza rotta (NO_ROUTES_FOUND) → vendibilità sconosciuta.
Decisione: i formati reali di Helius e Jupiter corrispondono al codice. Prossimi passi: quota del creatore ed esclusione dei conti di pool/exchange dal top 10.

### 2026-11-24 — Test unitari (Helius, Jupiter, trade-scan)
Comando: `uv run pytest -q`
Risultato: 95 passati, 0 falliti (nuovi: `tests/test_security.py`).
Note: risposte finte nel formato standard Solana JSON‑RPC e Jupiter; da confermare con risposte reali. Verificato che la chiave non compaia negli errori e che Helius rifiuti metodi di scrittura.

### 2026-11-24 — Test unitari (regole anti‑truffa)
Comando: `uv run pytest -q`
Risultato: 69 passati, 0 falliti (nuovi: `tests/test_scam.py`).
Note: ogni segnale d'allarme da solo porta a FAIL; un dato mancante porta a UNKNOWN (blocco).
Decisione: regole pronte; mancano i dati reali on‑chain (Helius, Jupiter).

## Cosa verrà registrato qui

| Tipo | Contenuto | Fase |
|---|---|---|
| Test unitari | `uv run pytest`: numero di test, passati/falliti, copertura | 1+ |
| Test di sicurezza | `.env` non leggibile da Claude, `gitleaks`, `pip-audit`, `bandit` | 1+ |
| Data recorder | ore di registrazione, errori, rate limit rispettati | 2 |
| Scam Detection | falsi positivi / falsi negativi a 24 h e 7 giorni | 3 |
| Backtest | PnL netto dopo costi, drawdown, n. trade, dati in/fuori campione | 4 |
| Shadow | trade simulati con quotazioni reali, confronto costi stimati/reali | 5 |
| Devnet | test Signer: limiti, allowlist, duplicati, kill switch | 6 |
| Pilota | trade reali, costi reali vs shadow | 7 |

## Modello di voce

```
### AAAA-MM-GG — <tipo di test>
Versione/commit: …
Comando: …
Risultato: …
Note / problemi: …
Decisione: …
```

## Registro

### 2026-11-24 — Test unitari, scheletro del progetto (ambiente cloud)
Comando: `uv run --python 3.12 pytest -q`
Risultato: **33 passati, 0 falliti**.
Copertura: modalità operative (default OFF, kill switch sempre ammesso, denaro reale solo con approvazione, LIVE solo da LIVE_PILOT) e hook di sicurezza (19 accessi sensibili bloccati, 6 operazioni normali ammesse, input non valido bloccato).
Decisione: ripetuto sul Mac (vedi sotto).

### 2026-11-24 — Test unitari sul Mac di Danish (Fase 1, passo 4)
Versione/commit: ce8e808 · Python 3.12.16 (uv) · pytest 9.2.0
Comando: `uv sync && uv run pytest -q`
Risultato: **33 passati, 0 falliti** (0,79 s).
Hook con il Python di sistema 3.9.6 (input finto `.env`): exit 2, blocco corretto.
Decisione: passo 4 superato. Prossimo: verifica dal vivo che Claude Code, aperto nella cartella `Trade`, non legga un `.env` di prova.

### 2026-11-24 — Prova dal vivo del blocco dei segreti sul Mac (Fase 1, passo 5)
Ambiente: sessione nuova di Claude Code sul Mac, con regole in `~/.claude/settings.json` e hook `~/.claude/hooks/protect_secrets.py`.
| # | Prova | Esito | Livello che ha bloccato |
|---|---|---|---|
| 1 | Write di `Trade/.env` | bloccata | regola deny |
| 2 | Read di `Trade/.env` | bloccata | regola deny |
| 3 | `cat Trade/.env` | bloccata | hook |
| 4 | `grep TEST Trade/.env` | bloccata | hook |
| 5 | Read di `~/.ssh/config` | bloccata | regola deny |
| 6 | Read di `.env.example` (controprova) | ammessa | — |
Note: un primo tentativo è stato annullato perché la sessione era aperta in `tradd` (senza regole di progetto); l'hook blocca anche comandi innocui che citano `.env` (comportamento prudente voluto).
Decisione: protezioni attive su due livelli. Passo 5 superato.

### 2026-11-24 — Registratore dati, test automatici (ambiente cloud)
Comando: `uv run --python 3.12 pytest -q`
Risultato: **52 passati, 0 falliti**.
Copertura nuova: parser DexScreener/GeckoTerminal su risposte reali (valori mancanti restano "sconosciuti", mai zero), ciclo completo con HTTP finto, errore di una fonte registrato senza fermare il ciclo, tabella eventi non modificabile, limitatore di frequenza, solo richieste GET.
Decisione: provare un ciclo reale sul Mac.

### 2026-11-24 — Registratore dati, primo ciclo reale sul Mac
Versione/commit: ed3bead · Comandi: `uv sync`, `uv run pytest -q` (52 passati), `uv run trade-record --once`
Risultato: 1 ciclo in ~30 s, **44 token nuovi, 42 snapshot, 0 errori**; 23 richieste GET, tutte HTTP 200, intervallo ~1,5 s su DexScreener. Database 128 KB.
Osservazioni: i pool ancora sulla curva di pump.fun hanno spesso `liquidity_usd` mancante (da trattare come sconosciuto nei filtri); già visibili nomi imitati (es. "CHIRSTMAS" accanto a "CHRISTMAS"), utile per lo Scam Detection.
Decisione: avviare la registrazione continua per 7 giorni.


## Backtest grandi cripto su Bitvavo — primo test esplorativo (25/11/2026)
Eseguito sul Mac con lo storico pubblico di Bitvavo (BTC ed ETH dal 2019, SOL dal 2021). Costi 0,30% per operazione. Decisione alla chiusura, esecuzione il giorno dopo.
| Mercato | Compra e tieni | Filtro media 200 g |
|---|---|---|
| Solo BTC (2019→2026) | +585%, calo max −74% | +309%, calo max −62% |
| Solo SOL (2021→2026) | −23%, calo max −93% | +134%, calo max −59% |
| Mix BTC+ETH (2019→2026) | +912%, calo max −73% | +781%, calo max −50% |
| Mix BTC+ETH+SOL (2022→2026) | +22%, calo max −76% | +132%, calo max −35% |
Il momentum a 90 giorni è risultato il peggiore quasi ovunque. Lettura: il filtro riduce le cadute ma non garantisce più guadagno. I dati coprono pochi cicli, quindi c'è rischio di overfitting. Prossimo controllo: `uv run trade-backtest` dal repository, che deve dare numeri coerenti.
