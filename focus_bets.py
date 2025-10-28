# focus_bets.py
# Generates 2plus.json, 3plus.json, 4plus.json into ./public
# ENV: API_FOOTBALL_KEY ; optional DATE=YYYY-MM-DD

from __future__ import annotations
import os, sys, json, time, math, random, datetime as dt
from typing import Any, Dict, List, Tuple
import httpx

BASE = "https://v3.football.api-sports.io"
API_KEY = os.getenv("API_FOOTBALL_KEY") or ""
DATE = os.getenv("DATE") or dt.date.today().isoformat()

TARGETS = [2.0, 3.0, 4.0]
LEGS_MIN, LEGS_MAX = 3, 7
ALLOW_LIST: set[int] = set()   # ostavi prazno ili popuni ID-evima liga

# ---------- logging ----------

def _log(msg: str) -> None:
    print(msg, flush=True)

def _fail(msg: str) -> None:
    _log(f"ERROR: {msg}")
    sys.exit(1)

# ---------- HTTP ----------

def _http(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if not API_KEY:
        _fail("API_FOOTBALL_KEY is missing")
    headers = {"x-apisports-key": API_KEY}
    url = BASE + path
    last = None
    for i in range(6):
        try:
            r = httpx.get(url, params=params, headers=headers, timeout=30)
            last = r
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.2 * (i + 1))
                continue
            break
        except httpx.HTTPError as e:
            last = e
            time.sleep(1.0 * (i + 1))
    if isinstance(last, httpx.Response):
        raise RuntimeError(f"HTTP {last.status_code}: {last.text[:240]}")
    raise RuntimeError(f"HTTP error: {last!r}")

# ---------- API wrappers ----------

def fixtures_by_date(date_str: str) -> List[Dict[str, Any]]:
    j = _http("/fixtures", {"date": date_str})
    return j.get("response", [])

def odds_by_fixture(fid: int) -> List[Dict[str, Any]]:
    j = _http("/odds", {"fixture": fid})
    return j.get("response", [])

# ---------- odds parsing ----------

# Normalizacija naziva marketa iz API-FOOTBALL u kratke ključeve.
MKT_ALIASES = {
    "Match Winner": "MW",
    "Double Chance": "DC",
    "Both Teams To Score": "BTTS",
    "Over/Under": "OU",
}

def parse_best_market_odds(odds_resp: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    odds_resp: API response['response'] for /odds
    Returns: { 'BTTS': {'Yes':1.8,'No':1.9}, 'OU': {'Over 2.5':1.95,'Under 2.5':1.85}, 'DC': {...}, 'MW': {...} }
    """
    out: Dict[str, Dict[str, float]] = {}
    for bk in odds_resp:
        for bet in bk.get("bookmakers", []):
            for b in bet.get("bets", []):
                name = b.get("name", "")
                mkt = MKT_ALIASES.get(name)
                if not mkt:
                    continue
                values = b.get("values", []) or []
                for v in values:
                    vname = str(v.get("value", "")).strip()
                    odd_raw = v.get("odd")
                    try:
                        odd = float(odd_raw)
                    except Exception:
                        continue
                    if odd <= 1.01:
                        continue
                    out.setdefault(mkt, {})
                    # zadrži najbolju kvotu po izabranom ishodu
                    if vname and odd > out[mkt].get(vname, 0.0):
                        out[mkt][vname] = odd
    return out

# ---------- legs assembly ----------

def nice_time(iso_str: str) -> str:
    try:
        t = dt.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return t.strftime("%H:%M")
    except Exception:
        return iso_str

def collect_legs(date_str: str) -> List[Dict[str, Any]]:
    fx = fixtures_by_date(date_str)
    if ALLOW_LIST:
        fx = [f for f in fx if int(f["league"]["id"]) in ALLOW_LIST]
    _log(f"✅ fixtures found={len(fx)} ALLOW_LIST={'on' if ALLOW_LIST else 'off'}")

    legs: List[Dict[str, Any]] = []
    for f in fx:
        lg = f.get("league", {})
        tm = f.get("teams", {})
        fix = f.get("fixture", {})
        fid = int(fix.get("id"))
        lg_name = (lg.get("name") or "").strip()
        cty = (lg.get("country") or "").strip() or "World"
        home = (tm.get("home") or {}).get("name") or ""
        away = (tm.get("away") or {}).get("name") or ""
        when = nice_time(fix.get("date", ""))

        try:
            best = parse_best_market_odds(odds_by_fixture(fid))
        except Exception as e:
            _log(f"⚠️  odds fetch fail fid={fid} {cty}/{lg_name}: {e}")
            continue

        # heuristika izbora najboljeg tržišta
        pick = None  # (market, outcome, odd)
        if "BTTS" in best and "Yes" in best["BTTS"] and best["BTTS"]["Yes"] <= 2.1:
            pick = ("Both Teams To Score", "Yes", best["BTTS"]["Yes"])
        elif "OU" in best and "Over 1.5" in best["OU"]:
            pick = ("Over/Under", "Over 1.5", best["OU"]["Over 1.5"])
        elif "DC" in best:
            # preferiraj 1X/X2
            cand = []
            for v in ("1X", "X2", "12"):
                if v in best["DC"]:
                    cand.append((v, best["DC"][v]))
            cand.sort(key=lambda x: -x[1])
            if cand:
                pick = ("Double Chance", cand[0][0], cand[0][1])
        elif "MW" in best:
            # uzmi veći favorit do 1.50
            mw = best["MW"]
            for lab in ("Home", "Away"):
                if lab in mw and mw[lab] <= 1.50:
                    pick = ("Match Winner", lab, mw[lab])
                    break

        if not pick:
            continue

        market, outcome, odd = pick
        leg = {
            "fid": fid,
            "country": cty,
            "league": f"{cty} — {lg_name}",
            "league_name": lg_name,
            "home_name": home,
            "away_name": away,
            "teams": f"{home} vs {away}",
            "time": when,
            "market": market,
            "pick_name": outcome,
            "odd": float(odd),
            "odds": float(odd),  # alias za app
        }
        legs.append(leg)
        _log(f"🧩 leg fid={fid} {cty}/{lg_name} | {home} vs {away} | {market}→{outcome} @ {odd:.2f}")

    _log(f"📦 legs collected={len(legs)}")
    return legs

# ---------- ticket building ----------

def total_odds(legs: List[Dict[str, Any]]) -> float:
    x = 1.0
    for l in legs:
        x *= float(l["odd"])
    return x

def build_tickets(all_legs: List[Dict[str, Any]],
                  targets: List[float],
                  legs_min: int = LEGS_MIN,
                  legs_max: int = LEGS_MAX) -> List[List[Dict[str, Any]]]:
    # sortiraj rastuće po kvoti da lakše gađamo target
    pool = sorted(all_legs, key=lambda L: float(L["odd"]))
    used: set[int] = set()
    tickets: List[List[Dict[str, Any]]] = []

    for t in targets:
        ticket: List[Dict[str, Any]] = []
        for L in pool:
            if L["fid"] in used:
                continue
            cand = ticket + [L]
            if len(cand) > legs_max:
                continue
            # opusti malo gornju granicu da ne preleti previše
            if total_odds(cand) <= t * 1.10 or len(cand) < legs_min:
                ticket = cand
                if len(ticket) >= legs_min and total_odds(ticket) >= t:
                    break
        if len(ticket) >= legs_min:
            tickets.append(ticket)
            used.update(l["fid"] for l in ticket)
            _log(f"🎟️ ticket#{len(tickets)} legs={len(ticket)} total={total_odds(ticket):.2f} target={t}")
        else:
            _log(f"❕ unable to reach target={t} with constraints; skipping")

    return tickets

# ---------- output ----------

def ticket_payload(name: str, date_str: str, legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "name": name,
        "date": date_str,
        "total_odds": round(total_odds(legs), 2),
        "legs_count": len(legs),
        "legs": [
            {
                "fixture_id": int(L["fid"]),
                "league": L["league"],
                "league_name": L["league_name"],
                "country": L["country"],
                "home_name": L["home_name"],
                "away_name": L["away_name"],
                "teams": L["teams"],
                "time": L["time"],
                "market": L["market"],
                "pick": L["pick_name"],
                "odd": round(float(L["odd"]), 3),
                "odds": round(float(L["odd"]), 3),  # alias za app
            } for L in legs
        ]
    }

def write_public(tickets: List[List[Dict[str, Any]]], date_str: str) -> None:
    os.makedirs("public", exist_ok=True)
    names = ["2plus", "3plus", "4plus"]
    for nm, legs in zip(names, tickets):
        payload = ticket_payload(nm, date_str, legs)
        path = os.path.join("public", f"{nm}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        _log(f"📝 wrote {path} total={payload['total_odds']:.2f} legs={payload['legs_count']}")

    # agregat
    agg = {
        "date": date_str,
        "tickets": [
            {"name": nm, "legs": len(legs), "total_odds": round(total_odds(legs), 2)}
            for nm, legs in zip(names, tickets)
        ],
    }
    with open("public/daily_log.json", "w", encoding="utf-8") as f:
        json.dump(agg, f, ensure_ascii=False, indent=2)
    _log("📊 wrote public/daily_log.json")

# ---------- main ----------

def run() -> Dict[str, Any]:
    _log(f"▶ date={DATE} targets={TARGETS} legs_min={LEGS_MIN} legs_max={LEGS_MAX}")
    try:
        legs = collect_legs(DATE)
        tickets = build_tickets(legs, TARGETS, LEGS_MIN, LEGS_MAX)
        write_public(tickets, DATE)
        return {"date": DATE, "tickets_count": len(tickets)}
    except Exception as e:
        _fail(str(e))
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
