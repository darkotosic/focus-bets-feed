#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import json
import time
import random
import re
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

# ========= ENV =========
API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Belgrade")
TZ = ZoneInfo(TIMEZONE)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_ORG = os.getenv("OPENAI_ORG") or None

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNELS = os.getenv("TELEGRAM_CHANNELS", "")

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID_FOCUS_BETS")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID_FOCUS_BETS")
AIRTABLE_FIELD_ID = os.getenv("AIRTABLE_FIELD_ID_FOCUS_BETS")

TARGETS = [float(x) for x in os.getenv("TICKET_TARGETS", "2.0,3.0,4.0").split(",")]
LEGS_MIN = int(os.getenv("LEGS_MIN", "3"))
LEGS_MAX = int(os.getenv("LEGS_MAX", "7"))
MAX_PER_COUNTRY = int(os.getenv("MAX_PER_COUNTRY", "2"))
MAX_HEAVY_FAVORITES = int(os.getenv("MAX_HEAVY_FAVORITES", "1"))
RELAX_STEPS = int(os.getenv("RELAX_STEPS", "2"))
RELAX_ADD = float(os.getenv("RELAX_ADD", "0.03"))
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
QUIET = os.getenv("QUIET", "0") == "1"
DEBUG = os.getenv("DEBUG", "1") == "1"
FORCE_CLEAR_AIRTABLE = os.getenv("FORCE_CLEAR_AIRTABLE", "0") == "1"


def _log(msg: str) -> None:
    if not QUIET:
        print(msg, file=sys.stderr, flush=True)


# ========= CAPS =========
BASE_TH: Dict[Tuple[str, str], float] = {
    ("Double Chance", "1X"): 1.20,
    ("Double Chance", "X2"): 1.25,
    ("Double Chance", "12"): 1.15,
    ("BTTS", "Yes"): 1.40,
    ("BTTS", "No"): 1.30,
    ("Over/Under", "Over 1.5"): 1.15,
    ("Over/Under", "Under 3.5"): 1.20,
    ("Over/Under", "Over 2.5"): 1.28,
    ("Match Winner", "Home"): 1.30,
    ("Match Winner", "Away"): 1.30,
    ("1st Half Goals", "Over 0.5"): 1.25,
    ("Home Team Goals", "Over 0.5"): 1.25,
    ("Away Team Goals", "Over 0.5"): 1.25,
}

ALLOW_LIST: set[int] = {
    2,
    3,
    913,
    5,
    536,
    808,
    960,
    10,
    667,
    29,
    30,
    31,
    32,
    37,
    33,
    34,
    848,
    311,
    310,
    342,
    218,
    144,
    315,
    71,
    169,
    210,
    346,
    233,
    39,
    40,
    41,
    42,
    703,
    244,
    245,
    61,
    62,
    78,
    79,
    197,
    271,
    164,
    323,
    135,
    136,
    389,
    88,
    89,
    408,
    103,
    104,
    106,
    94,
    283,
    235,
    286,
    287,
    322,
    140,
    141,
    113,
    207,
    208,
    202,
    203,
    909,
    268,
    269,
    270,
    340,
}
SKIP_STATUS = {
    "FT",
    "AET",
    "PEN",
    "ABD",
    "AWD",
    "CANC",
    "POSTP",
    "PST",
    "SUSP",
    "INT",
    "WO",
    "LIVE",
}
HEADERS = {"x-apisports-key": API_KEY}


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
                _log(f"⏳ API 429, sleep {sleep:.1f}s…")
                time.sleep(sleep + random.uniform(0, 0.3 * sleep))
                backoff *= 1.8
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ProtocolError) as e:
            _log(f"⚠️ HTTP transient {e.__class__.__name__}")
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


FORBIDDEN_SUBSTRS = [
    "asian",
    "alternative",
    "corners",
    "cards",
    "booking",
    "penalties",
    "penalty",
    "offside",
    "throw in",
    "interval",
    "race to",
    "period",
    "quarter",
    "draw no bet",
    "dnb",
    "to qualify",
    "method of victory",
    "overtime",
    "extra time",
    "win to nil",
    "clean sheet",
    "anytime",
    "player",
    "scorer",
]


DOC_MARKETS = {
    "match_winner": {"Match Winner", "1X2", "Full Time Result", "Result"},
    "double_chance": {"Double Chance", "Double chance"},
    "btts": {
        "Both Teams To Score",
        "Both teams to score",
        "BTTS",
        "Both Teams Score",
    },
    "ou": {
        "Goals Over/Under",
        "Over/Under",
        "Total Goals",
        "Total",
        "Goals Over Under",
        "Total Goals Over/Under",
    },
    "ou_1st": {
        "1st Half - Over/Under",
        "1st Half Goals Over/Under",
        "First Half - Over/Under",
        "Over/Under - 1st Half",
        "First Half Goals",
        "Goals Over/Under - 1st Half",
    },
    "ttg_home": {
        "Home Team Total Goals",
        "Home Team Goals",
        "Home Team - Total Goals",
        "Home Total Goals",
    },
    "ttg_away": {
        "Away Team Total Goals",
        "Away Team Goals",
        "Away Team - Total Goals",
        "Away Team Goals",
    },
    "ttg_generic": {
        "Team Total Goals",
        "Total Team Goals",
        "Team Goals",
    },
}


def _is_market_named(name: str, targets: set[str]) -> bool:
    n = (name or "").strip().lower()
    return any(n == t.lower() for t in targets)


def _is_fulltime_main(name: str) -> bool:
    nl = (name or "").lower()
    return not any(b in nl for b in FORBIDDEN_SUBSTRS)


def _normalize_ou_value(v: str) -> str:
    s = (v or "").strip()
    s = (
        s.replace("Over1.5", "Over 1.5")
        .replace("Under3.5", "Under 3.5")
        .replace("Over2.5", "Over 2.5")
    )
    s = re.sub(r"\s+", " ", s.title())
    return s


def _norm_over05(val: str) -> bool:
    return re.search(r"(?i)\bover\s*0\.5\b", val or "") is not None


def _value_mentions_home(val: str) -> bool:
    return re.search(r"(?i)\bhome\b", val or "") is not None


def _value_mentions_away(val: str) -> bool:
    return re.search(r"(?i)\baway\b", val or "") is not None


def best_market_odds(odds_resp: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    best: Dict[str, Dict[str, float]] = {}

    def put(mkt: str, val: str, odd_raw: Any) -> None:
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

                if _is_market_named(raw, DOC_MARKETS["ou_1st"]):
                    for v in bet.get("values", []) or []:
                        if _norm_over05(v.get("value") or ""):
                            put("1st Half Goals", "Over 0.5", v.get("odd"))
                    continue

                if not _is_fulltime_main(raw):
                    continue

                if _is_market_named(raw, DOC_MARKETS["match_winner"]):
                    for v in bet.get("values", []) or []:
                        val = (v.get("value") or "").strip()
                        if val in ("Home", "1"):
                            put("Match Winner", "Home", v.get("odd"))
                        elif val in ("Away", "2"):
                            put("Match Winner", "Away", v.get("odd"))
                        elif val in ("Draw", "X"):
                            pass
                    continue

                if _is_market_named(raw, DOC_MARKETS["double_chance"]):
                    for v in bet.get("values", []) or []:
                        val = (v.get("value") or "").replace(" ", "").upper()
                        if val in {"1X", "X2", "12"}:
                            put("Double Chance", val, v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["btts"]):
                    for v in bet.get("values", []) or []:
                        val = (v.get("value") or "").strip().title()
                        if val in {"Yes", "No"}:
                            put("BTTS", val, v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ou"]):
                    for v in bet.get("values", []) or []:
                        norm = _normalize_ou_value(v.get("value") or "")
                        if norm in {"Over 1.5", "Under 3.5", "Over 2.5"}:
                            put("Over/Under", norm, v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ttg_home"]):
                    for v in bet.get("values", []) or []:
                        if _norm_over05(v.get("value") or ""):
                            put("Home Team Goals", "Over 0.5", v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ttg_away"]):
                    for v in bet.get("values", []) or []:
                        if _norm_over05(v.get("value") or ""):
                            put("Away Team Goals", "Over 0.5", v.get("odd"))
                    continue

                if _is_market_named(raw, DOC_MARKETS["ttg_generic"]):
                    for v in bet.get("values", []) or []:
                        vv = (v.get("value") or "").strip()
                        if _norm_over05(vv):
                            if _value_mentions_home(vv):
                                put("Home Team Goals", "Over 0.5", v.get("odd"))
                            elif _value_mentions_away(vv):
                                put("Away Team Goals", "Over 0.5", v.get("odd"))
                    continue
    return best


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


def fetch_odds_best(fid: int) -> Dict[str, Dict[str, float]]:
    resp = _get("/odds", {"fixture": fid}).get("response") or []
    return best_market_odds(resp)


def assemble_legs(date_str: str, caps: Dict[Tuple[str, str], float]) -> List[Dict[str, Any]]:
    legs = []
    for f in fetch_fixtures(date_str):
        fx = f.get("fixture", {}) or {}
        lg = f.get("league", {}) or {}
        tm = f.get("teams", {}) or {}
        fid = fx.get("id")
        when = _fmt_dt_local(fx.get("date", ""))
        home = tm.get("home") or {}
        away = tm.get("away") or {}
        odds = fetch_odds_best(fid)

        best_market = None
        best_name = None
        best_odd = 0.0
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
            legs.append(
                {
                    "fid": int(fid),
                    "country": (lg.get("country") or "").strip() or "World",
                    "league": f"🏟 {lg.get('country','')} — {lg.get('name','')}",
                    "teams": f"⚽ {home.get('name')} vs {away.get('name')}",
                    "time": f"⏰ {when}",
                    "market": best_market,
                    "pick_name": best_name,
                    "odd": float(best_odd),
                    "pick": f"• {best_market} → {best_name}: {best_odd:.2f}",
                }
            )
    legs.sort(key=lambda L: L["odd"], reverse=True)
    _log(f"📦 legs candidates={len(legs)} (caps size={len(caps)})")
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


def _format_ticket(n: int, legs: List[Dict[str, Any]]) -> str:
    parts = [f"🎫 Ticket #{n}"]
    comps: List[str] = []
    for leg in legs:
        parts.extend(
            [
                leg["league"],
                f"🆔 {leg['fid']}",
                leg["teams"],
                leg["time"],
                leg["pick"],
                "",
            ]
        )
        comps.append(f"{leg['odd']:.2f}")
    total = _product([l["odd"] for l in legs])
    parts.append(f"TOTAL ODDS: {' × '.join(comps)} = {total:.2f}")
    return "\n".join(parts)


def _build_for_target(
    pool: List[Dict[str, Any]], target: float, used_fids: set
) -> Optional[List[Dict[str, Any]]]:
    cand = [x for x in pool if x["fid"] not in used_fids]
    cand.sort(key=lambda L: L["odd"], reverse=True)
    best: Optional[List[Dict[str, Any]]] = None

    # Greedy
    ticket: List[Dict[str, Any]] = []
    total = 1.0
    for leg in cand:
        if not _diversity_ok(ticket, leg):
            continue
        ticket.append(leg)
        total *= leg["odd"]
        if len(ticket) >= LEGS_MIN and total >= target:
            best = list(ticket)
            break

    # Small DFS
    def dfs(idx: int, cur: List[Dict[str, Any]], prod: float) -> None:
        nonlocal best
        if best and len(cur) >= len(best):
            return
        if len(cur) > LEGS_MAX:
            return
        if len(cur) >= LEGS_MIN and prod >= target:
            best = list(cur)
            return
        for j in range(idx, min(idx + 20, len(cand))):
            leg = cand[j]
            if any(x["fid"] == leg["fid"] for x in cur):
                continue
            if not _diversity_ok(cur, leg):
                continue
            dfs(j + 1, cur + [leg], prod * leg["odd"])
            if best:
                return

    if not best:
        dfs(0, [], 1.0)
    return best


def build_three_tickets(date_str: str) -> List[str]:
    tickets: List[str] = []
    used: set[int] = set()
    caps = dict(BASE_TH)
    for step in range(RELAX_STEPS + 1):
        legs = assemble_legs(date_str, caps)
        for idx, target in enumerate(TARGETS, start=1):
            if len(tickets) >= idx:
                continue
            built = _build_for_target(legs, target, used)
            if built:
                tickets.append(_format_ticket(len(tickets) + 1, built))
                used.update(x["fid"] for x in built)
        if len(tickets) >= 3:
            break
        caps = {k: (v + RELAX_ADD) for k, v in caps.items()}
        _log(f"↘ relax step={step + 1} caps+= {RELAX_ADD}")
    return tickets[:3]


# ===== OpenAI reasoning =====


class OpenAIConfigError(RuntimeError):
    """Raised when the OpenAI client is not properly configured."""


def _openai_headers() -> Dict[str, str]:
    if not OPENAI_API_KEY:
        raise OpenAIConfigError("OPENAI_API_KEY environment variable is not set")
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    if OPENAI_ORG:
        headers["OpenAI-Organization"] = OPENAI_ORG
    return headers


PROMPT_REASON = (
    "You are a football analyst. For the ticket below, write up to 5 one-line bullets "
    "with concrete stats if available (form L5, hit rates). Plain text only."
)


REASONING_FALLBACK = "- analysis unavailable -"


def openai_reason(ticket_text: str) -> str:
    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    body = {
        "model": OPENAI_MODEL,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "Be concise. Output plain text."},
            {
                "role": "user",
                "content": PROMPT_REASON + "\n---\n" + ticket_text,
            },
        ],
    }
    with httpx.Client(timeout=120) as c:
        r = c.post(url, headers=_openai_headers(), json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


# ===== Telegram =====
def post_to_telegram(message: str) -> None:
    """Šalje poruku na sve Telegram kanale definisane u TELEGRAM_CHANNELS."""

    token = TELEGRAM_BOT_TOKEN
    chans = [c.strip() for c in (TELEGRAM_CHANNELS or "").replace("\n", ",").split(",") if c.strip()]
    if not token or not chans:
        _log("ℹ️ Telegram not configured")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    _log(f"📡 Telegram BOT active, sending to {len(chans)} channels: {chans}")

    with httpx.Client(timeout=30) as c:
        for ch in chans:
            try:
                r = c.post(
                    url,
                    json={
                        "chat_id": ch,
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
                try:
                    data = r.json()
                except Exception:
                    data = {"raw": r.text[:200]}
                desc = data.get("description") or data.get("error_code") or data.get("raw", "")
                _log(f"📨 TG channel={ch} status={r.status_code} resp={desc}")
            except Exception as e:
                _log(f"⚠️ TG send error to {ch}: {e}")
            time.sleep(0.5)


# ===== Airtable =====
def _airtable_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }


def airtable_clear_table() -> None:
    if not all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID]):
        return
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
    with httpx.Client(timeout=60) as c:
        offset = None
        while True:
            params: Dict[str, Any] = {"pageSize": 100}
            if offset:
                params["offset"] = offset
            r = c.get(url, headers=_airtable_headers(), params=params)
            r.raise_for_status()
            data = r.json()
            recs = data.get("records", [])
            if not recs:
                break
            ids = [rec["id"] for rec in recs]
            query = "&".join([f"records[]={rid}" for rid in ids])
            dr = c.delete(f"{url}?{query}", headers=_airtable_headers())
            _log(f"🧹 Airtable delete {len(ids)} -> {dr.status_code}")
            offset = data.get("offset")
            if not offset:
                break


def airtable_insert_rows(rows: List[str]) -> Dict[str, Any]:
    if not all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID, AIRTABLE_FIELD_ID]):
        return {"ok": False, "reason": "missing_airtable_env"}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
    payload = {"records": [{"fields": {AIRTABLE_FIELD_ID: r}} for r in rows]}
    with httpx.Client(timeout=60) as c:
        r = c.post(url, headers=_airtable_headers(), json=payload)
        ok = 200 <= r.status_code < 300
        return {
            "ok": ok,
            "status": r.status_code,
            "resp": r.json() if r.content else {},
        }


# ===== File IO =====
def _today_filename(date_str: str) -> str:
    return f"focus_bets_{date_str}.txt"


def write_daily_log(date_str: str, tickets_with_reason: List[str]) -> None:
    fname = _today_filename(date_str)
    with open(fname, "w", encoding="utf-8") as f:
        for i, ticket in enumerate(tickets_with_reason, 1):
            f.write(ticket.strip() + "\n")
            if i < len(tickets_with_reason):
                f.write("\n")


def run(date_str: Optional[str] = None) -> Dict[str, Any]:
    if not date_str:
        date_str = datetime.now(TZ).strftime("%Y-%m-%d")
    _log(f"▶ date={date_str} targets={TARGETS} legs_min={LEGS_MIN} legs_max={LEGS_MAX}")
    tickets = build_three_tickets(date_str)
    _log(f"🎯 built_tickets={len(tickets)}")
    tickets_with_reason: List[str] = []
    openai_available = True
    openai_error_logged = False
    try:
        _openai_headers()
    except OpenAIConfigError as exc:
        openai_available = False
        openai_error_logged = True
        _log(f"ℹ️ OpenAI reasoning disabled: {exc}")
    for ticket in tickets:
        if not openai_available:
            reasoning = REASONING_FALLBACK
        else:
            try:
                reasoning = openai_reason(ticket)
            except OpenAIConfigError as exc:
                if not openai_error_logged:
                    _log(f"ℹ️ OpenAI reasoning disabled: {exc}")
                    openai_error_logged = True
                openai_available = False
                reasoning = REASONING_FALLBACK
            except Exception as exc:  # pragma: no cover - depends on external service
                _log(f"⚠️ OpenAI fail: {exc}")
                reasoning = REASONING_FALLBACK
        tickets_with_reason.append(f"{ticket}\n\n🧠 Reasoning:\n{reasoning}")

    write_daily_log(date_str, tickets_with_reason)

    for message in tickets_with_reason:
        if not DRY_RUN:
            post_to_telegram(message)

    airtable_result: Dict[str, Any] = {"ok": True, "status": 0}
    if not DRY_RUN:
        if FORCE_CLEAR_AIRTABLE:
            airtable_clear_table()
        airtable_result = airtable_insert_rows(tickets_with_reason)

    return {
        "date": date_str,
        "tickets_count": len(tickets_with_reason),
        "airtable": airtable_result,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
