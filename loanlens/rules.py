"""Red-flag checklist inspired by the Reserve Bank of India's digital lending rules.

These checks run deterministically on the structured terms extracted by the
model, so every flag can be traced to a specific field. The reasoning model
then weighs the flags together with the lender verification evidence.

This is a consumer-awareness aid, not legal advice. The full rules are on
https://www.rbi.org.in (search "Digital Lending").
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

RISKY_PERMISSIONS = {
    "contacts": "your phone's contact list",
    "call_logs": "your call history",
    "sms": "your SMS messages",
    "photos": "your photos and media",
    "media": "your photos and media",
    "location": "your precise location",
    "microphone": "your microphone",
    "camera": "your camera (beyond one-time KYC)",
}

# Rules summarised in plain language. Each checklist item is the borrower-facing
# version of a protection the RBI framework intends borrowers to have.
CHECKLIST = [
    ("kfs", "A Key Fact Statement (KFS) showing the all-in annual rate (APR) is given before you sign."),
    ("hidden_fees", "No fee can be charged unless it was disclosed in the KFS."),
    ("permissions", "Lending apps should not access contacts, photos or call logs; only one-time access to camera, mic or location for KYC with consent."),
    ("disbursal", "Money goes straight into your own bank account from the regulated lender, not through a third-party wallet."),
    ("grievance", "A named grievance redressal officer and complaint process must be shown."),
    ("cooling_off", "You get a cooling-off period to exit the loan by repaying principal plus proportionate APR."),
    ("regulated", "The actual lender is an RBI-regulated bank or NBFC, named in the app."),
]


@dataclass
class Flag:
    id: str
    severity: str  # "high" | "medium" | "low"
    title: str
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def _is_false(v) -> bool:
    return v is False or (isinstance(v, str) and v.strip().lower() in {"no", "false", "absent", "missing"})


def check_terms(terms: dict, apr_simple: float | None) -> list[Flag]:
    flags: list[Flag] = []

    if apr_simple is not None:
        if apr_simple > 1.0:
            flags.append(Flag("apr_extreme", "high", "Extremely expensive loan",
                              f"The real annual cost is about {apr_simple * 100:,.0f}%. Credit cards in India typically charge roughly 36–48% a year."))
        elif apr_simple > 0.36:
            flags.append(Flag("apr_high", "medium", "Expensive loan",
                              f"The real annual cost is about {apr_simple * 100:,.0f}%, well above typical personal-loan rates."))

    stated = str(terms.get("stated_rate") or "").lower()
    if apr_simple is not None and apr_simple > 0.5 and any(k in stated for k in ("0%", "zero", "no interest", "interest free", "interest-free")):
        flags.append(Flag("misleading_rate", "high", "Misleading '0% interest' claim",
                          "The app advertises no interest, but fees make the loan cost far more than a normal loan."))

    perms = [str(p).lower() for p in (terms.get("permissions") or [])
             if not any(k in str(p).lower() for k in ("kyc", "one-time", "one time"))]
    risky = sorted({RISKY_PERMISSIONS[k] for p in perms for k in RISKY_PERMISSIONS if k in p})
    joined = " ".join(perms)
    serious = sorted({RISKY_PERMISSIONS[k] for k in ("contacts", "call_logs", "sms", "photos", "media") if k in joined})
    soft = sorted({RISKY_PERMISSIONS[k] for k in ("location", "microphone", "camera") if k in joined})
    if serious:
        flags.append(Flag("permissions", "high", "Asks for access it shouldn't need",
                          "The app wants " + ", ".join(serious + soft) + ". Contact-list access has been used by illegal lenders to shame borrowers."))
    elif soft:
        flags.append(Flag("permissions_soft", "low", "Camera or location access",
                          "The app wants " + ", ".join(soft) + ". This is acceptable only as a one-time check during sign-up, so confirm it can't keep watching afterwards."))

    if _is_false(terms.get("kfs_provided")):
        flags.append(Flag("kfs", "high", "No Key Fact Statement",
                          "There is no clear one-page summary of the total cost before you accept."))

    if _is_false(terms.get("grievance_officer")):
        flags.append(Flag("grievance", "medium", "No grievance officer listed",
                          "If something goes wrong there is no named person to complain to."))

    if _is_false(terms.get("cooling_off")):
        flags.append(Flag("cooling_off", "low", "No cooling-off period",
                          "You can't exit early without paying full charges."))

    if _is_false(terms.get("disbursal_to_bank")):
        flags.append(Flag("disbursal", "medium", "Money not paid into your bank account",
                          "Loans routed through wallets or third parties are harder to trace and dispute."))

    if not (terms.get("lender_name") or terms.get("nbfc_partner")):
        flags.append(Flag("no_lender", "high", "Actual lender not named",
                          "The app doesn't say which bank or NBFC is lending. Legitimate apps must name their regulated lending partner."))

    late = str(terms.get("late_fee_text") or "").lower()
    if late and any(k in late for k in ("per day", "/day", "daily", "per hour")):
        flags.append(Flag("daily_penalty", "medium", "Penalty grows every day",
                          f"Late fee terms: “{terms.get('late_fee_text')}”. Daily penalties can quickly exceed the loan itself."))

    for clause in terms.get("concerning_clauses") or []:
        c = str(clause).lower()
        if any(k in c for k in ("contact your", "inform your", "notify your", "references", "family", "friends", "employer")):
            flags.append(Flag("third_party_contact", "high", "May contact your family or friends",
                              f"Clause: “{clause}”"))
            break

    return flags


def score(flags: list[Flag]) -> int:
    """0 (clean) to 100 (dangerous). Used for the gauge only."""
    weights = {"high": 30, "medium": 12, "low": 5}
    return min(100, sum(weights.get(f.severity, 0) for f in flags))
