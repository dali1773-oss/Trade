# TEST_REPORT — Risultati dei test

> Ultimo aggiornamento: 24/11/2026.

## Stato attuale

Nessun codice ancora: **nessun test eseguito**. Questo file verrà compilato a partire dalla Fase 1.

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
