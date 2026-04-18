"""
NHL Day Games: Over/Under Results by Start Time
Real schedule + score data from sportsdataverse/fastRhockey-data
Seasons: 2021-22, 2022-23, 2023-24

Since per-game O/U lines aren't freely available, we evaluate against
the three most common NHL totals: 5.5 · 6.0 · 6.5
  Over : total goals > line
  Under: total goals < line
  Push : total goals == line (6.0 line only)
"""

import requests
import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timedelta

SCHEDULE_BASE = (
    "https://raw.githubusercontent.com/sportsdataverse/"
    "fastRhockey-data/main/nhl/schedules/csv/"
)
SEASONS = {"2022": "2021-22", "2023": "2022-23", "2024": "2023-24"}


def download_schedule(year):
    r = requests.get(SCHEDULE_BASE + f"nhl_schedule_{year}.csv", timeout=20)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))


def parse_utc(ts):
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%MZ"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            pass
    return None


def utc_to_et(dt):
    offset = -4 if 4 <= dt.month <= 10 else -5
    return dt + timedelta(hours=offset)


def fmt_hour(h):
    if h == 12: return "12pm"
    if h > 12:  return f"{h - 12}pm"
    return f"{h}am"


def ou_result(total_goals, line):
    if total_goals > line:  return "Over"
    if total_goals < line:  return "Under"
    return "Push"


def _print_ou_table(games, line):
    by_hour = defaultdict(list)
    for g in games:
        by_hour[g["start_hour_et"]].append(g)

    col_w  = 9
    lw     = 8
    header = f"{'Start':<{lw}}{'Over':>{col_w}}{'Under':>{col_w}}{'Push':>{col_w}}{'Total':>{col_w}}  {'Over%':>6}"
    print(f"\n  Line {line}")
    print("  " + "─" * (len(header) - 2))
    print("  " + header)
    print("  " + "─" * (len(header) - 2))

    totals = {"Over": 0, "Under": 0, "Push": 0, "n": 0}
    for sh in sorted(by_hour):
        res = defaultdict(int)
        for g in by_hour[sh]:
            res[ou_result(g["total_goals"], line)] += 1
        n        = len(by_hour[sh])
        over_pct = 100 * res["Over"] / n if n else 0
        print(
            "  " + f"{fmt_hour(sh):<{lw}}"
            f"{res['Over']:>{col_w}}{res['Under']:>{col_w}}"
            f"{res['Push']:>{col_w}}{n:>{col_w}}  {over_pct:>5.1f}%"
        )
        for k in ("Over", "Under", "Push"):
            totals[k] += res[k]
        totals["n"] += n

    print("  " + "─" * (len(header) - 2))
    op = 100 * totals["Over"] / totals["n"] if totals["n"] else 0
    print(
        "  " + f"{'All':<{lw}}"
        f"{totals['Over']:>{col_w}}{totals['Under']:>{col_w}}"
        f"{totals['Push']:>{col_w}}{totals['n']:>{col_w}}  {op:>5.1f}%"
    )


def main():
    print("NHL Day Games (10am–5pm ET): Over/Under by Start Time")
    print("=" * 56)
    print(f"Seasons: {', '.join(SEASONS.values())}")
    print()

    all_rows = []
    for year, label in SEASONS.items():
        rows = download_schedule(year)
        print(f"  {label}: {len(rows)} games")
        all_rows.extend(rows)
    print()

    games = []
    for row in all_rows:
        ts = row.get("game_date_time", "")
        if not ts or ts.endswith("T00:00:00Z"):
            continue
        start_utc = parse_utc(ts)
        if not start_utc:
            continue
        start_et = utc_to_et(start_utc)
        if not (10 <= start_et.hour <= 17):
            continue
        if row.get("status_abstract_game_state") not in ("Final", ""):
            continue
        try:
            away = int(row["away_score"])
            home = int(row["home_score"])
        except (ValueError, KeyError):
            continue

        total = away + home
        games.append({
            "date":          start_et.strftime("%Y-%m-%d"),
            "away":          row.get("away_team_name", ""),
            "home":          row.get("home_team_name", ""),
            "away_score":    away,
            "home_score":    home,
            "total_goals":   total,
            "start_hour_et": start_et.hour,
            "start_time_et": start_et.strftime("%I:%M %p"),
            "game_type":     row.get("game_type", "REG"),
        })

    print(f"Day games with scores: {len(games)}")
    sat = [g for g in games if datetime.strptime(g["date"], "%Y-%m-%d").weekday() == 5]
    sun = [g for g in games if datetime.strptime(g["date"], "%Y-%m-%d").weekday() == 6]
    print(f"  Saturdays: {len(sat)}  |  Sundays: {len(sun)}")
    print()

    LINES = [5.5, 6.0, 6.5]

    for day_label, subset in [("SATURDAY", sat), ("SUNDAY", sun)]:
        print("=" * 60)
        print(f"  {day_label}  ({len(subset)} games)")
        print("=" * 60)
        for line in LINES:
            _print_ou_table(subset, line)
        print()

    print("=" * 60)
    print(f"  ALL DAY GAMES  ({len(games)} games)")
    print("=" * 60)
    for line in LINES:
        _print_ou_table(games, line)
    print()

    # ── Detailed breakdown for most common line (6.0) ────────────────────────
    print("─" * 60)
    print("  Goal-by-goal breakdown vs 6.0 line, per start hour")
    print("─" * 60)

    by_hour = defaultdict(list)
    for g in games:
        by_hour[g["start_hour_et"]].append(g)

    for sh in sorted(by_hour.keys()):
        hour_games = by_hour[sh]
        n         = len(hour_games)
        overs     = sum(1 for g in hour_games if g["total_goals"] > 6.0)
        unders    = sum(1 for g in hour_games if g["total_goals"] < 6.0)
        pushes    = sum(1 for g in hour_games if g["total_goals"] == 6.0)
        avg_goals = sum(g["total_goals"] for g in hour_games) / n
        over_pct  = 100 * overs / n

        # Count by total goals
        goal_counts = defaultdict(int)
        for g in hour_games:
            goal_counts[g["total_goals"]] += 1

        print(f"\n  {fmt_hour(sh)}  —  {n} games  |  avg {avg_goals:.1f} goals  |  Over(6): {overs} ({over_pct:.0f}%)  Under: {unders}  Push: {pushes}")
        for goals in sorted(goal_counts):
            result = "OVER " if goals > 6 else ("PUSH " if goals == 6 else "under")
            bar    = "█" * goal_counts[goals]
            pct    = 100 * goal_counts[goals] / n
            print(f"    {goals:>2}g [{result}]: {goal_counts[goals]:>3}  ({pct:4.1f}%)  {bar}")

    # Save
    out = []
    for g in games:
        g["ou_55"]  = ou_result(g["total_goals"], 5.5)
        g["ou_60"]  = ou_result(g["total_goals"], 6.0)
        g["ou_65"]  = ou_result(g["total_goals"], 6.5)
        out.append(g)
    with open("nhl_ou_day_games.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n\nFull results saved to nhl_ou_day_games.json ({len(out)} games)")
    print()
    print("Note: actual per-game lines vary by matchup. 5.5/6.0/6.5 cover")
    print("the vast majority of NHL regular-season totals.")
    print("Data: sportsdataverse/fastRhockey-data · All times Eastern")


if __name__ == "__main__":
    main()
