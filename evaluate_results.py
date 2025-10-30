import os
import json
from datetime import datetime, timezone
import requests
from typing import Any, Dict, Tuple, List

PUBLIC_DIR = "public"
API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE = "https://v3.football.api-sports.io"

FILES = [
    ("2plus", os.path.join(PUBLIC_DIR, "2plus.json")),
    ("3plus", os.path.join(PUBLIC_DIR, "3plus.json")),
    ("4plus", os.path.join(PUBLIC_DIR, "4plus.json")),
]

def _ensure_public_dir():
    os.makedirs(PUBLIC_DIR, exist_ok=True)

def _fixture_id_from_leg(leg: Dict[str, Any]) -> int | None:
    for key in ("fixture_id", "fid", "fixtureId", "fixtureID"):
        v = leg.get(key)
        if v:
            return int(v)
    return None

def _normalize_ou_pick(p: str) -> str:
    p = (p or "").strip()
    low = p.lower()
    if low.startswith("over "):
        return "O" + p.split(" ", 1)[1].strip()
    if low.startswith("under "):
        return "U" + p.split(" ", 1)[1].strip()
    return p

def _get_fixture(fixture_id: int) -> Dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("API_FOOTBALL_KEY missing")
    url = f"{BASE}/fixtures?id={fixture_id}"
    r = requests.get(url, headers={"x-apisports-key": API_KEY}, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data.get("response"):
        return {}
    return data["response"][0]

def judge_leg(leg: Dict[str, Any]) -> Tuple[bool, str]:
    fid = _fixture_id_from_leg(leg)
    if not fid:
        return False, "❌"
    fx = _get_fixture(fid)
    if not fx:
        return False, "⏳"

    status = fx["fixture"]["status"]["short"]
    # ako nije FT, ne ocenjuj
    if status not in ("FT", "AET", "PEN"):
        return False, "⏳"

    gh = fx["goals"]["home"] or 0
    ga = fx["goals"]["away"] or 0

    m = leg.get("market", "").strip()
    p = leg.get("pick", "").strip()
    ok = False

    # Double Chance
    if m == "Double Chance" or m == "DC":
        if p == "1X":
            ok = gh >= ga
        elif p == "X2":
            ok = ga >= gh
        elif p == "12":
            ok = gh != ga

    # BTTS
    elif m == "BTTS":
        if p == "Yes":
            ok = (gh > 0 and ga > 0)
        elif p == "No":
            ok = not (gh > 0 and ga > 0)

    # Match Winner
    elif m == "Match Winner":
        if p == "Home":
            ok = gh > ga
        elif p == "Away":
            ok = ga > gh
        elif p == "Draw":
            ok = gh == ga

    # Over/Under
    elif m == "Over/Under":
        p_norm = _normalize_ou_pick(p)
        if p_norm.startswith("O"):
            try:
                line = float(p_norm[1:])
                ok = (gh + ga) > line - 1e-9
            except Exception:
                ok = False
        elif p_norm.startswith("U"):
            try:
                line = float(p_norm[1:])
                ok = (gh + ga) < line + 1e-9
            except Exception:
                ok = False

    return ok, ("✅" if ok else "❌")

def evaluate_file(key: str, path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {
            "ticket_result": "missing",
            "ticket_result_emoji": "⏳",
            "legs": [],
        }
    with open(path, "r", encoding="utf-8") as f:
        src = json.load(f)

    ticket = src.get("ticket") or src
    legs = ticket.get("legs", [])

    evaluated_legs = []
    all_ok = True
    for leg in legs:
        ok, emoji = judge_leg(leg)
        # pick ostaje isti ali dodajemo emoji
        leg_out = dict(leg)
        leg_out["result_emoji"] = emoji
        if emoji in ("✅", "❌"):
            leg_out["pick"] = f"{leg.get('pick','')} {emoji}".strip()
        evaluated_legs.append(leg_out)
        if not ok:
            all_ok = False

    out = {
        "date": src.get("date"),
        "ticket": {
            "target": ticket.get("target"),
            "total_odds": ticket.get("total_odds"),
            "legs": evaluated_legs,
        },
        "ticket_result": "win" if all_ok else "lose",
        "ticket_result_emoji": "✅" if all_ok else "❌",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat()
    }

    _ensure_public_dir()
    with open(os.path.join(PUBLIC_DIR, f"eval_{key}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    return out

def run():
    _ensure_public_dir()
    results = {}
    for key, path in FILES:
        results[key] = evaluate_file(key, path)
    # večernji log u poseban fajl da ne pregazi jutarnji
    with open(os.path.join(PUBLIC_DIR, "daily_eval.json"), "w", encoding="utf-8") as f:
        json.dump({
            "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
            "files": list(results.keys())
        }, f, ensure_ascii=False, indent=2)
    return results

if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
