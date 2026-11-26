"""Helius + Jupiter + verdetto: HTTP finto, nessuna rete.

Le risposte imitano il formato standard di Solana JSON-RPC (jsonParsed) e delle
quotazioni Jupiter; vanno confermate con risposte reali (TEST_REPORT).
"""

from decimal import Decimal

import httpx
import pytest

from trade.config import redact
from trade.ratelimit import MinIntervalLimiter
from trade.scam import Verdict
from trade.security import gather_security_info, scan
from trade.sources import SourceError, make_client
from trade.sources.helius import (
    TOKEN_2022_PROGRAM,
    TOKEN_PROGRAM,
    HeliusClient,
    LargestAccount,
    parse_mint_info,
    top_holders_pct,
)
from trade.sources.jupiter import SOL_MINT, JupiterClient, roundtrip_loss_pct

KEY_H = "hhhhhhhh-1111-2222-3333-444444444444"
KEY_J = "jupiter-secret-key-0123456789"
MINT = "MintAddr1111111111111111111111111111111111"
POOL = "PoolAddr1111111111111111111111111111111111"


def mint_result(program=TOKEN_PROGRAM, mint_auth=None, freeze=None, extensions=None, supply="1000000000"):
    info = {"mintAuthority": mint_auth, "freezeAuthority": freeze, "supply": supply, "decimals": 6,
            "isInitialized": True}
    if extensions is not None:
        info["extensions"] = extensions
    return {"context": {"slot": 1}, "value": {
        "owner": program, "lamports": 1, "executable": False,
        "data": {"program": "spl-token", "parsed": {"type": "mint", "info": info}}}}


LARGEST = {"context": {"slot": 1}, "value": [
    {"address": "VaultA", "amount": "600000000"},  # conto del pool: escluso
    {"address": "W1", "amount": "50000000"},
    {"address": "W2", "amount": "40000000"},
    {"address": "W3", "amount": "10000000"},
]}


def owners_result(addrs):
    owner = {"VaultA": POOL, "W1": "Wallet1", "W2": "Wallet2", "W3": "Wallet3"}
    return {"context": {"slot": 1}, "value": [
        {"data": {"parsed": {"info": {"owner": owner[a]}, "type": "account"}}} for a in addrs]}


CREATOR = "Creator111111111111111111111111111111111111"


def fake_api(*, mint=None, sell_status=200, buy_status=200, sol_back="29400000", seen=None,
             creator_balance="20000000", sig_pages=1):
    mint = mint or mint_result()

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        host = request.url.host
        if host == "mainnet.helius-rpc.com":
            assert request.url.params["api-key"] == KEY_H
            body = __import__("json").loads(request.content)
            method = body["method"]
            if method == "getAccountInfo":
                return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": mint})
            if method == "getTokenLargestAccounts":
                return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": LARGEST})
            if method == "getMultipleAccounts":
                addrs, opts = body["params"]
                if opts["encoding"] == "base64":
                    # Pool (account del programma PumpSwap) e wallet normali (System Program).
                    prog = {POOL: "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"}
                    return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"value": [
                        {"owner": prog.get(a, "11111111111111111111111111111111")} for a in addrs]}})
                return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1,
                                                 "result": owners_result(addrs)})
            if method == "getSignaturesForAddress":
                before = body["params"][1].get("before")
                page = 0 if before is None else int(before.split("-")[1]) // 1000
                n = 1000 if page < sig_pages - 1 else 3
                start = page * 1000
                sigs = [{"signature": f"sig-{start + i + 1}"} for i in range(n)]
                return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": sigs})
            if method == "getTransaction":
                return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {
                    "transaction": {"message": {"accountKeys": [
                        {"pubkey": CREATOR, "signer": True, "writable": True},
                        {"pubkey": MINT, "signer": True, "writable": True}]}}}})
            if method == "getTokenAccountsByOwner":
                assert body["params"][0] == CREATOR and body["params"][1] == {"mint": MINT}
                return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"value": [
                    {"pubkey": "CreatorATA", "account": {"data": {"parsed": {"info": {
                        "tokenAmount": {"amount": creator_balance}}}}}}]}})
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "error": {"message": "no"}})
        if host == "api.jup.ag":
            assert request.method == "GET"
            assert request.headers["x-api-key"] == KEY_J
            p = request.url.params
            if p["inputMint"] == SOL_MINT:
                if buy_status != 200:
                    return httpx.Response(buy_status, json={"errorCode": "TOKEN_NOT_TRADABLE"})
                return httpx.Response(200, json={"outAmount": "123456"})
            if sell_status != 200:
                return httpx.Response(sell_status, json={"errorCode": "COULD_NOT_FIND_ANY_ROUTE"})
            return httpx.Response(200, json={"outAmount": sol_back})
        if host == "api.dexscreener.com":
            return httpx.Response(200, json=[{
                "chainId": "solana", "dexId": "pumpswap", "pairAddress": POOL,
                "baseToken": {"address": MINT, "symbol": "GOOD"},
                "quoteToken": {"address": SOL_MINT},
                "liquidity": {"usd": 50000, "base": 12500000, "quote": 125},
                "priceUsd": "0.002", "priceNative": "0.00001", "fdv": 400000,
                "txns": {"h1": {"buys": 40, "sells": 25}},
                "pairCreatedAt": 1700000000000}])
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def clients(client):
    return (HeliusClient(client, KEY_H, MinIntervalLimiter(0)),
            JupiterClient(client, KEY_J, MinIntervalLimiter(0)))


# --- parser ---------------------------------------------------------------

def test_parse_plain_spl_mint():
    mi = parse_mint_info(mint_result())
    assert not mi.mint_authority_active and not mi.freeze_authority_active
    assert not mi.is_token_2022 and mi.transfer_fee_bps == 0
    assert mi.supply == 1_000_000_000


def test_parse_token_2022_dangerous_extensions():
    ext = [
        {"extension": "transferFeeConfig", "state": {
            "olderTransferFee": {"transferFeeBasisPoints": 0},
            "newerTransferFee": {"transferFeeBasisPoints": 500}}},
        {"extension": "transferHook", "state": {"programId": "Hook111"}},
        {"extension": "permanentDelegate", "state": {"delegate": "Thief111"}},
    ]
    mi = parse_mint_info(mint_result(program=TOKEN_2022_PROGRAM, mint_auth="X", freeze="Y", extensions=ext))
    assert mi.is_token_2022 and mi.mint_authority_active and mi.freeze_authority_active
    assert mi.transfer_fee_bps == 500 and mi.has_transfer_hook and mi.has_permanent_delegate


@pytest.mark.parametrize("bad", [None, {}, {"value": None}, {"value": {"owner": "Other"}}])
def test_parse_mint_rejects_bad(bad):
    with pytest.raises(SourceError):
        parse_mint_info(bad)


def test_liquidity_owners_detects_amm_accounts_and_authorities():
    from trade.sources.helius import liquidity_owners

    progs = {"PoolPda": "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
             "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1": None,
             "Whale": "11111111111111111111111111111111"}
    assert liquidity_owners(progs, set()) == {"PoolPda", "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"}


def test_top_holders_excludes_pool_and_keeps_unknown_owners():
    accs = [LargestAccount("VaultA", 600), LargestAccount("W1", 50), LargestAccount("W2", 40)]
    pct = top_holders_pct(accs, {"VaultA": POOL, "W1": "a"}, 1000, {POOL})
    assert pct == Decimal("9.00")  # W2 senza proprietario noto resta nel conteggio


def test_roundtrip_loss():
    assert roundtrip_loss_pct(30_000_000, 29_400_000) == Decimal("2.00")


# --- client ---------------------------------------------------------------

async def test_helius_refuses_write_methods():
    async with make_client(fake_api()) as client:
        h, _ = clients(client)
        with pytest.raises(SourceError):
            await h.rpc("sendTransaction", ["x"])


async def test_helius_errors_never_contain_key():
    def boom(request):
        raise httpx.ConnectError(f"failed {request.url}")

    async with make_client(httpx.MockTransport(boom)) as client:
        h, _ = clients(client)
        with pytest.raises(SourceError) as exc:
            await h.mint_info(MINT)
    assert KEY_H not in str(exc.value)
    assert redact(KEY_H, [KEY_H]) == "***"


async def test_gather_all_good():
    seen = []
    async with make_client(fake_api(seen=seen)) as client:
        h, j = clients(client)
        rep = await gather_security_info(MINT, helius=h, jupiter=j, pool_addresses={POOL})
    i = rep.info
    assert i.mint_authority_active is False and i.freeze_authority_active is False
    assert i.top10_holders_pct == Decimal("10.00")
    assert i.sell_route_found is True and i.sell_price_impact_pct == Decimal("2.00")
    assert i.creator_holding_pct == Decimal("2.00")
    holders = [n for n in rep.notes if n.startswith("grande possessore")]
    assert "60.00%" in holders[0] and "PumpSwap" in holders[0] and "escluso" in holders[0]
    assert "wallet normale" in holders[1] and "contato" in holders[1]
    # Nessuna richiesta di scrittura: Jupiter solo GET di quotazioni, Helius solo metodi di lettura.
    assert all(r.url.path != "/swap/v1/swap" for r in seen)


async def test_honeypot_sell_has_no_route():
    async with make_client(fake_api(sell_status=400)) as client:
        h, j = clients(client)
        rep = await gather_security_info(MINT, helius=h, jupiter=j, pool_addresses={POOL})
    assert rep.info.sell_route_found is False


async def test_buy_not_quotable_is_unknown_not_fail():
    async with make_client(fake_api(buy_status=400)) as client:
        h, j = clients(client)
        rep = await gather_security_info(MINT, helius=h, jupiter=j, pool_addresses={POOL})
    assert rep.info.sell_route_found is None


async def test_rate_limited_jupiter_is_unknown():
    async with make_client(fake_api(sell_status=429)) as client:
        h, j = clients(client)
        rep = await gather_security_info(MINT, helius=h, jupiter=j, pool_addresses={POOL})
    assert rep.info.sell_route_found is None


async def test_scan_end_to_end_all_good_passes(tmp_path):
    f = tmp_path / "settings"
    f.write_text(f"HELIUS_API_KEY={KEY_H}\nJUPITER_API_KEY={KEY_J}\n")
    verdict, report, msg = await scan(MINT, f, transport=fake_api())
    assert msg == "ok"
    assert verdict.verdict is Verdict.PASS, verdict.reasons


async def test_creator_holding_too_much_fails(tmp_path):
    f = tmp_path / "settings"
    f.write_text(f"HELIUS_API_KEY={KEY_H}\nJUPITER_API_KEY={KEY_J}\n")
    verdict, _, _ = await scan(MINT, f, transport=fake_api(creator_balance="200000000"))
    assert verdict.verdict is Verdict.FAIL
    assert any(r.startswith("quota_creatore") for r in verdict.reasons)


async def test_creator_found_across_pages():
    async with make_client(fake_api(sig_pages=2)) as client:
        h, _ = clients(client)
        assert await h.find_creator(MINT) == CREATOR


async def test_creator_unknown_when_history_too_long():
    async with make_client(fake_api(sig_pages=10)) as client:
        h, j = clients(client)
        assert await h.find_creator(MINT) is None
        rep = await gather_security_info(MINT, helius=h, jupiter=j, pool_addresses={POOL})
    assert rep.info.creator_holding_pct is None


async def test_scan_with_mint_authority_fails(tmp_path):
    f = tmp_path / "settings"
    f.write_text(f"HELIUS_API_KEY={KEY_H}\nJUPITER_API_KEY={KEY_J}\n")
    verdict, _, _ = await scan(MINT, f, transport=fake_api(mint=mint_result(mint_auth="Owner")))
    assert verdict.verdict is Verdict.FAIL


async def test_scan_without_keys(tmp_path):
    verdict, _, msg = await scan(MINT, tmp_path / "manca", transport=fake_api())
    assert verdict is None and "chiavi mancanti" in msg
