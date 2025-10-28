#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, json, time, random, re
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
from pathlib import Path

# ========= ENV =========
API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
BASE_URL = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io").rstrip("/")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Belgrade")
TZ = ZoneInfo(TIMEZONE)

TARGETS = [float(x) for x in os.getenv("TICKET_TARGETS","2.0,3.0,4.0").split(",")]
LEGS_MIN = int(os.getenv("LEGS_MIN","3"))
LEGS_MAX = int(os.getenv("LEGS_MAX","7"))
MAX_PER_COUNTRY = int(os.getenv("MAX_PER_COUNTRY","2"))
MAX_HEAVY_FAVORITES = int(os.getenv("MAX_HEAVY_FAVORITES","1"))
RELAX_STEPS = int(os.getenv("RELAX_STEPS","2"))
RELAX_ADD   = float(os.getenv("RELAX_ADD","0.03"))
DEBUG = os.getenv("DEBUG","1") == "1"

OUT_DIR = Path("public")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def _log(msg:str):
    if DEBUG: print(msg, file=sys.stderr, flush=True)

HEADERS = {"x-apisports-key": API_KEY}
SKIP_STATUS = {"FT","AET","PEN","ABD","AWD","CANC","POSTP","PST","SUSP","INT","WO","LIVE"}

# ===== CAPS / pragovi =====
BASE_TH: Dict[Tuple[str,str], float] = {
    ("Double Chance","1X"): 1.20,
    ("Double Chance","X2"): 1.25,
    ("Double Chance","12"): 1.15,
    ("BTTS","Yes"): 1.40,
    ("BTTS","No"):  1.30,
    ("Over/Under","Over 1.5"):  1.15,
    ("Over/Under","Under 3.5"): 1.20,
    ("Over/Under","Over 2.5"):  1.28,
    ("Match Winner","Home"): 1.30,
    ("Match Winner","Away"): 1.30,
    ("1st Half Goals","Over 0.5"):  1.25,
    ("Home Team Goals","Over 0.5"): 1.25,
    ("Away Team Goals","Over 0.5"): 1.25,
}

# ===== Liga ALLOW LIST (evropske top lige i takmičenja + ključne 2. i kupovi) =====
ALLOW_LIST: set[int] = {
    2,3,913,5,536,808,960,10,667,29,30,31,32,37,33,34,848,311,310,342,218,144,315,71,
    169,210,346,233,39,40,41,42,703,244,245,61,62,78,79,197,271,164,323,135,136,389,
    88,89,408,103,104,106,94,283,235,286,287,322,140,141,113,207,208,202,203,909,268,269,270,340
}

# ===== HTTP =====
def _client() -> httpx.Client:
    return httpx.Client(timeout=30)

def _get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url=f"{BASE_URL}{'' if path.startswith('/') else '/'}{path}"
    backoff=1.5
    for _ in range(6):
        try:
            with _client() as c:
                r=c.get(url, headers=HEADERS, params=params)
            if r.status_code==429:
                ra=r.headers.get("Retry-After"); sleep=float(ra) if ra else backoff
                _log(f"⏳ API 429, sleep {sleep:.1f}s…")
                time.sleep(sleep+random.uniform(0,0.3*sleep)); backoff*=1.8; continue
            r.raise_for_status()
            return r.json()
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ProtocolError) as e:
            _log(f"⚠️ HTTP transient {e.__class__.__name__}"); time.sleep(backoff); backoff*=1.8
    raise RuntimeError("HTTP retries exhausted")

def _fmt_dt_local(iso: str) -> str:
    try: return datetime.fromisoformat(iso.replace("Z","+00:00")).astimezone(TZ).strftime("%Y-%m-%d %H:%M")
    except Exception: return iso

def _try_float(x: Any) -> Optional[float]:
    try:
        v=float(x)
        return v if v>0 else None
    except Exception:
        return None

# ===== Odds parser =====
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
    n=(name or "").strip().lower()
    return any(n==t.lower() for t in targets)

def _is_fulltime_main(name: str) -> bool:
    nl=(name or "").lower()
    return not any(b in nl for b in FORBIDDEN_SUBSTRS)

def _normalize_ou_value(v: str) -> str:
    s=(v or "").strip()
    s=s.replace("Over1.5","Over 1.5").replace("Under3.5","Under 3.5").replace("Over2.5","Over 2.5")
    s=re.sub(r"\s+"," ", s.title()); return s

def _norm_over05(val: str) -> bool: return re.search(r"(?i)\bover\s*0\.5\b", val or "") is not None
def _value_mentions_home(val: str) -> bool: return re.search(r"(?i)\bhome\b", val or "") is not None
def _value_mentions_away(val: str) -> bool: return re.search(r"(?i)\baway\b", val or "") is not None

def best_market_odds(odds_resp: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    best: Dict[str, Dict[str, float]] = {}
    def put(mkt: str, val: str, odd_raw: Any):
        odd=_try_float(odd_raw)
        if odd is None: return
        best.setdefault(mkt, {})
        if best[mkt].get(val, 0.0) < odd: best[mkt][val]=odd

    for item in odds_resp:
        for bm in item.get("bookmakers",[]) or []:
            for bet in bm.get("bets",[]) or []:
                raw=(bet.get("name") or "").strip()
                if not raw: continue

                if _is_market_named(raw, DOC_MARKETS["ou_1st"]):
                    for v in bet.get("values",[]) or []:
                        if _norm_over05(v.get("value") or ""):
                            put("1st Half Goals","Over 0.5", v.get("odd"))
                    continue

                if not _is_fulltime_main(raw):
                    continue

                if _is_market_named(raw, DOC_MARKETS["match_winner"]):
                    for v in bet.get("values",[]) or []:
                        val=(v.get("value") or "").strip()
                        if val in ("Home","1"): put("Match Winner","Home", v.get("odd"))
                        elif val in ("Away","2"): put("Match Winner","Away", v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["double_chance"]):
                    for v in bet.get("values",[]) or []:
                        val=(v.get("value") or "").replace(" ","").upper()
                        if val in {"1X","X2","12"}: put("Double Chance", val, v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["btts"]):
                    for v in bet.get("values",[]) or []:
                        val=(v.get("value") or "").strip().title()
                        if val in {"Yes","No"}: put("BTTS", val, v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ou"]):
                    for v in bet.get("values",[]) or []:
                        norm=_normalize_ou_value(v.get("value") or "")
                        if norm in {"Over 1.5","Under 3.5","Over 2.5"}:
                            put("Over/Under", norm, v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ttg_home"]):
                    for v in bet.get("values",[]) or []:
                        if _norm_over05(v.get("value") or ""): put("Home Team Goals","Over 0.5", v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ttg_away"]):
                    for v in bet.get("values",[]) or []:
                        if _norm_over05(v.get("value") or ""): put("Away Team Goals","Over 0.5", v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ttg_generic"]):
                    for v in bet.get("values",[]) or []:
                        vv=(v.get("value") or "").strip()
                        if _norm_over05(vv):
                            if _value_mentions_home(vv): put("Home Team Goals","Over 0.5", v.get("odd"))
                            elif _value_mentions_away(vv): put("Away Team Goals","Over 0.5", v.get("odd"))
                    continue
    return best

# ===== Data fetch =====
def fetch_fixtures(date_str: str) -> List[Dict[str, Any]]:
    items=_get("/fixtures", {"date": date_str}).get("response") or []
    out=[]
    for f in items:
        lg=f.get("league",{}) or {}; fx=f.get("fixture",{}) or {}
        st=(fx.get("status") or {}).get("short","")
        if lg.get("id") in ALLOW_LIST and st not in SKIP_STATUS:
            out.append(f)
    _log(f"✅ fixtures ALLOW_LIST={len(out)}")
    return out

def odds_by_fixture(fid: int) -> List[Dict[str,Any]]:
    return _get("/odds", {"fixture": fid}).get("response") or []

# ===== Legs =====
def assemble_legs(date_str: str, caps: Dict[Tuple[str,str], float]) -> List[Dict[str, Any]]:
    legs=[]
    for f in fetch_fixtures(date_str):
        fx=f.get("fixture",{}) or {}; lg=f.get("league",{}) or {}; tm=f.get("teams",{}) or {}
        fid=int(fx.get("id")); when=_fmt_dt_local(fx.get("date",""))
        home=(tm.get("home") or {}); away=(tm.get("away") or {})
        resp=odds_by_fixture(fid)
        best=best_market_odds(resp)
        _log(f"… fid={fid} league={lg.get('country','')}/{lg.get('name','')} odds_keys={[k for k in best.keys()]}")
        pick_mkt=None; pick_name=None; pick_odd=0.0
        for (mkt, variants) in best.items():
            for name, odd in variants.items():
                cap=caps.get((mkt,name))
                if cap is None: 
                    continue
                if odd < cap and odd > pick_odd:
                    pick_mkt=mkt; pick_name=name; pick_odd=odd
        if pick_mkt:
            legs.append({
                "fid": fid,
                "country": (lg.get('country') or '').strip() or 'World',
                "league_name": lg.get('name') or '',
                "league": f"{lg.get('country','')} — {lg.get('name','')}",
                "home_name": home.get('name') or '',
                "away_name": away.get('name') or '',
                "teams": f"{home.get('name','')} vs {away.get('name','')}",
                "time": when,
                "market": pick_mkt,
                "pick_name": pick_name,
                "odd": float(pick_odd)
            })
    legs.sort(key=lambda L: L["odd"], reverse=True)
    _log(f"📦 legs candidates={len(legs)} (caps size={len(caps)})")
    return legs

def _product(vals: List[float]) -> float:
    p=1.0
    for v in vals: p*=v
    return p

def _diversity_ok(ticket: List[Dict[str,Any]], cand: Dict[str,Any]) -> bool:
    countries = [x["country"] for x in ticket] + [cand["country"]]
    if countries.count(cand["country"]) > MAX_PER_COUNTRY:
        return False
    heavy = sum(1 for x in ticket if x["odd"] < 1.20) + (1 if cand["odd"] < 1.20 else 0)
    if heavy > MAX_HEAVY_FAVORITES: return False
    if any(x["fid"] == cand["fid"] for x in ticket): return False
    return True

def _build_for_target(pool: List[Dict[str,Any]], target: float, used_fids: set) -> Optional[List[Dict[str,Any]]]:
    cand=[x for x in pool if x["fid"] not in used_fids]
    cand.sort(key=lambda L: L["odd"], reverse=True)
    best=None
    # Greedy
    t=[]; total=1.0
    for L in cand:
        if not _diversity_ok(t,L): continue
        t.append(L); total*=L["odd"]
        if len(t)>=LEGS_MIN and total>=target: best=list(t); break
    # Small DFS
    def dfs(idx, cur, prod):
        nonlocal best
        if best and len(cur)>=len(best): return
        if len(cur)>LEGS_MAX: return
        if len(cur)>=LEGS_MIN and prod>=target:
            best=list(cur); return
        for j in range(idx, min(idx+20, len(cand))):
            L=cand[j]
            if any(x["fid"]==L["fid"] for x in cur): continue
            if not _diversity_ok(cur,L): continue
            dfs(j+1, cur+[L], prod*L["odd"])
            if best: return
    if not best: dfs(0, [], 1.0)
    return best

# ===== Tickets → JSON =====
def _ticket_json(legs: List[Dict[str,Any]]) -> Dict[str,Any]:
    return {
        "total_odds": round(_product([l["odd"] for l in legs]), 2),
        "legs": [{
            "fid": l["fid"],
            "league": l["league"],
            "teams": l["teams"],
            "time": l["time"],
            "market": l["market"],
            "pick": l["pick_name"],
            "odds": round(float(l["odd"]), 2)
        } for l in legs]
    }

def build_three_tickets(date_str: str) -> List[List[Dict[str,Any]]]:
    tickets=[]; used=set(); caps=dict(BASE_TH)
    for step in range(RELAX_STEPS+1):
        legs = assemble_legs(date_str, caps)
        for idx, target in enumerate(TARGETS, start=1):
            if len(tickets)>=idx: continue
            built=_build_for_target(legs, target, used)
            if built:
                tickets.append(built); used.update(x["fid"] for x in built)
                _log(f"🎫 ticket#{len(tickets)} target={target} legs={len(built)} total={_product([x['odd'] for x in built]):.2f}")
        if len(tickets)>=3: break
        caps={k:(v+RELAX_ADD) for k,v in caps.items()}
        _log(f"↘ relax step={step+1} caps+= {RELAX_ADD}")
    return tickets[:3]

# ===== IO =====
def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def write_pages(date_str: str, tickets: List[List[Dict[str,Any]]]) -> Dict[str,Any]:
    names = ["2plus","3plus","4plus"]
    out_meta=[]
    for i, legs in enumerate(tickets):
        name = names[i] if i < len(names) else f"t{i+1}"
        payload = {
            "date": date_str,
            "name": name,
            "ticket": _ticket_json(legs)
        }
        _write_json(OUT_DIR/f"{name}.json", payload)
        out_meta.append({"name": name, "total_odds": payload["ticket"]["total_odds"], "legs": len(legs)})
    # daily log
    _write_json(OUT_DIR/"daily_log.json", {
        "date": date_str,
        "tickets": out_meta
    })
    return {"count": len(tickets), "files": [f"{n}.json" for n in names[:len(tickets)]]}

# ===== MAIN =====
def run(date_str: Optional[str]=None) -> Dict[str,Any]:
    if not API_KEY:
        raise SystemExit("Missing API_FOOTBALL_KEY")
    if not date_str:
        date_str = datetime.now(TZ).strftime("%Y-%m-%d")
    _log(f"▶ date={date_str} targets={TARGETS} legs_min={LEGS_MIN} legs_max={LEGS_MAX}")
    tickets_legs = build_three_tickets(date_str)
    meta = write_pages(date_str, tickets_legs)
    return {"date": date_str, "tickets_count": meta["count"]}

if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
