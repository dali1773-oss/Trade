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
        default = {"result": "ok"} if request.url.host.endswith("helius-rpc.com") else {"outAmount": "123"}
        return httpx.Response(status, json=body if body is not None else default)

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
    res = await run(f, transport(seen=seen))
    assert res["Helius"] == "OK"
    assert res["Jupiter"].startswith("MANCANTE")
    assert [r.url.host for r in seen] == ["mainnet.helius-rpc.com"]


async def test_jupiter_key_in_header_only(tmp_path):
    f = write_settings(tmp_path, f"JUPITER_API_KEY={FAKE_KEY}\n")
    seen = []
    res = await run(f, transport(seen=seen))
    assert res["Jupiter"] == "OK"
    req = seen[0]
    assert req.url.host == "api.jup.ag" and req.method == "GET"
    assert req.headers["x-api-key"] == FAKE_KEY
    assert FAKE_KEY not in str(req.url)


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
