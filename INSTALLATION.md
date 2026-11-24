# INSTALLATION — Guida passo dopo passo

> Pensata per Danish: **Mac con chip Apple (Apple Silicon)**, rilevato il 24/11/2026. Ultimo aggiornamento: 24/11/2026.
> Regola: un passo alla volta. Dopo ogni passo incolla nel thread il risultato; Claude verifica e solo dopo si passa al successivo.
> Non incollare **mai** chiavi private, seed phrase o il contenuto del file `.env`.

## Fase 1 — Passo 1: verificare il Mac (nessuna installazione)

**Obiettivo:** sapere cosa c'è già sul computer, così i comandi successivi saranno quelli giusti.

1. **Aprire il Terminale:** premi `Cmd ⌘ + Spazio`, scrivi `Terminale` e premi Invio. Si apre una finestra con testo; è lì che si incollano i comandi.
2. **Copiare e incollare** questo blocco (tutto insieme) e premere Invio:

```bash
echo "--- macOS ---"; sw_vers
echo "--- chip ---"; uname -m
echo "--- spazio libero ---"; df -h ~ | tail -1
echo "--- strumenti Apple ---"; xcode-select -p 2>&1
echo "--- git ---"; command -v git >/dev/null && git --version 2>&1 | head -1 || echo "git: non trovato"
echo "--- python ---"; command -v python3 >/dev/null && python3 --version 2>&1 || echo "python3: non trovato"
echo "--- uv ---"; command -v uv >/dev/null && uv --version || echo "uv: non trovato"
echo "--- homebrew ---"; command -v brew >/dev/null && brew --version | head -1 || echo "brew: non trovato"
echo "--- node ---"; command -v node >/dev/null && node --version || echo "node: non trovato"
echo "--- claude code ---"; command -v claude >/dev/null && claude --version || echo "claude: non trovato"
```

3. **Cosa aspettarsi:** una serie di righe che iniziano con `---`. Se compare una finestra di macOS che propone di installare gli "strumenti di sviluppo da riga di comando", per ora premi **Annulla**: li installeremo insieme al passo 2, sapendo cosa stiamo facendo.
4. **Incolla nel thread** tutto il testo che il Terminale ha scritto. Non contiene dati sensibili.

**Verifica:** Claude controlla che macOS sia almeno 13.0 (requisito di Claude Code), il chip (`arm64`) e cosa manca.

**Errori comuni:**
- `command not found` su una riga: normale, significa solo che quel programma non c'è ancora.
- La finestra si chiude o non succede nulla: assicurati di aver incollato nel Terminale e premuto Invio.

---

## Mappa dei passi (aggiornata al 24/11/2026)

| Passo | Cosa | Stato |
|---|---|---|
| 1 | Verifica del Mac | ✅ |
| 2 | Installare `uv` (comando ufficiale `curl -LsSf https://astral.sh/uv/install.sh \| sh`, fonte https://github.com/astral-sh/uv) | ✅ |
| 3 | Scaricare il progetto in `~/tradd/Trade` con `git clone` e installare Python 3.12 con `uv python install 3.12` | ✅ |
| 4 | Aggiornare il progetto sul Mac (`git pull`), `uv sync`, `uv run pytest` | ⏳ prossimo |
| 5 | Verificare che Claude **non** riesca a leggere un `.env` di prova (permessi + hook) | ⏳ |
| 6 | Claude Code da terminale (facoltativo: oggi lavoriamo tramite l'app Claude). Comando ufficiale: `curl -fsSL https://claude.ai/install.sh \| bash` (fonte https://code.claude.com/docs/en/setup) | facoltativo |

Gli strumenti da riga di comando Apple e git erano già presenti; Homebrew non serve.

Prima di ogni comando che scarica uno script (`curl … | sh`), Claude mostrerà da quale sito ufficiale proviene e cosa fa.

## Registro delle installazioni

| Data | Passo | Esito | Note |
|---|---|---|---|
| 2026-11-24 | Passo 1: verifica | ✅ | macOS 14.6, Apple Silicon (arm64); strumenti Apple e git 2.39.5 presenti; Python di sistema 3.9.6 (troppo vecchio, useremo uv); Node v26.13.1; mancano uv, Homebrew e Claude Code da terminale; disco: 23 GB liberi su 228 (89% pieno) |
| 2026-11-24 | Passo 2: uv | ✅ (confermato da Danish) | uv 0.13.9 in `~/.local/bin`; installer ufficiale controllato prima dell'esecuzione, senza sudo; checksum sha256 saltato dall'installer (manca `sha256sum` su macOS); nessun file della shell modificato |
| 2026-11-24 | Passo 3: progetto + Python | ✅ | repository clonato in `/Users/danishali/tradd/Trade` (branch `claude/project-thread-ijdg0q`); Python 3.12.16 installato da uv in `~/.local/share/uv/python/`, comando `python3.12`; `python3` di sistema invariato |
