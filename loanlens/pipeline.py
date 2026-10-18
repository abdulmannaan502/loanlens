"""The LoanLens agent pipeline.

    input (text / image / app name)
      -> 1. extract terms          Nemotron Nano  (Nano Omni for images)
      -> 2. compute true cost      Python, deterministic
      -> 3. rule checks            Python, deterministic
      -> 4. verify lender          Tavily search + Nemotron Super
      -> 5. reason + verdict       Nemotron 3 Ultra
      -> 6. translate              Nemotron Nano
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

from .apr import LoanTerms, compute_cost, CostBreakdown
from .llm import NemotronClient
from .rules import check_terms, score, Flag, CHECKLIST
from . import verify

LANGS = {"en": "English", "te": "Telugu", "hi": "Hindi"}

EXTRACT_SYSTEM = """You extract loan terms from Indian lending-app offers, screenshots and agreements.
Return ONLY a JSON object with these keys (use null when not stated; never guess numbers):
{
  "app_name": string|null,
  "lender_name": string|null,          // the bank/NBFC actually lending, if named
  "nbfc_partner": string|null,
  "principal": number|null,            // amount sanctioned/advertised in INR
  "upfront_fees": number|null,         // processing/platform/verification fees deducted before disbursal, INR
  "gst_on_fees": boolean|null,         // true if GST is charged on top of those fees
  "interest_amount": number|null,      // interest in INR over the whole tenure
  "interest_rate_text": string|null,   // as written, e.g. "0.1% per day"
  "other_fees_at_repayment": number|null,
  "tenure_days": number|null,
  "installments": number|null,
  "stated_rate": string|null,          // the headline claim, e.g. "0% interest"
  "late_fee_text": string|null,
  "permissions": [string],             // e.g. ["contacts","camera","location"]
  "kfs_provided": boolean|null,
  "grievance_officer": boolean|null,
  "cooling_off": boolean|null,
  "disbursal_to_bank": boolean|null,
  "concerning_clauses": [string]       // short verbatim clauses that worry you, max 5
}
If an interest rate is given per day/month and the amount isn't, compute interest_amount = principal * rate * period."""

VERDICT_SYSTEM = """You are LoanLens, a protective financial advisor for first-time borrowers in India.
You get: extracted loan terms, the TRUE cost computed by code (trust these numbers exactly),
deterministic red flags, and lender verification evidence.

Return ONLY JSON:
{
  "verdict": "SAFE" | "RISKY" | "AVOID",
  "headline": string,          // one sentence a stressed borrower will read
  "reasons": [string],         // 2-4 short reasons, most serious first, cite the real numbers
  "next_steps": [string],      // 2-4 concrete actions (e.g. compare a bank loan, report at sachet.rbi.org.in, uninstall)
  "confidence": "high" | "medium" | "low"
}
Guidance:
- AVOID if the lender is unregulated/warned about, OR APR > 100%, OR it accesses contacts/photos.
- RISKY for high cost or missing disclosures from a regulated lender.
- SAFE only if the cost is reasonable and disclosures are present.
- Use simple words. No legal advice. Never change the computed numbers."""

TRANSLATE_SYSTEM = """Translate the JSON values into {lang} for a first-time borrower.
Use everyday spoken words, not formal jargon. Keep numbers, ₹ amounts, percentages, app names and URLs unchanged.
Keep the same JSON keys. Keep "verdict" in English. Return ONLY the JSON."""


@dataclass
class Analysis:
    terms: dict
    cost: dict | None
    flags: list[dict]
    risk_score: int
    verification: dict
    sources: list[dict]
    verdict: dict
    translations: dict = field(default_factory=dict)
    calls: list[dict] = field(default_factory=list)
    mode: str = "live"   # "live" | "offline" | "sample"
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def terms_to_loan(t: dict) -> LoanTerms | None:
    p, d = t.get("principal"), t.get("tenure_days")
    if not p or not d:
        return None
    return LoanTerms(
        principal=float(p),
        tenure_days=int(d),
        upfront_fees=float(t.get("upfront_fees") or 0),
        gst_on_fees=bool(t.get("gst_on_fees")),
        interest_amount=float(t.get("interest_amount") or 0),
        other_fees_at_repayment=float(t.get("other_fees_at_repayment") or 0),
        installments=int(t.get("installments") or 1),
        stated_rate=t.get("stated_rate"),
    )


def cost_dict(c: CostBreakdown | None) -> dict | None:
    return None if c is None else asdict(c)


def run(client: NemotronClient, text: str = "", image: tuple[bytes, str] | None = None,
        app_name: str = "", languages: tuple[str, ...] = ("te", "hi"), progress=None) -> Analysis:
    say = progress or (lambda *_: None)

    # 1. Extract
    say("extract", "Reading the offer with Nemotron" + (" Nano Omni (vision)" if image else " Nano"))
    hint = f"App name given by user: {app_name}\n\n" if app_name else ""
    if image:
        user = [{"type": "text", "text": hint + "Extract the loan terms from this screenshot. " + (text or "")},
                client.image_part(image[0], image[1])]
        terms = client.chat_json("VISION", "extract (vision)", EXTRACT_SYSTEM, user)
    elif text.strip():
        terms = client.chat_json("NANO", "extract", EXTRACT_SYSTEM, hint + text)
    else:
        terms = {"app_name": app_name, "permissions": [], "concerning_clauses": []}
    if app_name and not terms.get("app_name"):
        terms["app_name"] = app_name

    # 2. True cost
    say("cost", "Computing the true annual cost (deterministic Python)")
    loan = terms_to_loan(terms)
    cost = None
    if loan:
        try:
            cost = compute_cost(loan)
        except ValueError:
            cost = None

    # 3. Rules
    say("rules", "Checking terms against RBI digital lending protections")
    flags = check_terms(terms, cost.apr_simple if cost else None)

    # 4. Verify
    name = terms.get("app_name") or terms.get("lender_name") or app_name
    verification = {"status": "unverified", "summary": "No app or lender name to verify.", "evidence": []}
    sources: list[dict] = []
    if name and verify.tavily_key():
        say("verify", f"Searching the web for '{name}' with Tavily")
        sources = [s for s in verify.search_lender(name, terms.get("nbfc_partner") or terms.get("lender_name")) if "url" in s]
        say("verify", "Weighing the evidence with Nemotron Super")
        listing = "\n\n".join(f"[{i}] {s['title']}\n{s['url']}\n{s['content']}" for i, s in enumerate(sources))
        verification = client.chat_json("SUPER", "verify lender", verify.VERIFY_SYSTEM,
                                        f"App: {name}\nNamed lender: {terms.get('lender_name') or terms.get('nbfc_partner')}\n\nResults:\n{listing or '(none)'}")
    elif name:
        verification["summary"] = "Live verification is off (no Tavily key configured)."

    if verification.get("status") == "warning":
        flags.insert(0, Flag("lender_warning", "high", "Warnings found about this lender", verification.get("summary", "")))

    # 5. Verdict
    say("verdict", "Reasoning about the full picture with Nemotron 3 Ultra")
    payload = {
        "terms": terms,
        "true_cost": cost_dict(cost),
        "true_apr_percent": round(cost.apr_simple * 100, 1) if cost else None,
        "red_flags": [f.to_dict() for f in flags],
        "lender_verification": verification,
        "borrower_protections_checklist": [c[1] for c in CHECKLIST],
    }
    verdict = client.chat_json("ULTRA", "verdict", VERDICT_SYSTEM, json.dumps(payload, ensure_ascii=False), max_tokens=2500)

    # 6. Translate
    translations = {}
    for lang in languages:
        say("translate", f"Explaining in {LANGS[lang]} with Nemotron Nano")
        try:
            translations[lang] = client.chat_json(
                "NANO", f"translate ({lang})", TRANSLATE_SYSTEM.format(lang=LANGS[lang]),
                json.dumps({k: verdict.get(k) for k in ("headline", "reasons", "next_steps")}, ensure_ascii=False))
        except Exception:
            pass

    return Analysis(
        terms=terms, cost=cost_dict(cost), flags=[f.to_dict() for f in flags], risk_score=score(flags),
        verification=verification, sources=sources, verdict=verdict, translations=translations,
        calls=[c.__dict__ for c in client.log], mode="live",
    )


def run_offline(terms: dict) -> Analysis:
    """No API keys: still compute the true cost and rule flags so the app is useful."""
    loan = terms_to_loan(terms)
    cost = compute_cost(loan) if loan else None
    flags = check_terms(terms, cost.apr_simple if cost else None)
    s = score(flags)
    verdict_word = "AVOID" if s >= 60 or (cost and cost.apr_simple > 1) else "RISKY" if s >= 20 else "SAFE"
    verdict = {
        "verdict": verdict_word,
        "headline": "Offline check: true cost and rule flags only. Add API keys for the full Nemotron analysis.",
        "reasons": [f["title"] if isinstance(f, dict) else f.title for f in flags][:4] or ["No rule-based red flags found."],
        "next_steps": ["Ask the lender for its Key Fact Statement.", "Check the lender's name on rbi.org.in."],
        "confidence": "low",
    }
    return Analysis(terms=terms, cost=cost_dict(cost), flags=[f.to_dict() for f in flags], risk_score=s,
                    verification={"status": "unverified", "summary": "Live verification needs a Tavily key.", "evidence": []},
                    sources=[], verdict=verdict, mode="offline")
