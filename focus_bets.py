#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os, sys, json, time, re
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx

# ===== ENV =====
API_KEY = os.getenv("API_FOOTBALL_KEY")  # GitHub secret
BASE_URL = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Belgrade")
TZ = ZoneInfo(TIMEZONE)

# ciljne kvote i ograničenja
TARGETS = [float(x) for x in os.getenv("TICKET_TARGETS", "2.0,3.0,4.0").split(",")]
LEGS_MIN = int(os.getenv("LEGS_MIN", "3"))
LEGS_MAX = int(os.getenv("LEGS_MAX", "7"))
MAX_PER_COUNTRY = int(os.getenv("MAX_PER_COUNTRY", "2"))
MAX_HEAVY_FAVORITES = int(os.getenv("MAX_HEAVY_FAVORITES", "1"))
RELAX_STEPS = int(os.getenv("RELAX_STEPS", "2"))
RELAX_ADD = float(os.getenv("RELAX_ADD", "0.03"))
DEBUG = os.getenv("DEBUG", "1") == "1"

def _log(s: str): 
    if DEBUG:
        print(s, file=sys.stderr, flush=True)

# ===== CAP LIMITI po tržištu =====
BASE_TH: Dict[Tuple[str, str], float] = {
    ("Double Chance", "1X"): 1.20, ("Double Chance", "X2"): 1.25, ("Double Chance", "12"): 1.32,
    ("BTTS", "Yes"): 1.60, ("BTTS", "No"): 1.60,
    ("Over/Under", "O1.5"): 1.22, ("Over/Under", "O2.0"): 1.35, ("Over/Under", "O2.5"): 1.55,
    ("Match Winner", "Home"): 1.44, ("Match Winner", "Away"): 1.60,
    ("1st Half Goals", "O0.5"): 1.28, ("1st Half Goals", "O1.0"): 1.52,
}

# ===== HTTP helper =====
def _http(method: str, path: str, params: Dict[str, Any]) -> Any:
    url = f"{BASE_URL}{path}"
    headers = {"x-apisports-key": API_KEY}
    backoff = 1.2
    last = None
    for _ in range(6):
        try:
            with httpx.Client(timeout=25.0) as cli:
                r = cli.request(method, url, params=params or {}, headers=headers)
            if r.status_code == 200:
                j = r.json()
                return j.get("response", j)
            last = (r.status_code, r.text[:300])
            _log(f"HTTP {r.status_code}: {r.text[:200]}")
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ProtocolError) as e:
            last = (None, str(e))
            _log(f"HTTP transient {e.__class__.__name__}: {e}")
        time.sleep(backoff)
        backoff *= 1.7
    raise RuntimeError(f"HTTP retries exhausted: {last}")

def _fmt_dt_local(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso

def _try_float(x: Any) -> Optional[float]:
    try:
        v = float(x)
        return v if v > 0 else None
    except Exception:
        return None

def _to_s(x: Any) -> str:
    return str(x).strip() if x is not None else ""

# ===== ODDS parsing (robustno, bez .strip nad int) =====
def best_market_odds(resp: Any) -> Dict[str, Dict[str, float]]:
    """Vrati najbolje kvote po tržištu. Radi sa različitim oblicima responsa."""
    data: List[Dict[str, Any]] = []
    if isinstance(resp, dict):
        data = resp.get("response") or []
    elif isinstance(resp, list):
        data = resp
    else:
        return {}

    pool: Dict[Tuple[str, str], float] = {}

    def put(mkt: str, pick: str, odd_raw: Any):
        odd = _try_float(odd_raw)
        if odd is None:
            return
        key = (mkt, pick)
        if odd > pool.get(key, 0.0):
            pool[key] = odd

    for entry in data:
        for bm in entry.get("bookmakers", []) or []:
            for bet in bm.get("bets", []) or []:
                name = _to_s(bet.get("name"))
                # normalize imena tržišta
                if re.search(r"(?i)over.?under", name):
                    mkt = "Over/Under"
                elif re.search(r"(?i)both.*score", name):
                    mkt = "Both Teams To Score"
                else:
                    mkt = name

                for v in bet.get("values", []) or []:
                    val = _to_s(v.get("value"))
                    line = _to_s(v.get("handicap") or v.get("line"))
                    odd = v.get("odd")

                    # normalizacija naziva za MW/DC
                    if mkt == "Match Winner":
                        if re.search(r"(?i)^home", val): val = "Home"
                        elif re.search(r"(?i)^away", val): val = "Away"
                        elif re.search(r"(?i)^draw", val): val = "Draw"

                    if mkt == "Double Chance":
                        # očekuje "1X","12","X2"
                        val = val.replace(" ", "").upper()

                    if mkt == "Over/Under" and line:
                        # očekuje "Over 2.5"/"Under 2.5"
                        val = f"{val} {line}".strip()

                    put(mkt, val, odd)

    # Vratimo samo ono što ostatak koda koristi
    out: Dict[str, Dict[str, float]] = {}
    def pick(mkt: str, opts: List[str]):
        best_val = None
        best_odd = 0.0
        for o in opts:
            odd = pool.get((mkt, o))
            if odd and odd > best_odd:
                best_odd = odd
                best_val = o
        if best_val:
            out.setdefault(mkt, {})[best_val] = best_odd

    pick("Match Winner", ["Home", "Draw", "Away"])
    pick("Double Chance", ["1X", "12", "X2"])
    pick("Both Teams To Score", ["Yes", "No"])
    pick("Over/Under", ["Over 2.5", "Under 2.5", "Over 1.5", "Under 1.5"])
    pick("1st Half Winner", ["Home", "Draw", "Away"])
    pick("1st Half Goals", ["O0.5", "O1.0", "O1.5"])  # ako API mapira tako

    return out

# ===== API wrappers =====
def fetch_fixtures(date_str: str) -> List[Dict[str, Any]]:
    return _http("GET", "/fixtures", {"date": date_str})

def fetch_odds_best(fid: int) -> Dict[str, Dict[str, float]]:
    resp = _http("GET", "/odds", {"fixture": fid})
    return best_market_odds(resp) or {}

# ===== legs assemble =====
def assemble_legs(date_str: str, caps: Dict[Tuple[str, str], float]) -> List[Dict[str, Any]]:
    legs = []
    for f in fetch_fixtures(date_str):
        fx = f.get("fixture", {}) or {}
        lg = f.get("league", {}) or {}
        tm = f.get("teams", {}) or {}
        fid = fx.get("id")
        if not fid:
            continue

        odds = fetch_odds_best(int(fid))
        best_market = None
        best_name = None
        best_odd = 0.0

        # Prođi kroz dostupna tržišta i uzmi najbolju kvotu ispod cap-a
        for (mkt, variants) in odds.items():
            for name, odd in variants.items():
                cap = caps.get((mkt, name))
                if cap is None:
                    continue
                if odd < cap and odd > best_odd:
                    best_market = mkt
                    best_name = name
                    best_odd = odd

        if best_market:
            home = (tm.get("home") or {}).get("name")
            away = (tm.get("away") or {}).get("name")
            legs.append({
                "fid": int(fid),
                "country": (lg.get("country") or "").strip() or "World",
                "league": f"{lg.get('country','')} — {lg.get('name','')}",
                "home": home,
                "away": away,
                "kickoff_local": _fmt_dt_local(fx.get("date", "")),
                "market": best_market,
                "pick_name": best_name,
                "odd": float(best_odd),
            })

    legs.sort(key=lambda L: L["odd"], reverse=True)
    _log(f"legs candidates={len(legs)}")
    return legs

def _product(vals: List[float]) -> float:
    p = 1.0
    for v in vals:
        p *= v
    return p

def _diversity_ok(ticket: List[Dict[str, Any]], cand: Dict[str, Any]) -> bool:
    countries = [x["country"] for x in ticket] + [cand["country"]]
    if countries.count(cand["country"]) > MAX_PER_COUNTRY:
        return False
    heavy = sum(1 for x in ticket if x["odd"] < 1.20) + (1 if cand["odd"] < 1.20 else 0)
    if heavy > MAX_HEAVY_FAVORITES:
        return False
    if any(x["fid"] == cand["fid"] for x in ticket):
        return False
    return True

def _build_for_target(legs: List[Dict[str, Any]], target: float) -> Optional[List[Dict[str, Any]]]:
    best = None

    def score(t: List[Dict[str, Any]]) -> float:
        return abs(_product([x["odd"] for x in t]) - target)

    # greedy + mali backtrack
    for L in legs:
        t = [L]
        for R in legs:
            if len(t) >= LEGS_MAX:
                break
            if R is L:
                continue
            if not _diversity_ok(t, R):
                continue
            t2 = t + [R]
            if _product([x["odd"] for x in t2]) <= target * 1.12 and len(t2) <= LEGS_MAX:
                t = t2
            if _product([x["odd"] for x in t]) >= target and len(t) >= LEGS_MIN:
                cand = t[:]
                if not best or score(cand) < score(best):
                    best = cand
                break
        if best:
            break
    return best

def build_three_tickets(date_str: str) -> List[List[Dict[str, Any]]]:
    tickets: List[List[Dict[str, Any]]] = []
    used = set()
    caps = dict(BASE_TH)
    for _ in range(RELAX_STEPS + 1):
        legs = [L for L in assemble_legs(date_str, caps) if L["fid"] not in used]
        for target in TARGETS:
            if len(tickets) >= len(TARGETS):
                break
            built = _build_for_target(legs, target)
            if built:
                tickets.append(built)
                used.update(x["fid"] for x in built)
        if len(tickets) == len(TARGETS):
            break
        # relaksiraj pragove
        for k in list(caps.keys()):
            caps[k] = caps[k] + RELAX_ADD
    return tickets

# ===== JSON export =====
def write_public_json(date_str: str, tickets: List[List[Dict[str, Any]]]) -> None:
    os.makedirs("public", exist_ok=True)
    mapping = {2: "2plus.json", 3: "3plus.json", 4: "4plus.json"}
    for idx, built in enumerate(tickets):
        target_round = int(TARGETS[idx])
        name = mapping.get(target_round, f"{target_round}plus.json")
        payload = {
            "date": date_str,
            "target_odds": TARGETS[idx],
            "total_odds": round(_product([x["odd"] for x in built]), 2),
            "legs": [
                {
                    "fixture_id": x["fid"],
                    "league": x["league"],
                    "home": x["home"],
                    "away": x["away"],
                    "kickoff_local": x["kickoff_local"],
                    "market": x["market"],
                    "pick": x["pick_name"],
                    "odds": x["odd"],
                }
                for x in built
            ],
        }
        with open(os.path.join("public", name), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

def run(date_str: Optional[str] = None) -> Dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("Missing API_FOOTBALL_KEY")
    if not date_str:
        date_str = datetime.now(TZ).strftime("%Y-%m-%d")
    _log(f"run date={date_str} targets={TARGETS}")
    tickets = build_three_tickets(date_str)
    _log(f"built_tickets={len(tickets)}")
    write_public_json(date_str, tickets)
    return {
        "ok": True,
        "date": date_str,
        "files": ["public/2plus.json", "public/3plus.json", "public/4plus.json"],
    }

if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
