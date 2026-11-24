"""Controllo chiavi: HTTP finto, nessuna rete. La chiave non deve mai comparire nell'output."""

import httpx

from trade.check_keys import main, run
from trade.config import load_settings, redact

FAKE_KEY = "00000000-1111-2222-3333-444444444444"


def write_settings(tmp_path, content):
    f = tmp_path / "settings.txt"
    f.write_text(content)
    return f


def transport(status=200, body=None, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=body if body is not None else {"result": "ok"})

    return httpx.MockTransport(handler)


def test_load_settings_skips_comments_and_empty(tmp_path):
    f = write_settings(tmp_path, "# commento\nA=\nB = 'x'\nHELIUS_API_KEY=abc\n")
    assert load_settings(f) == {"B": "x", "HELIUS_API_KEY": "abc"}
    assert load_settings(tmp_path / "manca") == {}


def test_redact():
    assert redact(f"url?api-key={FAKE_KEY}", [FAKE_KEY]) == "url?api-key=***"


async def test_ok_and_key_sent_only_to_helius(tmp_path):
    f = write_settings(tmp_path, f"HELIUS_API_KEY={FAKE_KEY}\n")
    seen = []
    assert await run(f, transport(seen=seen)) == {"Helius": "OK"}
    assert seen[0].url.host == "mainnet.helius-rpc.com"


async def test_invalid_key(tmp_path):
    f = write_settings(tmp_path, f"HELIUS_API_KEY={FAKE_KEY}\n")
    res = await run(f, transport(status=401))
    assert res["Helius"].startswith("CHIAVE NON VALIDA")


async def test_missing_key(tmp_path):
    f = write_settings(tmp_path, "HELIUS_API_KEY=\n")
    res = await run(f, transport())
    assert res["Helius"].startswith("MANCANTE")


def test_cli_never_prints_key(tmp_path, capsys, monkeypatch):
    f = write_settings(tmp_path, f"HELIUS_API_KEY={FAKE_KEY}\n")

    def boom(request):
        raise httpx.ConnectError(f"fallito {request.url}")

    import trade.check_keys as ck

    real_run = ck.run
    monkeypatch.setattr(ck, "run", lambda path: real_run(path, httpx.MockTransport(boom)))
    assert main(["--file", str(f)]) == 1
    out = capsys.readouterr().out
    assert FAKE_KEY not in out
    assert "ERRORE DI RETE" in out
