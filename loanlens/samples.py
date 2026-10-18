"""Fictional sample offers for trying LoanLens.

The app names below are invented. They are modelled on common patterns in
predatory and legitimate digital lending offers, not on any real company.
"""

SAMPLES = {
    "FlashPaisa (fictional): '0% interest' 7-day loan": {
        "app_name": "FlashPaisa",
        "text": """FlashPaisa – Instant Cash in 5 Minutes!
Loan amount: ₹5,000
Tenure: 7 days
Interest: 0% – ZERO interest!
Processing & verification fee: ₹1,017 + 18% GST (deducted from disbursal)
Amount credited: ₹3,800 to your FlashPaisa wallet
Repay ₹5,000 on day 7.
Late payment: ₹250 per day.
Permissions required: Contacts, Photos & Media, Location, Camera, SMS
By continuing you agree that in case of non-payment, FlashPaisa may contact your references and the contacts saved on your device.
Lender: FlashPaisa Technologies (service provider)""",
        "terms": {
            "app_name": "FlashPaisa", "lender_name": None, "nbfc_partner": None,
            "principal": 5000, "upfront_fees": 1017, "gst_on_fees": True, "interest_amount": 0,
            "interest_rate_text": "0%", "other_fees_at_repayment": 0, "tenure_days": 7, "installments": 1,
            "stated_rate": "0% – ZERO interest", "late_fee_text": "₹250 per day",
            "permissions": ["contacts", "photos", "media", "location", "camera", "sms"],
            "kfs_provided": False, "grievance_officer": False, "cooling_off": None, "disbursal_to_bank": False,
            "concerning_clauses": ["FlashPaisa may contact your references and the contacts saved on your device"],
        },
    },
    "RupeeNow (fictional): 2-month loan with big fees": {
        "app_name": "RupeeNow",
        "text": """RupeeNow Personal Loan – Pre-approved!
Sanctioned amount: ₹10,000
Tenure: 61 days, 2 monthly instalments
Interest: 2% per month (₹400 total)
Processing fee: ₹1,500 + GST, deducted upfront
Platform fee at repayment: ₹300
Disbursed to your bank account.
Lending partner: Not shown in app
Permissions: Camera, Location
Grievance: support@rupeenow.example (no officer named)
Late fee: 1% of overdue amount per day""",
        "terms": {
            "app_name": "RupeeNow", "lender_name": None, "nbfc_partner": None,
            "principal": 10000, "upfront_fees": 1500, "gst_on_fees": True, "interest_amount": 400,
            "interest_rate_text": "2% per month", "other_fees_at_repayment": 300, "tenure_days": 61, "installments": 2,
            "stated_rate": "2% per month", "late_fee_text": "1% of overdue amount per day",
            "permissions": ["camera", "location"],
            "kfs_provided": None, "grievance_officer": False, "cooling_off": None, "disbursal_to_bank": True,
            "concerning_clauses": [],
        },
    },
    "Sahaj Credit (fictional): regulated 12-month EMI loan": {
        "app_name": "Sahaj Credit",
        "text": """Sahaj Credit – Personal Loan
Lender: Sahaj Finance Ltd (RBI-registered NBFC)
Loan amount: ₹50,000
Tenure: 12 months, 12 EMIs of ₹4,584
Interest: 18% p.a. reducing balance (total interest ₹5,008)
Processing fee: ₹1,000 + GST
Key Fact Statement: provided before acceptance (APR 22.4%)
Cooling-off period: 3 days
Grievance Redressal Officer: Ms. A. Rao, grievance@sahaj.example
Money disbursed directly to your bank account.
Permissions: Camera (one-time KYC)""",
        "terms": {
            "app_name": "Sahaj Credit", "lender_name": "Sahaj Finance Ltd", "nbfc_partner": "Sahaj Finance Ltd",
            "principal": 50000, "upfront_fees": 1000, "gst_on_fees": True, "interest_amount": 5008,
            "interest_rate_text": "18% p.a. reducing", "other_fees_at_repayment": 0, "tenure_days": 365, "installments": 12,
            "stated_rate": "18% p.a.", "late_fee_text": None,
            "permissions": ["camera (one-time KYC)"],
            "kfs_provided": True, "grievance_officer": True, "cooling_off": True, "disbursal_to_bank": True,
            "concerning_clauses": [],
        },
    },
}
