#!/usr/bin/env python3
"""NURU CLI simulator: chat with the full pipeline locally, no SMS needed.

  python scripts/simulate.py                 interactive chat
  python scripts/simulate.py --demo          run a scripted demo conversation
  python scripts/simulate.py -m "swali"      send one message and exit
  python scripts/simulate.py --verbose       also show category, rule and sources

Uses whatever NURU_LLM_PROVIDER is set (default "none", fully offline).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nuru.router import Reply, Router  # noqa: E402

DEMO_MESSAGES = [
    "MSAADA",
    "Je ni kweli uzazi wa mpango unaleta utasa?",
    "hedhi yangu haiji kwa mpangilio",
    "nianze kliniki ya ujauzito lini",
    "Ni kweli mjamzito asile mayai?",
    "Nina mimba ya miezi 6 natoka damu",
    "mtoto wangu mchanga hanyonyi",
    "KITUO",
    "Makole",
    "KITUO Ipagla",
    "Nimekosa tarehe ya chanjo ya mtoto",
    "bei ya mahindi sokoni leo",
]

PHONE = "+255700000000"  # dummy number for the simulator


def show(user: str, reply: Reply, verbose: bool) -> None:
    print(f"\n  MTUMIAJI > {user}")
    print(f"  NURU     < {reply.text}")
    if verbose:
        meta = [f"category={reply.category}", f"chars={len(reply.text)}", f"sms={reply.segments}"]
        if reply.rule_id:
            meta.append(f"rule={reply.rule_id}")
        if reply.content_ids:
            meta.append(f"content={','.join(reply.content_ids)}")
        if reply.source:
            meta.append(f"source={reply.source}")
        if reply.retrieval_score is not None:
            meta.append(f"score={reply.retrieval_score:.3f}")
        print("             [" + " ".join(meta) + "]")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat with NURU locally")
    parser.add_argument("--demo", action="store_true", help="run the scripted demo")
    parser.add_argument("-m", "--message", help="send a single message")
    parser.add_argument("-v", "--verbose", action="store_true", help="show routing details")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    router = Router.from_settings()
    print(f"NURU simulator | LLM provider: {router.provider.name} | "
          f"content entries: {len(router.retriever.entries)} | facilities: {len(router.finder.facilities)}")
    if router.sample_facility_data:
        print("Facility data: SAMPLE ONLY, not the official MoH HFR.")

    if args.message:
        show(args.message, router.handle(PHONE, args.message), args.verbose)
        return 0

    if args.demo:
        for msg in DEMO_MESSAGES:
            show(msg, router.handle(PHONE, msg), args.verbose)
        return 0

    print("Andika ujumbe (au 'exit' kutoka).")
    while True:
        try:
            msg = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if msg.lower() in {"exit", "quit", "toka"}:
            return 0
        show(msg, router.handle(PHONE, msg), args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
