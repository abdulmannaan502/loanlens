"""Batch job: analyse a list of loan apps and write a risk watchlist.

Designed to run as a Nebius Serverless Job on a schedule, so the expensive
work (web verification + Nemotron Ultra reasoning for many apps) happens in
the background instead of while a user waits.

Usage:
    python -m jobs.watchlist_job apps.txt watchlist.json

apps.txt has one app name per line. Requires NEBIUS_API_KEY and TAVILY_API_KEY
in the environment.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from loanlens.llm import NemotronClient
from loanlens.pipeline import run


def main(src: str, dst: str) -> None:
    client = NemotronClient.from_settings()
    if client is None:
        sys.exit("NEBIUS_API_KEY is not set.")
    names = [l.strip() for l in open(src, encoding="utf-8") if l.strip() and not l.startswith("#")]
    out = []
    for name in names:
        client.log.clear()
        try:
            a = run(client, app_name=name, languages=())
            out.append({"app": name, "verdict": a.verdict.get("verdict"), "headline": a.verdict.get("headline"),
                        "lender_status": a.verification.get("status"),
                        "sources": [s["url"] for s in a.sources][:5]})
            print(f"{name}: {a.verdict.get('verdict')}")
        except Exception as e:
            out.append({"app": name, "error": str(e)})
            print(f"{name}: failed ({e})")
    json.dump({"generated_at": datetime.now(timezone.utc).isoformat(), "apps": out},
              open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
