"""LoanLens: see the real cost of a loan app before you accept it.

Run:  streamlit run app.py
"""
from __future__ import annotations

import html
import json

import streamlit as st

from loanlens.llm import NemotronClient
from loanlens.pipeline import run, run_offline, LANGS, Analysis
from loanlens.samples import SAMPLES
from loanlens import verify

st.set_page_config(page_title="LoanLens", page_icon="🔎", layout="centered")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Noto+Sans:wght@400;500;700&family=Noto+Sans+Telugu:wght@400;600&family=Noto+Sans+Devanagari:wght@400;600&display=swap');
:root{
  --paper:#F2F5F3; --card:#FFFFFF; --ink:#1B2A3A; --muted:#5B6B78; --rule:#CBD5D0;
  --red:#C62828; --amber:#A86A12; --green:#1E7D4F; --blue:#24527A;
}
html, body, [class*="css"], .stMarkdown, p, li, label, input, textarea {
  font-family:'Noto Sans','Noto Sans Telugu','Noto Sans Devanagari',sans-serif !important; color:var(--ink);
}
.stApp{background:var(--paper);}
.block-container{padding-top:2rem; max-width:780px;}
h1,h2,h3,.ll-display{font-family:'Bricolage Grotesque','Noto Sans',sans-serif !important; letter-spacing:-0.01em;}
.ll-brand{display:flex; align-items:baseline; gap:.6rem; margin-bottom:.2rem;}
.ll-title{font-family:'Bricolage Grotesque',sans-serif; font-size:2.8rem; font-weight:800; line-height:1.05; color:var(--ink); letter-spacing:-0.02em;}
.ll-brand span{font-size:1rem; color:var(--muted);}
.ll-intro{font-size:1.05rem; color:var(--muted); max-width:60ch; margin:0 0 1.2rem 0;}

/* passbook receipt */
.ll-receipt{position:relative; background:var(--card); border:1px solid var(--rule); border-radius:6px;
  padding:1.4rem 1.5rem 1.2rem; margin:1rem 0 1.4rem; overflow:hidden;}
.ll-receipt .app{font-family:'Bricolage Grotesque',sans-serif; font-weight:700; font-size:1.3rem; margin:0 0 .9rem; min-height:3.4rem; padding-right:9rem;}
.ll-row{display:flex; justify-content:space-between; gap:1rem; padding:.45rem 0; font-size:1rem; border-bottom:1px solid #E6ECE9;}
.ll-row b{font-variant-numeric:tabular-nums;}
.ll-apr{margin-top:1rem; padding-top:1rem; border-top:2px dashed var(--rule);}
.ll-apr .label{color:var(--muted); font-size:.95rem;}
.ll-apr .num{font-family:'Bricolage Grotesque',sans-serif; font-weight:800; font-size:3.4rem; line-height:1; font-variant-numeric:tabular-nums;}
.ll-apr .claim{color:var(--muted); font-size:.95rem; margin-top:.3rem;}
.ll-stamp{position:absolute; top:1.1rem; right:1.1rem; transform:rotate(-8deg);
  font-family:'Bricolage Grotesque',sans-serif; font-weight:800; font-size:1.7rem; letter-spacing:.06em;
  padding:.25rem .8rem; border:4px solid currentColor; border-radius:8px; opacity:.88;
  animation:stamp .45s cubic-bezier(.2,1.6,.4,1) both;}
@keyframes stamp{from{transform:rotate(-8deg) scale(2.2); opacity:0} to{transform:rotate(-8deg) scale(1); opacity:.88}}
@media (prefers-reduced-motion: reduce){.ll-stamp{animation:none}}
.v-AVOID{color:var(--red);} .v-RISKY{color:var(--amber);} .v-SAFE{color:var(--green);}
.ll-headline{font-size:1.15rem; font-weight:500; margin:.2rem 0 1.2rem; max-width:62ch;}

.ll-flag{border-left:4px solid var(--rule); background:var(--card); padding:.7rem 1rem; margin:.5rem 0; border-radius:0 6px 6px 0;}
.ll-flag.high{border-color:var(--red);} .ll-flag.medium{border-color:var(--amber);} .ll-flag.low{border-color:var(--blue);}
.ll-flag b{display:block; margin-bottom:.15rem;}
.ll-flag p{margin:0; color:var(--muted); font-size:.95rem;}

.ll-verify{background:var(--card); border:1px solid var(--rule); border-radius:6px; padding:1rem 1.1rem; margin:.5rem 0 1rem;}
.ll-pill{display:inline-block; font-weight:700; font-size:.85rem; padding:.1rem .55rem; border-radius:99px; margin-bottom:.4rem;}
.p-regulated{background:#E2F2E9; color:var(--green);} .p-warning{background:#FBE4E4; color:var(--red);} .p-unverified{background:#F3ECDD; color:var(--amber);}
.ll-src{font-size:.9rem; margin:.25rem 0;}
.ll-src a{color:var(--blue);}
.ll-note{font-size:.88rem; color:var(--muted);}
.ll-mode{font-size:.88rem; padding:.5rem .8rem; border-radius:6px; background:#E9EEF3; color:var(--blue); margin-bottom:1rem;}
.stButton>button[kind="primary"]{background:var(--ink); border-color:var(--ink); font-weight:700; padding:.55rem 1.4rem;}
.stButton>button[kind="primary"] p{color:#FFFFFF !important;}
.stButton>button[kind="primary"]:hover{background:#2C4258; border-color:#2C4258;}
@media (max-width:600px){ .ll-apr .num{font-size:2.6rem;} .ll-stamp{font-size:1.2rem; top:.8rem; right:.8rem;} .ll-title{font-size:2.2rem;} }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

client = NemotronClient.from_settings()
has_tavily = bool(verify.tavily_key())

# ---------- sidebar ----------
with st.sidebar:
    st.markdown("### How LoanLens works")
    st.markdown(
        "Each step uses the smallest NVIDIA Nemotron model that does it well, served on **Nebius Token Factory**.")
    st.markdown(
        "| Step | Runs on |\n|---|---|\n"
        "| Read the offer | Nemotron Nano / 3.5 Super VL |\n"
        "| True cost math | Python (no AI guessing) |\n"
        "| Rule checks | Python, RBI-based checklist |\n"
        "| Check the lender | Tavily search + Nemotron Super |\n"
        "| Verdict | Nemotron 3 Ultra |\n"
        "| Telugu / Hindi | Nemotron 3 Ultra |")
    st.markdown("---")
    st.markdown(f'<div class="ll-status">Nemotron on Nebius: {"connected ✅" if client else "not configured"}<br>'
                f'Tavily web search: {"connected ✅" if has_tavily else "not configured"}</div>', unsafe_allow_html=True)
    langs = st.multiselect("Also explain in", options=["te", "hi"], default=["te", "hi"],
                           format_func=lambda c: LANGS[c])
    with st.expander("Open a saved report"):
        saved = st.file_uploader("LoanLens report (.json)", type=["json"], key="saved_report")
        if saved is not None and st.session_state.get("_loaded") != saved.name:
            try:
                st.session_state["result"] = Analysis(**json.loads(saved.getvalue()))
                st.session_state["_loaded"] = saved.name
            except Exception as e:
                st.error(f"That file isn't a LoanLens report: {e}")
    st.markdown("---")
    st.caption("LoanLens is an awareness tool, not legal or financial advice. "
               "Report illegal lending apps at sachet.rbi.org.in or cybercrime.gov.in (helpline 1930).")

# ---------- header ----------
st.markdown('<div class="ll-brand"><div class="ll-title">LoanLens</div><span>check a loan app before you accept</span></div>', unsafe_allow_html=True)
st.markdown('<p class="ll-intro">Paste a loan offer, upload a screenshot, or type the app\'s name. '
            'See what the loan really costs, what the app can do with your phone, and whether the lender is real, '
            'before you tap accept.</p>', unsafe_allow_html=True)

if not client:
    st.markdown('<div class="ll-mode">Offline mode: true-cost math and rule checks work without keys. '
                'Add <code>NEBIUS_API_KEY</code> and <code>TAVILY_API_KEY</code> to enable Nemotron reasoning and live lender checks.</div>',
                unsafe_allow_html=True)

tab_text, tab_img, tab_name, tab_sample = st.tabs(["Paste the offer", "Upload a screenshot", "Just the app name", "Try a sample"])

with tab_text:
    text_in = st.text_area("Loan offer or agreement text", height=180,
                           placeholder="e.g. Loan ₹5,000 for 7 days. 0% interest. Processing fee ₹1,200…")
    name_for_text = st.text_input("App name (optional)", key="name_text")
    go_text = st.button("Check this loan", type="primary", key="go_text")

with tab_img:
    up = st.file_uploader("Screenshot of the offer or agreement", type=["png", "jpg", "jpeg", "webp"])
    if up:
        st.image(up, width=260)
    name_for_img = st.text_input("App name (optional)", key="name_img")
    go_img = st.button("Check this screenshot", type="primary", key="go_img", disabled=not up)

with tab_name:
    only_name = st.text_input("Loan app name", placeholder="e.g. the app that sent you an SMS")
    st.caption("Without the offer text LoanLens can only check the lender, not the cost.")
    go_name = st.button("Check this lender", type="primary", key="go_name", disabled=not only_name)

with tab_sample:
    st.caption("These apps are fictional, built from common patterns in real offers.")
    pick = st.radio("Sample offer", list(SAMPLES.keys()), label_visibility="collapsed")
    st.code(SAMPLES[pick]["text"], language=None, wrap_lines=True)
    go_sample = st.button("Check this sample", type="primary", key="go_sample")


# ---------- run ----------
def _run(text="", image=None, app_name="", sample_terms=None):
    if client:
        steps = st.status("Checking the loan…", expanded=True)
        def progress(_step, msg):
            steps.write(msg)
        try:
            client.log.clear()
            a = run(client, text=text, image=image, app_name=app_name, languages=tuple(langs), progress=progress)
            steps.update(label="Done", state="complete", expanded=False)
            return a
        except Exception as e:
            steps.update(label="Nemotron call failed", state="error")
            st.error(f"The AI step failed: {e}. Showing the offline check instead." if sample_terms
                     else f"The AI step failed: {e}. Check your API key and model IDs in settings.")
            if sample_terms:
                return run_offline(sample_terms)
            return None
    if sample_terms:
        return run_offline(sample_terms)
    st.warning("Reading free text and screenshots needs Nemotron. Add a NEBIUS_API_KEY, or try a sample offer.")
    return None


if go_text and text_in.strip():
    st.session_state["result"] = _run(text=text_in, app_name=name_for_text)
elif go_img and up:
    st.session_state["result"] = _run(image=(up.getvalue(), up.type or "image/png"), text="", app_name=name_for_img)
elif go_name:
    st.session_state["result"] = _run(app_name=only_name)
elif go_sample:
    s = SAMPLES[pick]
    st.session_state["result"] = _run(text=s["text"], app_name=s["app_name"], sample_terms=s["terms"])


# ---------- render ----------
def trace_rows(calls):
    """Group model calls by step so 20+ small calls read as a handful of rows."""
    order, agg = [], {}
    for c in calls:
        step = c["step"].split(" (")[0] if c["step"].startswith(("translate", "fix")) else c["step"]
        step = "translate to Telugu / Hindi" if step in ("translate", "fix sentence") else step
        key = (step, c["model"])
        if key not in agg:
            agg[key] = {"step": step, "model": c["model"], "calls": 0, "model seconds": 0.0, "tokens": 0}
            order.append(key)
        agg[key]["calls"] += 1
        agg[key]["model seconds"] = round(agg[key]["model seconds"] + (c.get("seconds") or 0), 1)
        agg[key]["tokens"] += c.get("tokens") or 0
    return [agg[k] for k in order]


def rupees(x):
    return f"₹{x:,.0f}"


def render(a: Analysis):
    v = (a.verdict or {}).get("verdict", "RISKY").upper()
    if v not in {"AVOID", "RISKY", "SAFE"}:
        v = "RISKY"
    t, c = a.terms, a.cost
    app = html.escape(str(t.get("app_name") or t.get("lender_name") or "This loan"))

    rows = ""
    apr_block = ""
    if c:
        rows = (f'<div class="ll-row"><span>Amount promised</span><b>{rupees(t.get("principal") or 0)}</b></div>'
                f'<div class="ll-row"><span>Amount you actually receive</span><b>{rupees(c["net_disbursed"])}</b></div>'
                f'<div class="ll-row"><span>Total you must repay</span><b>{rupees(c["total_repayable"])}</b></div>'
                f'<div class="ll-row"><span>Cost for every ₹100 you receive</span><b>{rupees(c["cost_per_100"])}</b></div>')
        claim = html.escape(str(t.get("stated_rate") or "")) or "not stated"
        apr_block = (f'<div class="ll-apr"><div class="label">Real yearly cost (APR)</div>'
                     f'<div class="num v-{v}">{c["apr_simple"] * 100:,.0f}%</div>'
                     f'<div class="claim">The app says: “{claim}”</div></div>')
    else:
        rows = '<div class="ll-row"><span>No cost details found. Paste the offer text to compute the real cost.</span></div>'

    st.markdown(f'<div class="ll-receipt"><div class="ll-stamp v-{v}">{v}</div>'
                f'<div class="app">{app}</div>{rows}{apr_block}</div>', unsafe_allow_html=True)

    if a.calls:
        secs = sum(x.get("seconds") or 0 for x in a.calls)
        st.markdown(f'<div class="ll-note">Analysed live: {len(a.calls)} NVIDIA Nemotron calls on Nebius Token Factory'
                    f'{" plus Tavily web search" if a.sources else ""}, {secs:.1f}s of model time.</div>', unsafe_allow_html=True)

    lang_tabs = ["English"] + [LANGS[l] for l in a.translations]
    tabs = st.tabs(lang_tabs)
    blocks = [a.verdict] + [a.translations[l] for l in a.translations]
    for tab, b in zip(tabs, blocks):
        with tab:
            st.markdown(f'<p class="ll-headline">{html.escape(str(b.get("headline", "")))}</p>', unsafe_allow_html=True)
            if b.get("reasons"):
                st.markdown("**Why**")
                st.markdown("\n".join(f"- {r}" for r in b["reasons"]))
            if b.get("next_steps"):
                st.markdown("**What to do now**")
                st.markdown("\n".join(f"- {r}" for r in b["next_steps"]))

    if a.flags:
        st.markdown(f"### Red flags ({len(a.flags)})")
        for f in a.flags:
            st.markdown(f'<div class="ll-flag {f["severity"]}"><b>{html.escape(f["title"])}</b>'
                        f'<p>{html.escape(f["detail"])}</p></div>', unsafe_allow_html=True)

    st.markdown("### Is the lender real?")
    vf = a.verification or {}
    status = vf.get("status", "unverified")
    label = {"regulated": "Regulated lender found", "warning": "Warnings found", "unverified": "Could not verify"}.get(status, status)
    src_html = ""
    for ev in vf.get("evidence") or []:
        i = ev.get("source_index")
        if isinstance(i, int) and 0 <= i < len(a.sources):
            s = a.sources[i]
            src_html += (f'<div class="ll-src">• {html.escape(ev.get("claim", ""))} '
                         f'<a href="{html.escape(s["url"])}" target="_blank">[{html.escape(s["title"][:60] or "source")}]</a></div>')
    reg = f'<div class="ll-note">Lender named in evidence: {html.escape(vf["regulated_lender"])}</div>' if vf.get("regulated_lender") else ""
    st.markdown(f'<div class="ll-verify"><span class="ll-pill p-{status}">{label}</span>'
                f'<div>{html.escape(vf.get("summary", ""))}</div>{reg}{src_html}</div>', unsafe_allow_html=True)

    with st.expander("How this was worked out"):
        st.markdown("**The math** (computed in Python, not by the AI)")
        st.latex(r"\text{APR} = \frac{\text{repay} - \text{received}}{\text{received}} \times \frac{365}{\text{days}}")
        if c:
            for n in c.get("notes", []):
                st.markdown(f"- {n}")
            if c.get("apr_effective"):
                st.markdown(f"- With compounding, the effective yearly rate is about {c['apr_effective'] * 100:,.0f}%.")
        if a.calls:
            st.markdown("**Agent trace** (Nemotron calls on Nebius Token Factory)")
            st.dataframe(trace_rows(a.calls), hide_index=True, use_container_width=True)
        elif a.mode == "offline":
            st.caption("Offline mode: no AI calls were made. Terms came from the sample's pre-filled fields.")
        st.markdown("**Extracted terms**")
        st.json(a.terms, expanded=False)
        st.download_button("Download full report (JSON)", a.to_json(), file_name="loanlens_report.json", mime="application/json")


res = st.session_state.get("result")
if res:
    st.markdown("---")
    render(res)
