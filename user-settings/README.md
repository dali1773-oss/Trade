# Impostazioni utente di Claude Code (sul Mac)

`claude-user-settings.json` contiene le regole di protezione dei segreti da unire a `~/.claude/settings.json`, così valgono in **qualsiasi** cartella e non solo dentro `Trade`. L'hook usato è una copia di `.claude/hooks/protect_secrets.py` in `~/.claude/hooks/`.

Se `~/.claude/settings.json` esiste già, le regole vanno **unite** (aggiunte agli elenchi esistenti), mai sostituite.
