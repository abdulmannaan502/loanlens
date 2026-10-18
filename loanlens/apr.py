"""Deterministic loan-cost math.

Language models are never trusted with arithmetic in LoanLens. The model only
extracts the inputs (principal, fees, tenure, repayment schedule); every number
shown to the user is computed here.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LoanTerms:
    principal: float                      # amount "sanctioned" / advertised
    tenure_days: int                      # total loan length in days
    upfront_fees: float = 0.0             # processing / platform / verification fees cut before disbursal
    gst_on_fees: bool = False             # True if 18% GST is charged on upfront fees and not already included
    interest_amount: float = 0.0          # interest the borrower pays on top of principal
    other_fees_at_repayment: float = 0.0  # any fee added to the repayment
    installments: int = 1                 # 1 = single bullet repayment
    stated_rate: str | None = None        # whatever the app advertises, e.g. "0% interest"


@dataclass
class CostBreakdown:
    net_disbursed: float
    total_repayable: float
    total_cost: float
    period_rate: float           # cost / net_disbursed over the whole tenure
    apr_simple: float            # annualised, simple (what RBI-style KFS APR approximates)
    apr_effective: float | None  # annualised with compounding; None if absurdly large
    cost_per_100: float          # rupees paid for every ₹100 actually received
    notes: list[str] = field(default_factory=list)


GST_RATE = 0.18


def _irr_per_period(net: float, payment: float, n: int) -> float:
    """Solve net = payment * (1 - (1+r)^-n) / r for r by bisection."""
    if payment * n <= net:
        return 0.0
    lo, hi = 1e-9, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        pv = payment * (1 - (1 + mid) ** -n) / mid
        if pv > net:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def compute_cost(t: LoanTerms) -> CostBreakdown:
    if t.principal <= 0:
        raise ValueError("Principal must be positive.")
    if t.tenure_days <= 0:
        raise ValueError("Tenure must be at least one day.")

    notes: list[str] = []
    fees = t.upfront_fees * (1 + GST_RATE) if t.gst_on_fees else t.upfront_fees
    if t.gst_on_fees and t.upfront_fees:
        notes.append(f"18% GST adds ₹{t.upfront_fees * GST_RATE:,.0f} to the upfront fee.")

    net = t.principal - fees
    if net <= 0:
        raise ValueError("Fees are larger than the loan itself.")
    if fees:
        notes.append(f"You receive ₹{net:,.0f}, not ₹{t.principal:,.0f}: ₹{fees:,.0f} is cut before the money reaches you.")

    total_repay = t.principal + t.interest_amount + t.other_fees_at_repayment
    cost = total_repay - net
    period_rate = cost / net
    apr_simple = period_rate * 365 / t.tenure_days

    n = max(1, int(t.installments))
    if n == 1:
        eff = (1 + period_rate) ** (365 / t.tenure_days) - 1 if period_rate < 5 else None
    else:
        payment = total_repay / n
        days_per = t.tenure_days / n
        r = _irr_per_period(net, payment, n)
        apr_simple = r * 365 / days_per
        try:
            eff = (1 + r) ** (365 / days_per) - 1
        except OverflowError:
            eff = None
        notes.append(f"{n} instalments of ₹{payment:,.0f} every ~{days_per:.0f} days (rate solved as an IRR).")

    if eff is not None and eff > 1e6:
        eff = None

    return CostBreakdown(
        net_disbursed=round(net, 2),
        total_repayable=round(total_repay, 2),
        total_cost=round(cost, 2),
        period_rate=period_rate,
        apr_simple=apr_simple,
        apr_effective=eff,
        cost_per_100=round(100 * cost / net, 2),
        notes=notes,
    )


def risk_band(apr_simple: float) -> str:
    """Rough bands used only for colour-coding; the verdict comes from the reasoning step."""
    if apr_simple <= 0.36:
        return "normal"
    if apr_simple <= 1.0:
        return "high"
    return "extreme"
