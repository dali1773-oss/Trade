# RISK_MANAGEMENT — Gestione del rischio

> Stato: **regole proposte, da approvare da Danish**. Ultimo aggiornamento: 24/11/2026.
> Questi limiti sono implementati nel Risk Manager **e** ricontrollati dal Signer. Nessun agente di analisi può modificarli.

## 1. Verità scomode (da leggere prima di tutto)

- **Il trading automatico non garantisce profitti.** Su meme coin la maggior parte dei token va a zero; molti sono progettati per derubare gli acquirenti.
- **Rischio di perdita totale reale.** Con 500 € bisogna considerare possibile perderli tutti. Usare solo denaro la cui perdita non cambia la vita.
- **Dati sui trader di pump.fun** (fonti verificate il 24/11/2026, da leggere con prudenza):
  - Decrypt, gennaio 2025, dati Dune: solo lo **0,4%** dei wallet (55.012 su 13,4 milioni) aveva realizzato più di 10.000 $ di profitto.
  - CoinGecko Research, dati apr 2024 – apr 2026: la quota di wallet in profitto realizzato è oscillata tra **30%** (giugno 2025) e **73%** (aprile 2026), ma il 65% dei wallet in profitto guadagnava tra 1 e 500 $, il dato esclude le perdite non realizzate e include bot e wash trading.
  - Bitquery (ottobre 2026): solo il **26%** dei grandi guadagni (≥100.000 $) era replicabile con trading normale; il resto veniva da token trasferiti (insider), coordinamento o casi non classificati. Copiare i "wallet vincenti" spesso significa copiare insider.
- **Concorrenza:** competiamo con bot professionali con nodi dedicati, latenza di millisecondi e capitale molto maggiore. Non vinceremo la gara di velocità sul primo blocco: la strategia deve cercare vantaggi diversi (filtri anti‑scam migliori, disciplina, selezione), non essere "il più veloce".
- **Tasse in Italia** (CMS, aggiornato 22/09/2026): plusvalenze cripto tassate al **33% dal 1° gennaio 2026**, la franchigia di 2.000 € è stata abolita, obbligo di quadro RW. Ogni operazione va registrata per la dichiarazione. Consultare un commercialista.

## 2. Modello dei costi (obbligatorio per ogni trade)

Ogni `TradeIntent` deve stimare il costo del **giro completo** (acquisto + vendita):

| Voce | Valore di riferimento | Fonte / nota |
|---|---|---|
| Commissione base Solana | 5.000 lamport per firma (0,000005 SOL) | solana.com, si paga anche se la transazione fallisce |
| Priority fee | `prezzo CU × limite CU`; stima dalla Helius Priority Fee API | in congestione può salire molto |
| Rent account token (ATA) | ~0,002 SOL per ogni nuovo token, **recuperabile** chiudendo l'account | importante con importi piccoli |
| Commissione del pool | es. PumpSwap 0,25% per scambio (The Block, mar 2025, da riverificare) | varia per DEX |
| Commissione aggregatore | Jupiter Ultra applica commissioni di swap (importo non indicato nelle pagine lette) | da misurare nelle quotazioni reali |
| Slippage / impatto prezzo | spesso 1–5% per lato su token piccoli | dominante con poca liquidità |
| Tip Jito (opzionale) | da definire in fase successiva | protezione MEV |
| Costi API | 0 € con piani gratuiti | vedi §7 |

**Esempio realistico:** posizione da 10 € su un token con poca liquidità → 0,25% + 0,25% di pool, 2% + 2% di slippage, più rete → **circa 4–5% di costo del giro completo**. Per guadagnare bisogna superare questa soglia *prima* di pagare il 33% di tasse sul guadagno. Regola: il trade si fa solo se il guadagno atteso stimato è almeno **2× il costo stimato del giro completo**.

## 3. Struttura del capitale (proposta)

| Quota | Importo | Dove | Uso |
|---|---|---|---|
| Riserva | 400 € | resta fuori dal wallet caldo (conto/exchange regolamentato) | non tocca il sistema durante il pilota |
| Wallet caldo pilota | **max 100 €** | wallet Solana dedicato, solo per il progetto | `LIVE_PILOT` |
| Gas | ~0,05–0,1 SOL inclusi nei 100 € | stesso wallet | commissioni e rent |

L'aumento del wallet caldo oltre 100 € avviene solo dopo i criteri di §9 e con approvazione esplicita di Danish.

## 4. Limiti per operazione

| Regola | Valore pilota | Valore LIVE (massimo) |
|---|---|---|
| Importo massimo per trade | 5 € | 2% del capitale del sistema (10 € su 500 €) |
| Posizioni aperte contemporanee | 2 | 4 |
| Slippage massimo accettato | 300 bps (3%) | 300 bps |
| Impatto prezzo massimo in vendita simulata | 5% | 5% |
| Liquidità minima del pool | 20.000 $ | 20.000 $ |
| Età minima del pool | 10 minuti (niente cecchinaggio del primo blocco) | da validare col backtest |
| Stop loss | −25% per posizione | da validare |
| Time stop | chiusura dopo 24 h se nessun target | da validare |
| Cooldown stesso token | 24 h dopo uno stop loss | 24 h |
| Leva | **vietata** | **vietata** |

I valori sono iniziali e prudenti: vanno calibrati con dati registrati e backtest, poi approvati.

## 5. Limiti di periodo

| Regola | Pilota | LIVE |
|---|---|---|
| Perdita massima giornaliera | 10 € → `PAUSE` fino al giorno dopo | 3% del capitale |
| Perdita massima settimanale | 25 € → `PAUSE` + revisione | 8% del capitale |
| Numero massimo di trade al giorno | 10 | 20 |
| Drawdown massimo dal picco | 40 € (40% del pilota) → `OFF` + revisione con Danish | 20% del capitale → `OFF` |
| Errori di esecuzione consecutivi | 3 → `PAUSE` | 3 → `PAUSE` |

## 6. Kill switch

Tre modi indipendenti per fermare tutto:
1. Comando Telegram `/kill` (solo dal chat id di Danish).
2. Comando locale `trade kill` sul computer.
3. File `KILL` nella cartella del progetto: se esiste, il Signer rifiuta qualsiasi firma.

Il kill switch: annulla ordini pendenti, smette di aprire posizioni, opzionalmente chiude le posizioni aperte (scelta configurabile, default: chiede conferma a Danish), passa a `OFF`. Va **testato** in DEVNET e in `LIVE_PILOT` prima di qualsiasi aumento di capitale.

## 7. Costi fissi mensili come rischio

Con 500 € di capitale, 49 $/mese (Helius Developer) equivalgono a ~9% del capitale al mese. Regola: **solo piani gratuiti** finché lo shadow trading non dimostra un vantaggio netto superiore al costo dell'abbonamento. Budget massimo Claude API per la corsia lenta: da fissare nella console (proposta: 5 €/mese).

## 8. Modifiche alle strategie

- Nessuna modifica automatica di parametri con denaro reale.
- Ogni modifica: nuova `strategy_version` → backtest → shadow ≥ 7 giorni → approvazione di Danish → commit.
- Ottimizzazioni automatiche (es. hyperopt) solo in `BACKTEST`, con controllo anti‑overfitting (dati fuori campione).

## 9. Criteri go/no‑go per il denaro reale

Per passare da `SHADOW` a `LIVE_PILOT` servono **tutti**:
- ≥ 100 trade simulati in shadow con quotazioni reali Jupiter.
- PnL netto simulato > 0 **dopo** tutti i costi stimati, con margine.
- Drawdown simulato entro i limiti di §5.
- 7 giorni consecutivi senza errori non gestiti.
- Kill switch e limiti del Signer testati in DEVNET.
- Approvazione scritta di Danish.

Per aumentare il capitale oltre il pilota: ≥ 50 trade reali, PnL reale coerente con lo shadow (differenza di costi entro il 30%), nessun incidente di sicurezza.
