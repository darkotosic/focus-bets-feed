#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json
from pathlib import Path
from datetime import datetime, timezone

OUT_DIR = Path("public")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def load_fixture_result(fid: int) -> dict:
    # ovde ide pravi API-Football poziv
    # sada sve FT 0-0 da ne puca
    return {
        "status": "FT",
        "home_goals": 0,
        "away_goals": 0,
    }

def leg_hit(leg: dict, res: dict) -> bool:
    hg = res["home_goals"]
    ag = res["away_goals"]
    mkt = leg.get("market")
    pick = leg.get("pick")

    if res["status"] != "FT":
        return False

    if mkt == "Match Winner":
        if pick == "Home":
            return hg > ag
        if pick == "Away":
            return ag > hg
        return False

    if mkt == "Double Chance":
        if pick == "1X":
            return hg >= ag
        if pick == "X2":
            return ag >= hg
        if pick == "12":
            return hg != ag
        return False

    if mkt == "BTTS":
        if pick == "Yes":
            return (hg > 0 and ag > 0)
        if pick == "No":
            return not (hg > 0 and ag > 0)
        return False

    if mkt == "Over/Under":
        try:
            parts = pick.split()
            ou = parts[0].lower()   # over / under
            line = float(parts[1])
            goals = hg + ag
            if ou == "over":
                return goals > line - 1e-9
            else:
                return goals < line + 1e-9
        except Exception:
            return False

    # za ostala tržišta nemamo podatke u placeholderu
    return False

def evaluate_ticket(ticket: dict) -> dict:
    legs = ticket.get("legs") or []
    all_hit = True
    out_legs = []

    for leg in legs:
        fid = leg.get("fid")
        res = load_fixture_result(fid)
        ok = leg_hit(leg, res)
        out_legs.append({
            **leg,
            "result": {
                "status": res["status"],
                "home_goals": res["home_goals"],
                "away_goals": res["away_goals"],
                "hit": ok,
                "emoji": "✅" if ok else "❌"
            }
        })
        if not ok:
            all_hit = False

    total_odds = float(ticket.get("total_odds", 0))
    total_label = f"{total_odds:.2f}"
    if all_hit and legs:
        total_label = f"{total_label} ✅"

    return {
        "total_odds": total_odds,
        "total_label": total_label,
        "all_hit": all_hit,
        "legs": out_legs,
    }

def load_ticket_file(name: str) -> dict:
    path = OUT_DIR / name
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = {
        "date": date_str,
        "tickets": {}
    }

    for name in ["2plus.json", "3plus.json", "4plus.json"]:
        raw = load_ticket_file(name)
        if not raw:
            result["tickets"][name] = {
                "exists": False,
                "evaluated": False,
                "ticket": None
            }
            continue

        ticket = raw.get("ticket") or {}
        evaluated = evaluate_ticket(ticket)
        result["tickets"][name] = {
            "exists": True,
            "evaluated": True,
            "ticket": evaluated
        }

    out_path = OUT_DIR / "evaluation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps({"status": "ok", "file": str(out_path)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
