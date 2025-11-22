#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, json, time, random, re
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import httpx

# ========= ENV =========
API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
if not API_KEY:
    raise SystemExit("Missing API_FOOTBALL_KEY (env)")

BASE_URL = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io").rstrip("/")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Belgrade")
TZ = ZoneInfo(TIMEZONE)

# All tickets target 2.0 as requested
TARGETS = [2.0, 2.0, 2.0]
LEGS_MIN = int(os.getenv("LEGS_MIN", "3"))
LEGS_MAX = int(os.getenv("LEGS_MAX", "7"))
MAX_PER_COUNTRY = int(os.getenv("MAX_PER_COUNTRY", "2"))
MAX_HEAVY_FAVORITES = int(os.getenv("MAX_HEAVY_FAVORITES", "1"))
RELAX_STEPS = int(os.getenv("RELAX_STEPS", "5"))
RELAX_ADD = float(os.getenv("RELAX_ADD", "0.03"))
DEBUG = os.getenv("DEBUG", "1") == "1"

OUT_DIR = Path("public")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def _log(msg: str):
    if DEBUG:
        print(msg, file=sys.stderr, flush=True)

HEADERS = {"x-apisports-key": API_KEY}
SKIP_STATUS = {"FT","AET","PEN","ABD","AWD","CANC","POSTP","PST","SUSP","INT","WO","LIVE"}

# ===== baseline odds caps (kept conservative; RELAX_ADD will loosen) =====
BASE_TH: Dict[Tuple[str,str], float] = {
    ("Double Chance","1X"): 1.20,
    ("Double Chance","X2"): 1.25,
    ("Double Chance","12"): 1.15,
    ("BTTS","Yes"): 1.40,
    ("BTTS","No"): 1.30,
    ("Over/Under","Over 1.5"): 1.15,
    ("Over/Under","Under 3.5"): 1.20,
    ("Over/Under","Over 2.5"): 1.28,
    ("Match Winner","Home"): 1.30,
    ("Match Winner","Away"): 1.30,
    ("1st Half Goals","Over 0.5"): 1.25,
    ("Home Team Goals","Over 0.5"): 1.25,
    ("Away Team Goals","Over 0.5"): 1.25,
}

# ===== allow list (unchanged) =====
ALLOW_LIST: set[int] = {
    2,3,913,5,536,808,960,10,667,29,30,31,32,37,33,34,848,311,310,342,218,144,315,71,
    169,210,346,233,39,40,41,42,703,244,245,61,62,78,79,197,271,164,323,135,136,389,
    88,89,408,103,104,106,94,283,235,286,287,322,140,141,113,207,208,202,203,909,268,269,270,340
}

# ===== priority leagues: countries + UEFA comps =====
PRIORITY_COUNTRIES = {
    "England","France","Spain","Germany","Italy","Netherlands","Serbia","Turkey"
}
PRIORITY_COMP_PATTERNS = [
    r"UEFA\s+Champions\s+League",
    r"UEFA\s+Europa\s+League",
    r"UEFA\s+Europa\s+Conference",
    r"UEFA\s+Nations\s+League"
]
PRIORITY_COMP_RE = re.compile("|".join(PRIORITY_COMP_PATTERNS), re.I)

# ===== HTTP =====
def _client() -> httpx.Client:
    return httpx.Client(timeout=30)

def _get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BASE_URL}{'' if path.startswith('/') else '/'}{path}"
    backoff = 1.5
    for _ in range(6):
        try:
            with _client() as c:
                r = c.get(url, headers=HEADERS, params=params)
            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                sleep = float(ra) if ra else backoff
                _log(f"⏳ API 429, sleep {sleep:.1f}s")
                time.sleep(sleep + random.uniform(0, 0.3 * sleep))
                backoff *= 1.8
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ProtocolError) as e:
            _log(f"HTTP transient {e.__class__.__name__}")
            time.sleep(backoff)
            backoff *= 1.8
    raise RuntimeError("HTTP retries exhausted")

def _fmt_dt_local(iso: str) -> str:
    try:
        return (
            datetime.fromisoformat(iso.replace("Z", "+00:00"))
            .astimezone(TZ)
            .strftime("%Y-%m-%d %H:%M")
        )
    except Exception:
        return iso

def _try_float(x: Any) -> Optional[float]:
    try:
        v = float(x)
        return v if v > 0 else None
    except Exception:
        return None

# ===== odds parser =====
FORBIDDEN_SUBSTRS = [
    "asian","alternative","corners","cards","booking","penalties","penalty","offside",
    "throw in","interval","race to","period","quarter","draw no bet","dnb","to qualify",
    "method of victory","overtime","extra time","win to nil","clean sheet","anytime",
    "player","scorer"
]

DOC_MARKETS = {
    "match_winner": {"Match Winner","1X2","Full Time Result","Result"},
    "double_chance": {"Double Chance","Double chance"},
    "btts": {"Both Teams To Score","Both teams to score","BTTS","Both Teams Score"},
    "ou": {"Goals Over/Under","Over/Under","Total Goals","Total","Goals Over Under","Total Goals Over/Under"},
    "ou_1st": {"1st Half - Over/Under","1st Half Goals Over/Under","First Half - Over/Under","Over/Under - 1st Half","First Half Goals","Goals Over/Under - 1st Half"},
    "ttg_home": {"Home Team Total Goals","Home Team Goals","Home Team - Total Goals","Home Total Goals"},
    "ttg_away": {"Away Team Total Goals","Away Team Goals","Away Team - Total Goals","Away Team Goals"},
    "ttg_generic": {"Team Total Goals","Total Team Goals","Team Goals"}
}

def _is_market_named(name: str, targets: set[str]) -> bool:
    n = (name or "").strip().lower()
    return any(n == t.lower() for t in targets)

def _is_fulltime_main(name: str) -> bool:
    nl = (name or "").lower()
    return not any(b in nl for b in FORBIDDEN_SUBSTRS)

def _normalize_ou_value(v: str) -> str:
    s = (v or "").strip()
    s = s.replace("Over1.5", "Over 1.5").replace("Under3.5", "Under 3.5").replace("Over2.5", "Over 2.5")
    s = re.sub(r"\s+", " ", s.title())
    return s

def best_market_odds(odds_resp: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    best: Dict[str, Dict[str, float]] = {}

    def put(mkt: str, val: str, odd_raw: Any):
        odd = _try_float(odd_raw)
        if odd is None:
            return
        best.setdefault(mkt, {})
        if best[mkt].get(val, 0.0) < odd:
            best[mkt][val] = odd

    for item in odds_resp:
        for bm in item.get("bookmakers", []) or []:
            for bet in bm.get("bets", []) or []:
                raw = (bet.get("name") or "").strip()
                if not raw:
                    continue

                # 1st half
                if _is_market_named(raw, DOC_MARKETS["ou_1st"]):
                    for v in bet.get("values", []) or []:
                        if re.search(r"(?i)\bover\s*0\.5\b", v.get("value") or ""):
                            put("1st Half Goals", "Over 0.5", v.get("odd"))
                    continue

                if not _is_fulltime_main(raw):
                    continue

                if _is_market_named(raw, DOC_MARKETS["match_winner"]):
                    for v in bet.get("values", []) or []:
                        val = (v.get("value") or "").strip()
                        if val in ("Home","1"):
                            put("Match Winner", "Home", v.get("odd"))
                        elif val in ("Away","2"):
                            put("Match Winner", "Away", v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["double_chance"]):
                    for v in bet.get("values", []) or []:
                        val = (v.get("value") or "").replace(" ", "").upper()
                        if val in {"1X","X2","12"}:
                            put("Double Chance", val, v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["btts"]):
                    for v in bet.get("values", []) or []:
                        val = (v.get("value") or "").strip().title()
                        if val in {"Yes","No"}:
                            put("BTTS", val, v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ou"]):
                    for v in bet.get("values", []) or []:
                        norm = _normalize_ou_value(v.get("value") or "")
                        if norm in {"Over 1.5","Under 3.5","Over 2.5"}:
                            put("Over/Under", norm, v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ttg_home"]):
                    for v in bet.get("values", []) or []:
                        if re.search(r"(?i)\bover\s*0\.5\b", v.get("value") or ""):
                            put("Home Team Goals", "Over 0.5", v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ttg_away"]):
                    for v in bet.get("values", []) or []:
                        if re.search(r"(?i)\bover\s*0\.5\b", v.get("value") or ""):
                            put("Away Team Goals", "Over 0.5", v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ttg_generic"]):
                    for v in bet.get("values", []) or []:
                        vv = (v.get("value") or "").strip().lower()
                        if "over 0.5" in vv and "home" in vv:
                            put("Home Team Goals", "Over 0.5", v.get("odd"))
                        elif "over 0.5" in vv and "away" in vv:
                            put("Away Team Goals", "Over 0.5", v.get("odd"))
                    continue

    return best

# ===== fixtures =====
def fetch_fixtures(date_str: str) -> List[Dict[str, Any]]:
    items = _get("/fixtures", {"date": date_str}).get("response") or []
    out = []
    for f in items:
        lg = f.get("league", {}) or {}
        fx = f.get("fixture", {}) or {}
        st = (fx.get("status") or {}).get("short", "")
        if lg.get("id") in ALLOW_LIST and st not in SKIP_STATUS:
            out.append(f)
    _log(f"✅ fixtures ALLOW_LIST={len(out)}")
    return out

def fetch_all_fixtures_no_filter(date_str: str) -> List[Dict[str, Any]]:
    items = _get("/fixtures", {"date": date_str}).get("response") or []
    out = []
    for f in items:
        fx = f.get("fixture", {}) or {}
        st = (fx.get("status") or {}).get("short", "")
        if st not in SKIP_STATUS:
            out.append(f)
    _log(f"⚠️ fallback fixtures ALL={len(out)}")
    return out

def odds_by_fixture(fid: int) -> List[Dict[str, Any]]:
    return _get("/odds", {"fixture": fid}).get("response") or []

# ===== priority scoring =====
def _priority_score(league_country: str, league_name: str) -> int:
    if league_country in PRIORITY_COUNTRIES:
        return 2
    if PRIORITY_COMP_RE.search(league_name or ""):
        return 2
    return 1

# ===== leg assembly =====
def assemble_legs_from_fixtures(
    fixtures: List[Dict[str, Any]],
    caps: Dict[Tuple[str,str], float],
    allowed_pairs: Optional[set[Tuple[str,str]]] = None
) -> List[Dict[str, Any]]:
    legs = []
    for f in fixtures:
        fx = f.get("fixture", {}) or {}
        lg = f.get("league", {}) or {}
        tm = f.get("teams", {}) or {}
        fid = int(fx.get("id"))
        when_local = _fmt_dt_local(fx.get("date", ""))
        home = (tm.get("home") or {})
        away = (tm.get("away") or {})

        resp = odds_by_fixture(fid)
        best = best_market_odds(resp)
        _log(f"… fid={fid} league={lg.get('country','')}/{lg.get('name','')} odds_keys={[k for k in best.keys()]}")

        pick_mkt = None
        pick_name = None
        pick_odd = 0.0

        for (mkt, variants) in best.items():
            for name, odd in variants.items():
                if allowed_pairs is not None and (mkt, name) not in allowed_pairs:
                    continue
                cap = caps.get((mkt, name))
                if cap is None:
                    continue
                if odd < cap and odd > pick_odd:
                    pick_mkt = mkt
                    pick_name = name
                    pick_odd = odd

        if pick_mkt:
            display_time = f"{when_local} • {fid}"
            legs.append({
                "fid": fid,
                "country": (lg.get("country") or "").strip() or "World",
                "league_name": lg.get("name") or "",
                "league": f"{lg.get('country','')} — {lg.get('name','')}",
                "home_name": home.get("name") or "",
                "away_name": away.get("name") or "",
                "teams": f"{home.get('name','')} vs {away.get('name','')}",
                "time": display_time,
                "market": pick_mkt,
                "pick_name": pick_name,
                "odd": float(pick_odd),
                "prio": _priority_score(lg.get("country") or "", lg.get("name") or "")
            })

    # priority first, then by descending odd
    legs.sort(key=lambda L: (L["prio"], L["odd"]), reverse=True)
    _log(f"📦 legs candidates={len(legs)} (caps size={len(caps)})")
    return legs

def assemble_legs(date_str: str, caps: Dict[Tuple[str,str], float], allowed_pairs: Optional[set[Tuple[str,str]]] = None) -> List[Dict[str, Any]]:
    return assemble_legs_from_fixtures(fetch_fixtures(date_str), caps, allowed_pairs)

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

def _build_for_target(pool: List[Dict[str, Any]], target: float, used_fids: set) -> Optional[List[Dict[str, Any]]]:
    cand = [x for x in pool if x["fid"] not in used_fids]
    cand.sort(key=lambda L: (L["prio"], L["odd"]), reverse=True)
    best = None

    # greedy
    t = []
    total = 1.0
    for L in cand:
        if not _diversity_ok(t, L):
            continue
        t.append(L)
        total *= L["odd"]
        if len(t) >= LEGS_MIN and total >= target:
            best = list(t)
            break

    # dfs
    def dfs(idx, cur, prod):
        nonlocal best
        if best and len(cur) >= len(best):
            return
        if len(cur) > LEGS_MAX:
            return
        if len(cur) >= LEGS_MIN and prod >= target:
            best = list(cur)
            return
        for j in range(idx, min(idx + 24, len(cand))):
            L = cand[j]
            if any(x["fid"] == L["fid"] for x in cur):
                continue
            if not _diversity_ok(cur, L):
                continue
            dfs(j + 1, cur + [L], prod * L["odd"])
            if best:
                return

    if not best:
        dfs(0, [], 1.0)
    return best

def _ticket_json(legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "total_odds": round(_product([l["odd"] for l in legs]), 2),
        "legs": [{
            "fid": l["fid"],
            "league": l["league"],
            "teams": l["teams"],
            "time": l["time"],               # TicketScreen reads "time" or "kickoff_local"
            "market": l["market"],
            "pick": l["pick_name"],          # TicketScreen maps pick/pick_name
            "odds": round(float(l["odd"]), 2)
        } for l in legs]
    }

# ===== requested build rules =====
ALLOWED_T2: set[Tuple[str,str]] = {
    ("Double Chance","1X"),
    ("Double Chance","X2"),
    ("Over/Under","Over 1.5"),
    ("Over/Under","Over 2.5"),
    ("Over/Under","Under 3.5"),
}
ALLOWED_T3: set[Tuple[str,str]] = {
    ("BTTS","Yes"),
    ("BTTS","No"),
    ("Match Winner","Home"),
    ("Match Winner","Away"),
}

def _pool_for_ticket(date_str: str, caps: Dict[Tuple[str,str], float], allowed_pairs: Optional[set[Tuple[str,str]]]) -> List[Dict[str, Any]]:
    legs = assemble_legs(date_str, caps, allowed_pairs)
    # if pool too small, widen to ALL fixtures while keeping the same allowed pairs rule
    if len(legs) < 25:
        all_fixtures = fetch_all_fixtures_no_filter(date_str)
        legs = assemble_legs_from_fixtures(all_fixtures, caps, allowed_pairs)
    return legs

def build_three_tickets(date_str: str) -> List[List[Dict[str, Any]]]:
    tickets: List[List[Dict[str, Any]]] = []
    used: set[int] = set()

    # ticket configs: [(allowed_pairs or None), target]
    configs = [
        (None, TARGETS[0]),        # Ticket #1: mixed like before
        (ALLOWED_T2, TARGETS[1]),  # Ticket #2: 1X/X2/O1.5/O2.5/U3.5
        (ALLOWED_T3, TARGETS[2])   # Ticket #3: BTTS Yes/No + Home/Away
    ]

    # progressive relaxation for each ticket independently
    for idx, (allowed_pairs, target) in enumerate(configs, start=1):
        caps = dict(BASE_TH)
        built = None
        for step in range(RELAX_STEPS + 1):
            pool = _pool_for_ticket(date_str, caps, allowed_pairs)
            built = built = _build_for_target(pool, target, set())  # allow reuse if absolutely needed

            if built:
                break
            caps = {k: (v + RELAX_ADD) for k, v in caps.items()}
            _log(f"↘ relax T{idx} step={step+1} caps+= {RELAX_ADD}")
        if not built:
            # last-ditch: drop country diversity but keep used_fids and caps
            pool = _pool_for_ticket(date_str, caps, allowed_pairs)
            built = _build_for_target(pool, target, used=set())  # allow reuse if absolutely needed
        if built:
            tickets.append(built)
            used.update(x["fid"] for x in built)
            total = _product([x["odd"] for x in built])
            _log(f"🎫 ticket#{idx} legs={len(built)} total={total:.2f}")
        else:
            tickets.append([])  # keep file shape consistent

    return tickets[:3]

# ===== I/O =====
def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _save_snapshot(date_str: str, tickets_payload: List[Dict[str, Any]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "feed_snapshot.json", "w", encoding="utf-8") as f:
        json.dump({"date": date_str, "tickets": tickets_payload}, f, ensure_ascii=False, indent=2)
    lines = [f"date={date_str}"]
    for t in tickets_payload:
        lines.append(f"[{t['name']}] target={t.get('target')} total={t.get('total_odds'):.2f}")
        for lg in t["legs"]:
            lines.append(
                f"  - {lg['time']} | {lg['league']} | {lg['teams']} | {lg['market']} -> {lg['pick']} | odd={lg['odds']}"
            )
    with open(OUT_DIR / "feed_snapshot.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def write_pages(date_str: str, tickets: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
    names = ["2plus","3plus","4plus"]  # file names remain the same for app/pages.yml compatibility
    out_meta = []
    tickets_payload_for_snapshot: List[Dict[str, Any]] = []

    for i, legs in enumerate(tickets):
        name = names[i] if i < len(names) else f"t{i+1}"
        ticket_json = _ticket_json(legs) if legs else {"total_odds": 0, "legs": []}
        payload = {
            "date": date_str,
            "name": name,
            "ticket": ticket_json
        }
        _write_json(OUT_DIR / f"{name}.json", payload)
        out_meta.append({"name": name, "total_odds": ticket_json["total_odds"], "legs": len(ticket_json["legs"])})
        tickets_payload_for_snapshot.append({
            "name": name,
            "target": TARGETS[i] if i < len(TARGETS) else None,
            "total_odds": ticket_json["total_odds"],
            "legs": ticket_json["legs"],
        })

    _write_json(OUT_DIR / "daily_log.json", {
        "date": date_str,
        "tickets": out_meta
    })

    _save_snapshot(date_str, tickets_payload_for_snapshot)
    return {"count": len(out_meta), "files": [f"{m['name']}.json" for m in out_meta]}

def run(date_str: Optional[str] = None) -> Dict[str, Any]:
    if not date_str:
        date_str = datetime.now(TZ).strftime("%Y-%m-%d")
    _log(f"▶ date={date_str} targets={TARGETS} legs_min={LEGS_MIN} legs_max={LEGS_MAX}")
    tickets_legs = build_three_tickets(date_str)
    meta = write_pages(date_str, tickets_legs)
    return {"date": date_str, "tickets_count": meta["count"]}

if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
