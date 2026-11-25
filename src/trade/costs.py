"""Modello dei costi del giro completo (Fase 4) — RISK_MANAGEMENT.md §2.

Tutto in SOL (lamport) per non dipendere dal cambio. Un trade ha senso solo se il
guadagno atteso è almeno `min_edge_multiple` volte il costo stimato del giro
completo (acquisto + vendita). Le tasse (33% in Italia dal 2026) si pagano sul
guadagno netto, quindi riducono il risultato ma non il costo.

Componenti:
- perdita del giro misurata con le quotazioni Jupiter (commissioni dei pool + impatto
  sul prezzo; vedi sources/jupiter.py `sell_check`);
- commissioni di rete: 5.000 lamport per firma + priority fee, per due transazioni;
- rent del conto token (~0,002 SOL): si recupera chiudendo il conto dopo la vendita;
  se non si chiude è un costo pieno;
- margine prudenziale per slippage reale peggiore della quotazione (ritardo, MEV).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

LAMPORTS_PER_SOL = 1_000_000_000
BASE_FEE_LAMPORTS = 5_000  # per firma, si paga anche se la transazione fallisce
TOKEN_ACCOUNT_RENT_LAMPORTS = 2_039_280  # conto token SPL standard


@dataclass(frozen=True)
class CostModel:
    priority_fee_lamports: int = 50_000  # per transazione; da stimare con la Priority Fee API di Helius
    extra_slippage_pct: Decimal = Decimal("1.0")  # per l'intero giro, oltre a quanto quotato
    close_token_account: bool = True  # recupera il rent dopo la vendita
    tax_rate: Decimal = Decimal("0.33")
    min_edge_multiple: Decimal = Decimal("2")

    def network_lamports(self) -> int:
        per_tx = BASE_FEE_LAMPORTS + self.priority_fee_lamports
        rent = 0 if self.close_token_account else TOKEN_ACCOUNT_RENT_LAMPORTS
        return 2 * per_tx + rent

    def roundtrip_cost_pct(self, position_lamports: int, quoted_roundtrip_loss_pct: Decimal) -> Decimal:
        """Costo totale stimato del giro completo, in % della posizione."""
        if position_lamports <= 0:
            raise ValueError("la posizione deve essere positiva")
        network_pct = Decimal(self.network_lamports()) * 100 / Decimal(position_lamports)
        total = quoted_roundtrip_loss_pct + network_pct + self.extra_slippage_pct
        return total.quantize(Decimal("0.01"))

    def worth_trading(self, expected_gain_pct: Decimal, cost_pct: Decimal) -> bool:
        """Regola di RISK_MANAGEMENT §2: guadagno atteso ≥ 2 × costo del giro."""
        return expected_gain_pct >= self.min_edge_multiple * cost_pct

    def net_after_tax_pct(self, gross_move_pct: Decimal, cost_pct: Decimal) -> Decimal:
        """Risultato netto in % dopo costi e (se positivo) tasse."""
        net = gross_move_pct - cost_pct
        if net > 0:
            net = net * (1 - self.tax_rate)
        return net.quantize(Decimal("0.01"))


def sol_to_lamports(sol: Decimal) -> int:
    return int(sol * LAMPORTS_PER_SOL)
