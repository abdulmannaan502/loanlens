import pytest

from loanlens.apr import LoanTerms, compute_cost
from loanlens.rules import check_terms
from loanlens.llm import extract_json, strip_reasoning
from loanlens.samples import SAMPLES


def test_zero_interest_short_loan():
    c = compute_cost(LoanTerms(principal=5000, tenure_days=7, upfront_fees=1200))
    assert c.net_disbursed == 3800
    assert round(c.apr_simple * 100) == 1647


def test_gst_is_added_to_fees():
    c = compute_cost(LoanTerms(principal=5000, tenure_days=7, upfront_fees=1000, gst_on_fees=True))
    assert c.net_disbursed == 3820


def test_emi_loan_is_reasonable():
    t = SAMPLES["Meridew Credit (fictional): regulated 12-month EMI loan"]["terms"]
    c = compute_cost(LoanTerms(principal=50000, tenure_days=365, upfront_fees=1000, gst_on_fees=True,
                               interest_amount=t["interest_amount"], installments=12))
    assert 0.18 < c.apr_simple < 0.26


def test_fees_larger_than_loan_rejected():
    with pytest.raises(ValueError):
        compute_cost(LoanTerms(principal=1000, tenure_days=7, upfront_fees=1500))


def test_flags_on_predatory_sample():
    t = SAMPLES["Zorvanta Cash (fictional): '0% interest' 7-day loan"]["terms"]
    ids = {f.id for f in check_terms(t, 16.5)}
    assert {"apr_extreme", "misleading_rate", "permissions", "third_party_contact", "no_lender"} <= ids


def test_kyc_camera_not_flagged():
    t = SAMPLES["Meridew Credit (fictional): regulated 12-month EMI loan"]["terms"]
    assert not [f for f in check_terms(t, 0.22) if f.id in ("permissions", "permissions_soft")]


def test_camera_alone_is_only_a_soft_flag():
    ids = {f.id: f.severity for f in check_terms({"permissions": ["camera", "location"], "lender_name": "X"}, 0.2)}
    assert ids.get("permissions_soft") == "low" and "permissions" not in ids


def test_json_helpers():
    assert extract_json('noise ```json\n{"a": 1}\n``` tail') == {"a": 1}
    assert strip_reasoning("<think>hmm</think>{}") == "{}"


def test_amount_received_overrides_fee_math():
    # fee quoted as 1,200 incl. GST AND the credited amount is stated: don't count GST twice
    c = compute_cost(LoanTerms(principal=5000, tenure_days=7, upfront_fees=1200, gst_on_fees=True, amount_received=3800))
    assert c.net_disbursed == 3800
    assert round(c.apr_simple * 100) == 1647


def test_script_check():
    from loanlens.pipeline import foreign_letters
    assert foreign_letters("యాప్ ₹5,000 NBFC 1,647%", "te") == []
    assert foreign_letters("చేయলে", "te") == ["ল"]


def test_translation_guards():
    from loanlens.pipeline import good_translation
    src = "The app wants your contacts, photos and SMS permissions."
    assert good_translation(src, "ఈ యాప్ మీ కాంటాక్ట్స్, ఫోటోలు మరియు SMS అనుమతులు అడుగుతుంది.", "te")
    assert not good_translation(src, "The user wants a translation into Telugu for a first-time borrower.", "te")  # instruction echo
    assert not good_translation(src, "యాప్ SMS", "te")                                                              # cut off
