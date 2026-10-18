"""Live lender verification with Tavily search.

Tavily returns clean, source-attributed web results. LoanLens runs a few
targeted searches (regulation status, partner bank/NBFC, complaints and
warnings) and hands the evidence to Nemotron Super to summarise. Every claim
in the summary must point back to one of these sources.
"""
from __future__ import annotations

from .llm import _setting


def tavily_key() -> str | None:
    return _setting("TAVILY_API_KEY")


def search_lender(name: str, partner: str | None = None, max_results: int = 4) -> list[dict]:
    from tavily import TavilyClient

    client = TavilyClient(api_key=tavily_key())
    queries = [
        f"{name} loan app RBI registered NBFC lending partner",
        f"{name} loan app complaints harassment fraud",
    ]
    if partner:
        queries.append(f"{partner} NBFC RBI registration")

    seen, results = set(), []
    for q in queries:
        try:
            resp = client.search(q, max_results=max_results, search_depth="advanced")
        except Exception as e:  # network / quota issues shouldn't kill the analysis
            results.append({"query": q, "error": str(e)})
            continue
        for r in resp.get("results", []):
            url = r.get("url")
            if url in seen:
                continue
            seen.add(url)
            results.append({
                "query": q,
                "title": r.get("title", ""),
                "url": url,
                "content": (r.get("content") or "")[:700],
            })
    return results


VERIFY_SYSTEM = """You verify Indian lending apps for consumers.
You get web search results about a lending app. Decide what the evidence shows.

Return ONLY JSON:
{
  "status": "regulated" | "unverified" | "warning",
  "regulated_lender": string or null,       // bank/NBFC named in the evidence, if any
  "summary": string,                        // 2-3 plain sentences
  "evidence": [ {"claim": string, "source_index": int} ]   // max 4, index into the results list
}

Rules:
- "regulated" only if a source clearly ties the app to an RBI-regulated bank or NBFC.
- "warning" if sources report harassment, fraud, bans, police cases or removal from app stores.
- Otherwise "unverified". Absence of evidence is NOT proof of fraud; say so plainly.
- Only cite a source if it actually names the app or its lender; generic advice articles are not evidence. If no source names them, evidence must be an empty list.
- Never invent sources or facts that are not in the results."""
