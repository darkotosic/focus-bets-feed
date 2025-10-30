"""
focus_bets.py
Jutarnji run za GitHub Pages / Expo app

Radi sledeće:
1. Povlači fixturе za date=YYYY-MM-DD iz API-FOOTBALL (samo allow list liga).
2. Za svaki fixture povlači odds (Match Winner, Over/Under, BTTS).
3. Izgradi kandidat legs.
4. Napravi 3 tiketa za targete 2.0, 3.0, 4.0 sa min 3 i max 7 mečeva.
5. Snimi u ./public:
   - 2plus.json
   - 3plus.json
   - 4plus.json
   - daily_log.json

Frontend očekuje format:
{
  "date": "2025-10-30",
  "ticket": {
    "target": 2.0,
    "total_odds": 2.05,
    "legs": [
      {
        "fid": 1382357,
        "league": "Switzerland — Super League",
        "teams": "TeamA vs TeamB",
        "time": "2025-10-30 18:00",
        "market": "Over/Under",
        "pick": "Over 1.5",
        "odds": 1.22
      }
    ]
  }
}

Napomena:
- Obavezno u GitHub Secrets: API_FOOTBALL_KEY
- Ako nema dovoljno mečeva, praviće kraće tikete ali će ih ipak snimiti.
"""

from __future__ import annotations
import os
import json
import math
from datetime import datetime, timezone, date as date_cls
from typing import Any, Dict, List, Tuple
import requests

API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
BASE = "https://v3.football.api-sports.io"
PUBLIC_DIR = "public"

# 30 najboljih evropskih i relevantnih takmičenja za dnevni feed
ALLOW_LEAGUES = {
    # liga_id: naziv
    39: "England — Premier League",
    140: "Spain — La Liga",
    135: "Italy — Serie A",
    78: "Germany — Bundesliga",
    61: "France — Ligue 1",
    88: "Netherlands — Eredivisie",
    94: "Portugal — Primeira Liga",
    203: "Turkey — Super Lig",
    179: "Belgium — Jupiler Pro League",
    180: "Switzerland — Super League",
    307: "Serbia — Super Liga",
    143: "Greece — Super League",
    207: "Austria — Bundesliga",
    144: "Cyprus — 1. Division",
    156: "Denmark — Superliga",
    106: "Russia — Premier League",
    235: "Scotland — Premiership",
    10: "UEFA — Champions League",
    11: "UEFA — Europa League",
    848: "UEFA — Europa Conference League",
    142: "Croatia — HNL",
    78: "Germany — Bundesliga",
    141: "Romania — Liga 1",
    343: "Czech Republic — First League",
    119: "Ukraine — Premier League",
    40: "England — Championship",
    569: "England — League One",
    571: "England — League Two",
    262: "Sweden — Allsvenskan",
    235: "Scotland — Premiership",
    607: "Norway — Eliteserien",
}

ODDS_MARKETS_WANTED = [
    "Match Winner",
    "Over/Under",
    "BTTS"
]


def ensure_public_dir() -> None:
    os.makedirs(PUBLIC_DIR, exist_ok=True)


def public_path(name: str) -> str:
    return os.path.join(PUBLIC_DIR, name)


def http_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("API_FOOTBALL_KEY is missing")
    url = f"{BASE}/{path}"
    r = requests.get(url, headers={"x-apisports-key": API_KEY}, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_fixtures_for_date(date_str: str) -> List[Dict[str, Any]]:
    # v3/fixtures?date=2025-10-30
    data = http_get("fixtures", {"date": date_str})
    res: List[Dict[str, Any]] = []
    for fx in data.get("response", []):
        league_id = fx.get("league", {}).get("id")
        if league_id in ALLOW_LEAGUES:
            res.append(fx)
    return res


def fetch_odds_for_fixture(fixture_id: int) -> Dict[str, Any]:
    data = http_get("odds", {"fixture": fixture_id})
    # response je lista bukija, id 1 je najčešći
    out: Dict[str, Any] = {}
    for item in data.get("response", []):
        for b in item.get("bookmakers", []):
            for m in b.get("bets", []):
                name = m.get("name")
                if name in ODDS_MARKETS_WANTED:
                    # uzmi prvi market tog imena
                    if name not in out:
                        out[name] = m
    return out


def best_market_odds(fixture: Dict[str, Any], odds: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Vrati listu kandidata za taj fixture, posle će se birati najbolji."""
    out: List[Dict[str, Any]] = []
    league_name = f"{fixture['league']['country']} — {fixture['league']['name']}"
    teams = f"{fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']}"
    time_utc = fixture["fixture"]["date"]
    fid = fixture["fixture"]["id"]
    # BTTS
    m = odds.get("BTTS")
    if m:
        for v in m.get("values", []):
            if v.get("value") in ("Yes", "No"):
                out.append({
                    "fid": fid,
                    "league": league_name,
                    "teams": teams,
                    "time": time_utc,
                    "market": "BTTS",
                    "pick": v["value"],
                    "odds": float(v["odd"])
                })
    # Over/Under -> uzmi O1.5 i O2.5 ako postoje
    m = odds.get("Over/Under")
    if m:
        for v in m.get("values", []):
            val = v.get("value", "")
            # API često vraća "Over 1.5", "Over 2.5", "Under 3.5"
            if val.startswith("Over") or val.startswith("Under"):
                out.append({
                    "fid": fid,
                    "league": league_name,
                    "teams": teams,
                    "time": time_utc,
                    "market": "Over/Under",
                    "pick": val,
                    "odds": float(v["odd"])
                })
    # Match Winner -> Home / Away
    m = odds.get("Match Winner")
    if m:
        for v in m.get("values", []):
            if v.get("value") in ("Home", "Away", "Draw"):
                out.append({
                    "fid": fid,
                    "league": league_name,
                    "teams": teams,
                    "time": time_utc,
                    "market": "Match Winner",
                    "pick": v["value"],
                    "odds": float(v["odd"])
                })
    return out


def collect_legs(date_str: str) -> List[Dict[str, Any]]:
    fixtures = fetch_fixtures_for_date(date_str)
    print(f"✅ fixtures ALLOW_LIST={len(fixtures)}")
    legs: List[Dict[str, Any]] = []
    for fx in fixtures:
        fid = fx["fixture"]["id"]
        odds = fetch_odds_for_fixture(fid)
        cands = best_market_odds(fx, odds)
        for c in cands:
            # dodaj fixture_id u svim varijantama da evaluator bude srećan
            c["fixture_id"] = c["fid"]
            legs.append(c)
        print(f"… fid={fid} league={fx['league']['country']}/{fx['league']['name']} odds_keys={list(odds.keys())}")
    return legs


def build_ticket(target_odds: float,
                 legs_pool: List[Dict[str, Any]],
                 min_legs: int = 3,
                 max_legs: int = 7) -> Dict[str, Any]:
    """
    Greedy: uzmi najbolje kvote (najviše) dok ne pređeš target.
    Ako ne može, vrati koliko ima.
    """
    # sortiraj po kvoti opadajuće
    legs_sorted = sorted(legs_pool, key=lambda x: x["odds"], reverse=True)
    chosen: List[Dict[str, Any]] = []
    prod = 1.0
    for leg in legs_sorted:
        if len(chosen) >= max_legs:
            break
        chosen.append(leg)
        prod *= leg["odds"]
        if prod >= target_odds and len(chosen) >= min_legs:
            break
    # ako i dalje manje od min_legs, popuni iz ostatka
    if len(chosen) < min_legs:
        for leg in legs_sorted:
            if leg in chosen:
                continue
            chosen.append(leg)
            prod *= leg["odds"]
            if len(chosen) >= min_legs:
                break
    return {
        "target": float(target_odds),
        "total_odds": round(prod, 2),
        "legs": chosen
    }


def build_three_tickets(date_str: str) -> Dict[str, Any]:
    legs_pool = collect_legs(date_str)
    print(f"📦 legs candidates={len(legs_pool)}")
    if not legs_pool:
        # fallback prazan
        return {
            "tickets": [
                {"target": 2.0, "total_odds": 1.0, "legs": []},
                {"target": 3.0, "total_odds": 1.0, "legs": []},
                {"target": 4.0, "total_odds": 1.0, "legs": []},
            ]
        }

    t1 = build_ticket(2.0, legs_pool, 3, 7)
    print(f"🎫 ticket#1 target=2.0 legs={len(t1['legs'])} total={t1['total_odds']}")
    t2 = build_ticket(3.0, legs_pool, 3, 7)
    print(f"🎫 ticket#2 target=3.0 legs={len(t2['legs'])} total={t2['total_odds']}")
    t3 = build_ticket(4.0, legs_pool, 3, 7)
    print(f"🎫 ticket#3 target=4.0 legs={len(t3['legs'])} total={t3['total_odds']}")

    return {
        "tickets": [t1, t2, t3]
    }


def save_public_files(date_str: str, tickets: List[Dict[str, Any]]) -> None:
    ensure_public_dir()

    mapping = [
        ("2plus.json", tickets[0]),
        ("3plus.json", tickets[1]),
        ("4plus.json", tickets[2]),
    ]

    for fname, ticket in mapping:
        with open(public_path(fname), "w", encoding="utf-8") as f:
            json.dump({
                "date": date_str,
                "ticket": ticket
            }, f, ensure_ascii=False, indent=2)

    with open(public_path("daily_log.json"), "w", encoding="utf-8") as f:
        json.dump({
            "date": date_str,
            "tickets_count": len(tickets),
            "files": [m[0] for m in mapping],
            "generated_at_utc": datetime.now(timezone.utc).isoformat()
        }, f, ensure_ascii=False, indent=2)


def run(targets: List[float] | None = None) -> Dict[str, Any]:
    # date = danas UTC
    d: date_cls = datetime.now(timezone.utc).date()
    date_str = d.isoformat()
    if targets is None:
        targets = [2.0, 3.0, 4.0]
    print(f"▶ date={date_str} targets={targets} legs_min=3 legs_max=7")

    built = build_three_tickets(date_str)
    tickets = built["tickets"]
    save_public_files(date_str, tickets)

    return {
        "date": date_str,
        "tickets_count": len(tickets)
    }


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, ensure_ascii=False, indent=2))
