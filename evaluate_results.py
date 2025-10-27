#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, sys, time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import httpx

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io")

FILES = [
    ("2plus", "public/2plus.json"),
    ("3plus", "public/3plus.json"),
    ("4plus", "public/4plus.json"),
]

def _http(path: str, params: Dict[str, Any]) -> Any:
    headers = {"x-apisports-key": API_KEY}
    url = f"{BASE_URL}{path}"
    backoff = 1.2
    for _ in range(6):
        try:
            with httpx.Client(timeout=20.0) as cli:
                r = cli.get(url, params=params, headers=headers)
            if r.status_code == 200:
                return r.json().get("response", [])
        except Exception:
            pass
        time.sleep(backoff); backoff *= 1.7
    raise RuntimeError("API call failed")

def _get_fixture(fid: int) -> Dict[str, Any]:
    resp = _http("/fixtures", {"id": fid})
    return resp[0] if resp else {}

def _ft(goals: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    try:
        return int(goals.get("home")), int(goals.get("away"))
    except Exception:
        return None, None

def _ht(score: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    s = score.get("halftime") or {}
    try:
        h = s.get("home"); a = s.get("away")
        return (int(h) if h is not None else None, int(a) if a is not None else None)
    except Exception:
        return None, None

def _pending(status: str) -> bool:
    # NS, TBD, PST, CANC, ABD, SUSP; also “1H/2H/HT” still running
    code = (status or "").upper()
    return code not in ("FT", "AET", "PEN")

def judge_leg(leg: Dict[str, Any], fx: Dict[str, Any]) -> Dict[str, Any]:
    res = {"fixture_id": leg["fixture_id"], "market": leg["market"], "pick": leg["pick"], "result": "pending"}
    st = ((fx.get("fixture") or {}).get("status") or {}).get("short", "")
    if _pending(st):
        return res

    gh, ga = _ft(fx.get("goals") or {})
    hth, hta = _ht(fx.get("score") or {})
    if gh is None or ga is None:
        return res  # no result visible

    ok = False
    m = (leg["market"] or "").strip()
    p = (leg["pick"] or "").strip()

    if m == "Double Chance":
        if p == "1X": ok = gh >= ga
        elif p == "X2": ok = ga >= gh
        elif p == "12": ok = gh != ga

    elif m == "BTTS":
        if p == "Yes": ok = (gh > 0 and ga > 0)
        elif p == "No": ok = not (gh > 0 and ga > 0)

    elif m == "Over/Under":
        # supports O1.5, O2.0, O2.5
        if p.startswith("O"):
            try:
                line = float(p[1:])
                ok = (gh + ga) > line - 1e-9  # over
            except Exception:
                ok = False
        elif p.startswith("U"):
            try:
                line = float(p[1:])
                ok = (gh + ga) < line + 1e-9  # under
            except Exception:
                ok = False

    elif m == "Match Winner":
        if p == "Home": ok = gh > ga
        elif p == "Away": ok = ga > gh
        elif p == "Draw": ok = gh == ga

    elif m == "1st Half Goals":
        # supports O0.5, O1.0
        if p.startswith("O"):
            try:
                line = float(p[1:])
                if hth is None or hta is None:
                    return res
                ok = (hth + hta) > line - 1e-9
            except Exception:
                ok = False

    res["result"] = "win" if ok else "lose"
    res["score_ft"] = f"{gh}-{ga}"
    if hth is not None and hta is not None:
        res["score_ht"] = f"{hth}-{hta}"
    return res

def evaluate_ticket(src: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "date": src.get("date"),
        "target_odds": src.get("target_odds"),
        "total_odds": src.get("total_odds"),
        "legs": [],
        "ticket_result": "pending",
        "wins": 0,
        "loses": 0,
        "pendings": 0,
    }
    all_done = True
    all_win = True

    for L in src.get("legs", []):
        fid = int(L["fixture_id"])
        fx = _get_fixture(fid)
        r = judge_leg(
            {
                "fixture_id": fid,
                "market": L["market"],
                "pick": L["pick"],
            },
            fx,
        )
        out["legs"].append(r)
        if r["result"] == "win":
            out["wins"] += 1
        elif r["result"] == "lose":
            out["loses"] += 1
            all_win = False
        else:
            out["pendings"] += 1
            all_done = False
            all_win = False

    if all_done:
        out["ticket_result"] = "win" if all_win else "lose"
    else:
        out["ticket_result"] = "pending"
    return out

def main() -> None:
    # učitaj ulaze
    tickets: List[Tuple[str, Dict[str, Any]]] = []
    for key, path in FILES:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            tickets.append((key, json.load(f)))

    if not tickets:
        print(json.dumps({"ok": False, "msg": "no input files"}))
        return

    # evaluacija
    os.makedirs("public", exist_ok=True)
    daily = {"date": tickets[0][1].get("date"), "evaluated_at_utc": datetime.now(timezone.utc).isoformat(), "tickets": []}

    for key, src in tickets:
        out = evaluate_ticket(src)
        daily["tickets"].append({"name": key, "ticket_result": out["ticket_result"], "wins": out["wins"], "loses": out["loses"], "pendings": out["pendings"]})
        with open(f"public/eval_{key}.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    with open("public/daily_log.json", "w", encoding="utf-8") as f:
        json.dump(daily, f, ensure_ascii=False, indent=2)

    print(json.dumps({"ok": True, "outputs": ["public/eval_2plus.json","public/eval_3plus.json","public/eval_4plus.json","public/daily_log.json"]}))
    
if __name__ == "__main__":
    main()
