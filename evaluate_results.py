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

EMOJI = {"win": "✅", "lose": "❌", "pending": "⏳"}

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

def _fixture_id_from_leg(leg: Dict[str, Any]) -> Optional[int]:
    for key in ("fixture_id", "fid", "fixtureId", "fixtureID"):
        if key in leg:
            try:
                return int(leg[key])
            except (TypeError, ValueError):
                return None
    return None


def _market_from_leg(leg: Dict[str, Any]) -> str:
    for key in ("market", "market_name", "market_display"):
        val = leg.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if val not in (None, ""):
            return str(val)
    return ""


def _pick_from_leg(leg: Dict[str, Any]) -> str:
    for key in ("pick", "pick_name", "selection", "value"):
        val = leg.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if val not in (None, ""):
            return str(val)
    return ""


def _decorate_with_mark(text: Any, mark: str) -> Any:
    if not mark or text is None:
        return text
    text_str = str(text)
    if not text_str:
        return text
    return f"{text_str} {mark}"


def judge_leg(leg: Dict[str, Any], fx: Dict[str, Any]) -> Dict[str, Any]:
    res = {
        "fixture_id": leg["fixture_id"],
        "market": leg["market"],
        "pick": leg["pick"],
        "result": "pending",
    }
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
    ticket_src = src.get("ticket") if isinstance(src, dict) else None
    if isinstance(ticket_src, dict):
        base = ticket_src
    else:
        base = src if isinstance(src, dict) else {}

    date_val = None
    target_val = None
    total_val = None
    if isinstance(src, dict):
        date_val = src.get("date") or None
        target_val = src.get("target_odds") if src.get("target_odds") is not None else None
        total_val = src.get("total_odds") if src.get("total_odds") is not None else None
    else:
        date_val = None
    if isinstance(base, dict):
        if date_val is None:
            date_val = base.get("date")
        if target_val is None:
            target_val = base.get("target_odds")
        if total_val is None:
            total_val = base.get("total_odds")

    out = {
        "date": date_val,
        "target_odds": target_val,
        "total_odds": total_val,
        "legs": [],
        "ticket_result": "pending",
        "ticket_result_emoji": "",
        "wins": 0,
        "loses": 0,
        "pendings": 0,
    }
    if "name" in src:
        out["name"] = src["name"]
    fx_cache: Dict[int, Dict[str, Any]] = {}
    all_done = True
    all_win = True

    legs_list = base.get("legs") if isinstance(base, dict) else []
    if not isinstance(legs_list, list):
        legs_list = []

    for L in legs_list:
        if not isinstance(L, dict):
            continue
        fid = _fixture_id_from_leg(L)
        if fid is None:
            all_done = False
            all_win = False
            pending_leg = dict(L)
            pending_leg.setdefault("result", "pending")
            leg_pick_raw = _pick_from_leg(L)
            pending_mark = EMOJI.get("pending", "")
            pending_leg.setdefault("pick_original", leg_pick_raw)
            if "pick" in pending_leg or leg_pick_raw:
                original_pick = pending_leg.get("pick", leg_pick_raw)
                pending_leg["pick"] = _decorate_with_mark(original_pick, pending_mark)
            if "pick_display" in pending_leg:
                original_display = pending_leg["pick_display"]
                pending_leg.setdefault("pick_display_original", original_display)
                pending_leg["pick_display"] = _decorate_with_mark(original_display, pending_mark)
            pending_leg["result_emoji"] = pending_mark
            out["legs"].append(pending_leg)
            out["pendings"] += 1
            continue

        fx = fx_cache.get(fid)
        if fx is None:
            fx = _get_fixture(fid)
            fx_cache[fid] = fx

        leg_market = _market_from_leg(L)
        leg_pick = _pick_from_leg(L)
        r = judge_leg(
            {
                "fixture_id": fid,
                "market": leg_market,
                "pick": leg_pick,
            },
            fx,
        )

        mark = EMOJI.get(r["result"], "")
        decorated = dict(L)
        decorated["fixture_id"] = fid
        decorated["market"] = leg_market
        decorated["pick_original"] = leg_pick
        decorated["pick"] = _decorate_with_mark(leg_pick, mark)
        if "pick_display" in decorated:
            original_display = decorated["pick_display"]
            decorated["pick_display_original"] = original_display
            decorated["pick_display"] = _decorate_with_mark(original_display, mark)
        decorated["result"] = r["result"]
        decorated["result_emoji"] = mark
        if "score_ft" in r:
            decorated["score_ft"] = r["score_ft"]
        if "score_ht" in r:
            decorated["score_ht"] = r["score_ht"]
        out["legs"].append(decorated)

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

    out["ticket_result_emoji"] = EMOJI.get(out["ticket_result"], "")
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
    daily = {"date": None, "evaluated_at_utc": datetime.now(timezone.utc).isoformat(), "tickets": []}

    for key, src in tickets:
        out = evaluate_ticket(src)
        if daily["date"] is None:
            # Prefer evaluated ticket date, fall back to source structure
            if isinstance(src, dict):
                ticket_obj = src.get("ticket") if isinstance(src.get("ticket"), dict) else {}
                daily["date"] = src.get("date") or ticket_obj.get("date")
            if daily["date"] is None:
                daily["date"] = out.get("date")
        daily["tickets"].append({
            "name": key,
            "ticket_result": out["ticket_result"],
            "ticket_result_emoji": out.get("ticket_result_emoji", ""),
            "wins": out["wins"],
            "loses": out["loses"],
            "pendings": out["pendings"],
        })
        with open(f"public/eval_{key}.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    with open("public/daily_log.json", "w", encoding="utf-8") as f:
        json.dump(daily, f, ensure_ascii=False, indent=2)

    print(json.dumps({"ok": True, "outputs": ["public/eval_2plus.json","public/eval_3plus.json","public/eval_4plus.json","public/daily_log.json"]}))
    
if __name__ == "__main__":
    main()
