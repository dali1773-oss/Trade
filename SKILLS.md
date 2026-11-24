# SKILLS — Strumenti, skill, MCP, librerie e servizi valutati

> Ricerca verificata il **24/11/2026**. Licenza, ultimo aggiornamento (data dell'ultimo push su GitHub) e stelle sono stati letti dall'API di ricerca di GitHub; prezzi e limiti dalle pagine ufficiali indicate. Dove un dato non è stato verificato è scritto **"da verificare"**. Nulla è stato installato.
>
> Decisione: ✅ adottare · 🟡 più avanti / opzionale · ❌ scartato (per ora)

## Legenda delle categorie

| Categoria | Cos'è | Dove vive |
|---|---|---|
| **Funzione nativa di Claude Code** | CLAUDE.md, permessi, hook, subagent, skill locali | file nel repo (`CLAUDE.md`, `.claude/`) |
| **Skill** | file `SKILL.md` di istruzioni/conoscenza che Claude carica quando serve | `.claude/skills/` |
| **MCP server** | servizio che dà a Claude strumenti esterni (dati, azioni) | configurato con `claude mcp add` |
| **Subagent** | assistente con contesto isolato e strumenti limitati | `.claude/agents/*.md` |
| **Plugin** | pacchetto che unisce skill, hook, subagent e MCP | `/plugin install` |
| **Libreria** | codice importato dal nostro programma Python | `pyproject.toml` |
| **Framework / repository** | progetto completo (bot, piattaforma) | valutato, non necessariamente usato |
| **Servizio / API** | fornitore esterno di dati o esecuzione | chiave in `.env` |

Documentazione ufficiale Claude Code sulle differenze: https://code.claude.com/docs/en/features-overview

---

## A. Funzioni native di Claude Code

| Nome | Doc ufficiale | Uso nel progetto | Decisione |
|---|---|---|---|
| `CLAUDE.md` | https://code.claude.com/docs/en/memory | regole permanenti del progetto (creato in questa PR) | ✅ |
| Permessi (`.claude/settings.json`) | https://code.claude.com/docs/en/permissions | vieta lettura di segreti e comandi pericolosi (creato in questa PR) | ✅ |
| Hook `PreToolUse` | https://code.claude.com/docs/en/hooks-guide | blocco deterministico di accessi a file sensibili | ✅ Fase 1 |
| Sandbox (`/sandbox`) | https://code.claude.com/docs/en/sandboxing | isola i comandi; su macOS usa Seatbelt; basata su `anthropics/sandbox-runtime` (Apache‑2.0, push 13/11/2026) | ✅ Fase 1 |
| Subagent di progetto | https://code.claude.com/docs/en/sub-agents | `security-reviewer`, `backtest-analyst`, `docs-keeper` (vedi AGENTS.md §11) | ✅ Fase 1 |
| Skill di progetto | https://code.claude.com/docs/en/skills | procedure ripetute (es. "rivedi una dipendenza") | 🟡 quando emergono procedure ripetute |
| Plugin | https://code.claude.com/docs/en/plugins/overview | non necessari per ora | ❌ per ora |

## B. Skill esterne

### jup-ag/agent-skills (Jupiter) ✅ in sviluppo
- **Tipo:** Skill (solo documentazione, nessun codice eseguibile secondo la pagina ufficiale).
- **GitHub:** https://github.com/jup-ag/agent-skills · **Doc:** https://developers.jup.ag/docs/ai/skills
- **Funzioni:** `integrating-jupiter` (Swap, Token, Price, Trigger, ecc., gestione errori), `jupiter-lend`.
- **Compatibilità Claude Code:** sì (la pagina cita Claude Code, Cursor, Codex).
- **Installazione documentata:** `npx skills add jup-ag/agent-skills --skill "integrating-jupiter"`. Richiede Node.js. *Prima di eseguirla va verificato il pacchetto npm `skills`; alternativa più sicura: copiare a mano la cartella della skill in `.claude/skills/` dopo averla letta.*
- **Costo:** gratis · **Licenza:** MIT · **Ultimo push:** 07/07/2026 · **Manutenzione:** organizzazione ufficiale Jupiter, attiva.
- **Rischi:** bassi (testo), ma va letto prima: le skill sono istruzioni che Claude segue.
- **Agente:** Execution (per scrivere correttamente l'integrazione Jupiter).

### anthropics/skills 🟡 riferimento
- **Tipo:** raccolta di skill di esempio di Anthropic. **GitHub:** https://github.com/anthropics/skills · Ultimo push 16/11/2026 · licenza non indicata a livello di repository (da verificare per singola skill).
- **Uso:** modelli per scrivere le nostre skill. Nessuna è specifica per il trading.

## C. MCP server (solo sviluppo/ricerca, mai nell'esecuzione)

### Helius MCP ✅ solo in modalità `--read-only`
- **Doc:** https://www.helius.dev/docs/agents/mcp · **Pacchetto npm:** `helius-mcp`
- **Funzioni:** 10 strumenti (account, wallet, asset, transazioni, chain, streaming, knowledge, **write**, compression, expandResult).
- **Installazione documentata:** `claude mcp add helius npx helius-mcp@latest` — **noi la useremo con la variabile `HELIUS_MCP_READ_ONLY=1`** (o flag `--read-only`), che rimuove `heliusWrite` e 15 azioni che modificano lo stato.
- **Rischio importante:** senza read‑only può inviare transazioni, generare keypair e pagare con USDC da un keypair locale. Mai dargli accesso a un wallet con fondi.
- **Costo:** usa la chiave Helius (piano Free). **Agente:** supporto allo sviluppo di Blockchain Intelligence.

### CoinGecko MCP (ufficiale) ✅ sviluppo
- **Doc:** https://docs.coingecko.com/ai-integration/mcp-server
- **Installazione documentata (senza chiave):** `claude mcp add --transport http coingecko https://mcp.api.coingecko.com/mcp`
- **Funzioni:** due strumenti (`search_docs`, `execute`); `execute` esegue TypeScript contro l'SDK CoinGecko, inclusi metodi on‑chain GeckoTerminal (nuovi pool, pool in tendenza, OHLCV).
- **Costo:** versione senza chiave gratuita con limiti condivisi. **Licenza SDK:** `coingecko/coingecko-typescript` Apache‑2.0, push 17/11/2026.
- **Rischi:** sola lettura di dati di mercato; `execute` gira sui server CoinGecko. **Agente:** ricerca per Discovery.

### Scartati
| Nome | Motivo |
|---|---|
| `sendaifun/solana-mcp` | ultimo push 20/05/2025 (fermo), e dà a un LLM la possibilità di firmare |
| `GoPlusSecurity/goplus-mcp` | ultimo push 29/05/2025 (fermo); usiamo l'API diretta |
| MCP DexScreener di terze parti (`openSVM/…`, `janswist/…`, `kukapay/…`, ecc.) | progetti piccoli e non ufficiali; l'API DexScreener è semplice da chiamare direttamente |
| `dcSpark/mcp-server-helius` | non ufficiale, ultimo push 30/05/2025; esiste quello ufficiale |

## D. Librerie (codice nostro)

| Libreria | GitHub | Licenza | Ultimo push | Uso / agente | Decisione |
|---|---|---|---|---|---|
| uv (gestore Python) | https://github.com/astral-sh/uv | Apache‑2.0 | 24/11/2026 | installazione e versioni bloccate | ✅ |
| pydantic | https://github.com/pydantic/pydantic | MIT | 24/11/2026 | schemi dei messaggi tra agenti | ✅ |
| httpx | https://github.com/encode/httpx | BSD‑3 | 16/11/2026 | chiamate API | ✅ |
| websockets | https://github.com/python-websockets/websockets | BSD‑3 | 14/11/2026 | stream Helius | ✅ |
| solders | https://github.com/kevinheavey/solders | Apache‑2.0 | 26/10/2026 | transazioni/chiavi Solana (Signer, Execution) | ✅ |
| solana-py | https://github.com/michaelhly/solana-py | MIT | 23/11/2026 | client RPC Solana | ✅ |
| helius-sdk | https://github.com/helius-labs/helius-sdk | MIT | 24/11/2026 | SDK TypeScript: utile come riferimento, noi useremo Python | 🟡 |
| DuckDB | https://github.com/duckdb/duckdb | MIT | 24/11/2026 | analisi/backtest | ✅ |
| python-telegram-bot | https://github.com/python-telegram-bot/python-telegram-bot | GPL‑3.0 | 22/11/2026 | Notifier (uso personale: GPL ok) | ✅ |
| anthropic (SDK Python) | https://github.com/anthropics/anthropic-sdk-python | Apache‑2.0 | 23/11/2026 | Social/Reporter | 🟡 Fase 8 |
| CCXT | https://github.com/ccxt/ccxt | MIT | 24/11/2026 | eventuale modulo exchange centralizzati | 🟡 Fase 9 |
| PRAW (Reddit) | https://github.com/praw-dev/praw | BSD‑2 | 24/11/2026 | Social (termini API Reddit da verificare) | 🟡 Fase 8 |
| Telethon | https://github.com/LonamiWebs/Telethon | MIT | **archiviato** (02/2026) | automatizza account utente Telegram | ❌ |
| web3.py | https://github.com/ApeWorX/web3.py (ricerca GitHub; ex `ethereum/web3.py`, da verificare) | MIT | 30/10/2026 | eventuale modulo Base/EVM | 🟡 Fase 9 |
| pip-audit | https://github.com/pypa/pip-audit | Apache‑2.0 | 19/11/2026 | vulnerabilità dipendenze | ✅ |
| gitleaks | https://github.com/gitleaks/gitleaks | MIT | 28/10/2026 | segreti nel codice | ✅ |
| bandit | https://github.com/PyCQA/bandit | Apache‑2.0 | 09/11/2026 | analisi sicurezza Python | ✅ |

## E. Framework e repository valutati

| Nome | GitHub | Licenza | Ultimo push | Valutazione | Decisione |
|---|---|---|---|---|---|
| Freqtrade | https://github.com/freqtrade/freqtrade | GPL‑3.0 | 24/11/2026 | ottimo bot per exchange centralizzati (backtest, dry‑run, Telegram); **non** supporta meme coin su DEX Solana | 🟡 eventuale modulo CEX |
| Hummingbot + Gateway | https://github.com/hummingbot/hummingbot · https://github.com/hummingbot/gateway | Apache‑2.0 | 20/11/2026 | Gateway supporta Jupiter, Raydium, Meteora su Solana; orientato al market making; chiede la chiave privata dentro il gateway (passphrase) | ❌ per ora (studiare il codice dei connettori) |
| NautilusTrader | https://github.com/nautechsystems/nautilus_trader | LGPL‑3.0 | 24/11/2026 | motore professionale Rust/Python, curva d'apprendimento alta | ❌ per ora |
| Jesse | https://github.com/jesse-ai/jesse | MIT | 23/11/2026 | backtest per CEX | ❌ |
| vectorbt | https://github.com/polakowo/vectorbt | NOASSERTION (licenza con restrizioni: da leggere) | 11/11/2026 | backtest vettoriale veloce | 🟡 da verificare licenza |
| backtesting.py | https://github.com/kernc/backtesting.py | AGPL‑3.0 | 05/08/2026 | semplice, ma AGPL | ❌ |
| LangGraph | https://github.com/langchain-ai/langgraph | MIT | 24/11/2026 | orchestrazione LLM: utile al Reporter, non al percorso caldo | 🟡 |
| CrewAI | https://github.com/crewAIInc/crewAI | MIT | 24/11/2026 | agenti LLM a ruoli; non deterministico | ❌ per il core |
| elizaOS | https://github.com/elizaOS/eliza | MIT | 24/11/2026 | framework agenti social/crypto; troppo ampio, LLM al centro | ❌ |
| Solana Agent Kit | https://github.com/sendaifun/solana-agent-kit | Apache‑2.0 | 14/05/2026 | dà a un LLM strumenti per firmare transazioni: contrario alla nostra architettura | ❌ |
| Coinbase AgentKit | https://github.com/coinbase/agentkit | NOASSERTION | 24/11/2026 | come sopra, per EVM | ❌ |
| OpenBB | https://github.com/OpenBB-finance/OpenBB | — | — | **la società ha annunciato la chiusura** (pagina GitHub dell'organizzazione e openbb.co, ago–ott 2026); gli asset passano alla fondazione non‑profit OpenBQ (https://github.com/openbq-org/OpenBB). Orientato ad azioni/macro | ❌ |
| Jito (searcher, RPC) | https://github.com/jito-labs/jito-py-rpc | Apache‑2.0 | 03/06/2025 (fermo) | bundle anti‑MEV; il client Python è poco aggiornato | 🟡 Fase 7, valutare `jito-labs/searcher-examples` (push 19/10/2026) |

## F. Servizi e API dati

| Servizio | Doc ufficiale | Piano gratuito (verificato 24/11/2026) | Primo piano a pagamento | Uso / agente | Decisione |
|---|---|---|---|---|---|
| **DexScreener** | https://docs.dexscreener.com/api/reference | gratuito; 60 req/min su profili/boost; termini: uso commerciale ammesso, licenza revocabile | non necessario | Discovery | ✅ |
| **GeckoTerminal / CoinGecko** | https://docs.coingecko.com/docs/keyless-public-api | senza chiave ~5 chiamate/min (non per produzione); chiave Demo gratuita | Basic 35 $/mese (dato da articolo CoinGecko) | Discovery, OHLCV | ✅ con chiave Demo |
| **Helius** | https://www.helius.dev/pricing | Free: 1M crediti/mese, 10 req/s, 1 sendTransaction/s, Sender incluso, LaserStream WSS standard | Developer 49 $/mese | RPC, WebSocket, priority fee, on‑chain | ✅ Free |
| **Jupiter** | https://dev.jup.ag/portal/rate-limit | senza chiave 0,5 req/s; chiave Free 60 req/min | Developer 25 $/mese | quotazioni, swap, simulazione vendita | ✅ Free con chiave |
| **Birdeye** | https://docs.birdeye.so/docs/pricing | Standard 0 $: 30.000 CU, 1 req/s, dati limitati | Lite 39 $/mese | analisi token/holder | 🟡 |
| **GoPlus Security** | https://gopluslabs.io/security-api | Free: 150K CU/mese, 30K/giorno, 150/min; supporta EVM e Solana | Test 199 $/mese | Scam Detection | ✅ Free |
| **RugCheck** | https://rugcheck.xyz (doc API ufficiali da verificare) | endpoint pubblici senza chiave (secondo la libreria di terze parti `cyhole`) | — | Scam Detection | ✅ come segnale aggiuntivo |
| **TokenSniffer** | https://tokensniffer.readme.io/reference/pricing | prova 14 giorni su richiesta | 99 $/mese (500 token/giorno); supporta Solana | Scam Detection | 🟡 solo se i gratuiti non bastano |
| **DEXTools** | https://www.dextools.io | prezzi API non pubblicati nelle pagine lette | da verificare | Discovery | ❌ per ora |
| **X API** | https://docs.x.com/x-api/getting-started/pricing | nessun piano gratuito (solo crediti promozionali); 0,005 $ per post letto | a consumo | Social | 🟡 Fase 8 con tetto di spesa |
| **Telegram Bot API** | https://core.telegram.org/bots/api (da verificare) | gratuita | — | Notifier, Social (solo chat dove il bot è aggiunto) | ✅ |
| **Claude API** | https://docs.claude.com (prezzi da verificare al momento dell'uso) | — | a consumo | Social, Reporter | 🟡 Fase 8 |

## G. Avvisi emersi dalla ricerca

1. **Organizzazioni false:** `github.com/Dexscreener-API` non è DexScreener (pagina piena di parole chiave, nessun legame con dexscreener.com). Non usarla.
2. **OpenBB** sta chiudendo come azienda: non costruirci sopra.
3. **Telethon** è archiviato.
4. **Helius MCP** può muovere fondi se non in read‑only.
5. I limiti gratuiti cambiano spesso: ricontrollarli prima di ogni fase (data di verifica in cima a questo file).
