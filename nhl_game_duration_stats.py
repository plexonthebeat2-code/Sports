"""
NHL Day Games: Start Time vs Total Goals Scored
Real schedule + score data from sportsdataverse/fastRhockey-data
Seasons: 2021-22, 2022-23, 2023-24
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
    url = SCHEDULE_BASE + f"nhl_schedule_{year}.csv"
    r = requests.get(url, timeout=20)
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
    if h == 0:  return "12am"
    return f"{h}am"


def main():
    print("NHL Day Games (10am–5pm ET): Start Time vs Total Goals")
    print("=" * 56)
    print(f"Seasons: {', '.join(SEASONS.values())}")
    print()

    all_rows = []
    for year, label in SEASONS.items():
        rows = download_schedule(year)
        print(f"  {label}: {len(rows)} games loaded")
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
            total_goals = int(row["away_score"]) + int(row["home_score"])
        except (ValueError, KeyError):
            continue

        games.append({
            "date":          start_et.strftime("%Y-%m-%d"),
            "away":          row.get("away_team_name", ""),
            "home":          row.get("home_team_name", ""),
            "away_score":    int(row["away_score"]),
            "home_score":    int(row["home_score"]),
            "total_goals":   total_goals,
            "start_hour_et": start_et.hour,
            "start_time_et": start_et.strftime("%I:%M %p"),
            "game_type":     row.get("game_type", "REG"),
        })

    print(f"Day games with scores: {len(games)}")
    print()

    # Build cross-tab: start_hour × total_goals
    counts = defaultdict(lambda: defaultdict(int))
    for g in games:
        counts[g["start_hour_et"]][g["total_goals"]] += 1

    start_hours = sorted(counts.keys())
    all_goal_counts = sorted({g for sh in counts for g in counts[sh]})

    col_w = 5
    lw    = 8
    corner = "Start"
    header = (
        f"{corner:<{lw}}"
        + "".join(f"{g:>{col_w}}" for g in all_goal_counts)
        + f"{'Total':>{col_w + 1}}"
    )
    bar = "─" * len(header)

    print(bar)
    print("  Start hour  ×  Total goals scored in game")
    print(bar)
    print(header)
    print(bar)

    for sh in start_hours:
        row_total = sum(counts[sh].values())
        line = (
            f"{fmt_hour(sh):<{lw}}"
            + "".join(f"{counts[sh].get(g, 0):>{col_w}}" for g in all_goal_counts)
            + f"{row_total:>{col_w + 1}}"
        )
        print(line)

    print(bar)
    col_totals  = {g: sum(counts[sh].get(g, 0) for sh in start_hours) for g in all_goal_counts}
    grand_total = sum(col_totals.values())
    print(
        f"{'Total':<{lw}}"
        + "".join(f"{col_totals[g]:>{col_w}}" for g in all_goal_counts)
        + f"{grand_total:>{col_w + 1}}"
    )
    print(bar)

    # Per-start-hour breakdown as plain list
    print()
    print("Plain breakdown by start time:")
    print()
    for sh in start_hours:
        total = sum(counts[sh].values())
        avg   = sum(g * counts[sh][g] for g in counts[sh]) / total
        print(f"  {fmt_hour(sh)} starts  ({total} games, avg {avg:.1f} goals/game)")
        for g in sorted(counts[sh]):
            n   = counts[sh][g]
            pct = 100 * n / total
            bar_vis = "█" * n
            print(f"    {g:>2} goals: {n:>3}  ({pct:4.1f}%)  {bar_vis}")
        print()

    # Save
    with open("nhl_goals_by_start_time.json", "w") as f:
        json.dump(games, f, indent=2)
    print(f"Full game list saved to nhl_goals_by_start_time.json")

    print()
    print("Data: sportsdataverse/fastRhockey-data · All times Eastern")


if __name__ == "__main__":
    main()
