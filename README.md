# Trade$£

Sistema di trading automatico multi‑agente per criptovalute e meme coin, con capitale iniziale di **500 € reali**, sicurezza al primo posto e nessuna promessa di profitto.

> **Stato (24/11/2026):** Fase 0 — progettazione completata, nessun codice e nessuna installazione ancora. Prossimo passo: verifica del Mac di Danish ([INSTALLATION.md](INSTALLATION.md)).
> ⚠️ Il trading di meme coin comporta un rischio concreto di **perdita totale**. Leggi [RISK_MANAGEMENT.md](RISK_MANAGEMENT.md).

## Documenti

| File | Contenuto |
|---|---|
| [CLAUDE.md](CLAUDE.md) | regole permanenti per Claude Code |
| [TASKS.md](TASKS.md) | **checklist**: fatto / in corso / da fare |
| [ROADMAP.md](ROADMAP.md) | confronto chain, costi, fasi, ordine installazioni |
| [ARCHITECTURE.md](ARCHITECTURE.md) | come è costruito il sistema |
| [AGENTS.md](AGENTS.md) | scheda di ogni agente |
| [SKILLS.md](SKILLS.md) | strumenti verificati (link, licenze, costi, decisioni) |
| [INSTALLATION.md](INSTALLATION.md) | guida passo dopo passo |
| [SECURITY.md](SECURITY.md) | chiavi, wallet, permessi, prompt injection |
| [RISK_MANAGEMENT.md](RISK_MANAGEMENT.md) | limiti, costi reali, kill switch, go/no‑go |
| [TEST_REPORT.md](TEST_REPORT.md) | risultati di test, backtest, shadow |
| [CHANGELOG.md](CHANGELOG.md) | storico delle modifiche |

## Analisi del progetto

Il repository era vuoto: l'analisi riguarda l'idea descritta da Danish.

### Punti di forza
- **Sicurezza e controllo umano già richiesti:** niente leva, niente ordini reali senza approvazione, kill switch, wallet dedicato. È la base giusta.
- **Agente anti‑scam con veto:** su meme coin è il componente che conta di più.
- **Esecuzione deterministica:** l'idea di non far dipendere le operazioni veloci da un LLM è corretta.
- **Test prima del denaro:** backtest e simulazione prima del reale.
- **Approccio progressivo** e documentato.

### Punti deboli e correzioni

| Problema | Perché è un problema | Correzione proposta |
|---|---|---|
| Aspettativa implicita di "sfruttare le opportunità" delle meme | la maggior parte dei token va a zero; i grandi guadagni sono spesso di insider (Bitquery: solo 26% replicabile) | obiettivo della prima fase: **misurare** se esiste un vantaggio, non guadagnare |
| Competere sulla velocità (nuovi pool) | bot professionali con infrastruttura dedicata arrivano prima | niente cecchinaggio del primo blocco; vantaggio cercato nei filtri anti‑scam e nella disciplina |
| Costi sottovalutati su importi piccoli | su posizioni da 5–10 € il giro completo può costare 4–5% o più | modello di costi obbligatorio e regola "guadagno atteso ≥ 2× costo" |
| Abbonamenti a dati a pagamento | 49 $/mese ≈ 9% del capitale al mese | solo piani gratuiti finché lo shadow non prova un vantaggio |
| Troppi agenti LLM | lenti, costosi, non ripetibili, vulnerabili a prompt injection (i nomi dei token possono contenere istruzioni) | LLM solo nella corsia lenta, senza strumenti né accesso al wallet |
| Backtest su meme | i token morti spariscono dalle API (survivorship bias) | registrare i nostri dati dal primo giorno (Fase 2) |
| "Nessun paper trading come ambiente finale" | corretto, ma il passaggio al reale va reso misurabile | criteri go/no‑go espliciti e pilota con max 100 € |
| Social da X/Telegram/Discord | API X a pagamento; automatizzare account utente viola i termini | solo API ufficiali e bot autorizzati, Fase 8, con tetto di spesa |
| Tasse | in Italia 33% sulle plusvalenze cripto dal 2026, nessuna franchigia | registro di ogni operazione; consultare un commercialista |

### Opportunità individuate
- Piani gratuiti sufficienti per tutte le fasi fino allo shadow trading: DexScreener, GeckoTerminal (chiave Demo), Helius Free, Jupiter Free, GoPlus Free, RugCheck.
- Skill ufficiale Jupiter per Claude Code (solo documentazione) per scrivere l'integrazione in modo corretto.
- MCP ufficiali CoinGecko e Helius (in sola lettura) per fare ricerca durante lo sviluppo.
- Funzioni native di Claude Code (permessi, hook, sandbox) per impedire a Claude stesso di toccare chiavi e fondi.

## Principio guida

**L'AI consiglia, il codice decide, il Risk Manager autorizza, il Signer firma, Danish approva.**
