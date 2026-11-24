# TEST_REPORT — Risultati dei test

> Ultimo aggiornamento: 24/11/2026.

## Stato attuale

Fasi 1–2 completate, Fase 3 in corso. Ultimo risultato: 76 test passati, 0 falliti (nuovi: `tests/test_check_keys.py`, verifica anche che la chiave non compaia mai nell'output).

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
