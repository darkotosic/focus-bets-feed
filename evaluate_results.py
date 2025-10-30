#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, sys, time
from pathlib import Path
from datetime import datetime, timezone

API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
BASE_URL = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io").rstrip("/")
PUBLIC = Path("public")
PUBLIC.mkdir(parents=True, exist_ok=True)


def log(s: str) -> None:
    print(s, file=sys.stderr, flush=True)


def http_get(url: str, params: dict) -> dict:
    import httpx
    headers = {"x-apisports-key": API_KEY}
    for _ in range(4):
        try:
            with httpx.Client(timeout=20) as c:
                r = c.get(url, headers=headers, params=params)
            if r.status_code == 429:
                ra = r.headers.get("Retry-After", "1")
                time.sleep(float(ra))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log(f"HTTP error {e}, retrying...")
            time.sleep(1.5)
    return {}


def fetch_fixture_result(fid: int) -> dict:
    """Vrati dict sa FT rezultatom."""
    url = f"{BASE_URL}/fixtures"
    data = http_get(url, {"id": fid}).get("response") or []
    if not data:
        return {"status": "NA"}
    fx = data[0].get("fixture", {}) or {}
    goals = data[0].get("goals", {}) or {}
    return {
        "status": (fx.get("status") or {}).get("short") or "NA",
        "home_goals": goals.get("home"),
        "away_goals": goals.get("away"),
    }


def leg_hit(leg: dict, res: dict) -> bool:
    if res.get("status") not in {"FT", "AET", "PEN"}:
        # ako nije gotova, tretiramo kao promašaj da se vidi u appu
        return False
    hg = res.get("home_goals", 0) or 0
    ag = res.get("away_goals", 0) or 0
    market = leg.get("market")
    pick = leg.get("pick")

    # Match Winner
    if market == "Match Winner":
        if pick == "Home":
            return hg > ag
        if pick == "Away":
            return ag > hg
        return False

    # Double Chance
    if market == "Double Chance":
        if pick == "1X":
            return hg >= ag
        if pick == "X2":
            return ag >= hg
        if pick == "12":
            return hg != ag
        return False

    # BTTS
    if market == "BTTS":
        both = (hg > 0 and ag > 0)
        if pick == "Yes":
            return both
        if pick == "No":
            return not both
        return False

    # Over/Under
    if market == "Over/Under":
        # očekujemo format "Over 1.5" ili "Under 3.5"
        try:
            parts = pick.split()
            ou = parts[0].lower()
            line = float(parts[1])
            total = hg + ag
            if ou == "over":
                return total > line - 1e-9
            else:
                return total < line + 1e-9
        except Exception:
            return False

    return False


def main() -> None:
    snap_path = PUBLIC / "feed_snapshot.json"
    if not snap_path.exists():
        # nema jutarnjeg
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out = {"date": now, "tickets": [], "error": "feed_snapshot.json not found"}
        with open(PUBLIC / "evaluation.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(json.dumps({"status": "no-snapshot"}, ensure_ascii=False))
        return

    with open(snap_path, "r", encoding="utf-8") as f:
        snap = json.load(f)

    date_str = snap.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    evaluated_tickets = []

    per_ticket_payloads = []

    for ticket in snap.get("tickets", []):
        legs = ticket.get("legs") or []
        out_legs = []
        simple_legs = []
        all_hit = True
        any_pending = False
        has_loss = False
        for leg in legs:
            fid = leg.get("fid")
            try:
                fetch_id = int(str(fid))
            except (TypeError, ValueError):
                fetch_id = None
            if fetch_id is None:
                res = {"status": "NA", "home_goals": None, "away_goals": None}
            else:
                res = fetch_fixture_result(fetch_id)
            ok = leg_hit(
                {
                    "market": leg.get("market"),
                    "pick": leg.get("pick") or leg.get("pick_name"),
                },
                res,
            )
            if not ok:
                all_hit = False
            status = res.get("status")
            is_final = status in {"FT", "AET", "PEN"}
            if not is_final:
                any_pending = True
            elif not ok:
                has_loss = True
            fixture_id = fetch_id
            leg_summary = {
                "fixture_id": fixture_id,
                "result": "win" if ok and is_final else ("pending" if not is_final else "lose"),
            }
            hg = res.get("home_goals")
            ag = res.get("away_goals")
            if is_final and hg is not None and ag is not None:
                leg_summary["score_ft"] = f"{hg}-{ag}"
            simple_legs.append(leg_summary)
            out_legs.append(
                {
                    **leg,
                    "result": {
                        "status": res.get("status"),
                        "home_goals": res.get("home_goals"),
                        "away_goals": res.get("away_goals"),
                        "hit": ok,
                        "emoji": "✅" if ok else "❌",
                    },
                }
            )

        total_odds = float(ticket.get("total_odds") or 0)
        label = f"{total_odds:.2f}"
        if all_hit and legs:
            label = f"{label} ✅"

        ticket_slug = str(ticket.get("name") or ticket.get("target") or "ticket").strip()
        if not ticket_slug:
            ticket_slug = "ticket"
        ticket_slug = ticket_slug.replace(" ", "_")

        has_legs = bool(legs)

        if has_loss:
            ticket_result = "lose"
        elif any_pending:
            ticket_result = "pending"
        elif has_legs and all_hit:
            ticket_result = "win"
        elif not has_legs:
            ticket_result = "pending"
        else:
            ticket_result = "lose"

        per_ticket_payloads.append(
            {
                "slug": ticket_slug,
                "payload": {"ticket_result": ticket_result, "legs": simple_legs},
            }
        )

        evaluated_tickets.append(
            {
                "name": ticket.get("name"),
                "target": ticket.get("target"),
                "total_odds": total_odds,
                "total_label": label,
                "all_hit": all_hit,
                "legs": out_legs,
            }
        )

    out_obj = {
        "date": date_str,
        "tickets": evaluated_tickets,
    }

    with open(PUBLIC / "evaluation.json", "w", encoding="utf-8") as f:
        json.dump(out_obj, f, ensure_ascii=False, indent=2)

    for item in per_ticket_payloads:
        out_path = PUBLIC / f"eval_{item['slug']}.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(item["payload"], fh, ensure_ascii=False, indent=2)

    print(json.dumps({"status": "ok", "file": "public/evaluation.json"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
