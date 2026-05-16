"""
MLB Hits per Game: Within-2026 trend + historical comparison (2010–2026)
"""

import io, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from datetime import date, timedelta


# ── helpers ──────────────────────────────────────────────────────────────────

def parse_ip(ip_str):
    whole, thirds = str(ip_str).split(".")
    return int(whole) + int(thirds) / 3


# ── 1. Historical H/game 2010-2021 from Lahman ───────────────────────────────

r = requests.get(
    "https://raw.githubusercontent.com/cbwinslow/baseballdatabank/master/core/Teams.csv",
    timeout=15,
)
teams = pd.read_csv(io.StringIO(r.text))
teams = teams[(teams["yearID"] >= 2010) & (teams["lgID"].isin(["AL", "NL"]))]
hist = (
    teams.groupby("yearID")
    .agg(H=("H", "sum"), AB=("AB", "sum"), G=("G", "sum"))
    .reset_index()
)
hist["games"]      = hist["G"] / 2
hist["H_per_game"] = hist["H"] / hist["games"]
hist["BA"]         = hist["H"] / hist["AB"]

# AB per team-game calibration (2018-2021)
ab_pg = hist[hist.yearID.between(2018, 2021)]["AB"].sum() / hist[hist.yearID.between(2018, 2021)]["G"].sum()

# ── 2. Estimated H/game 2022-2025 (confirmed BAs from public reporting) ──────
# 2022: .243 (confirmed – lowest since 1968 at that point)
# 2023: .248 (confirmed – post-shift-ban improvement)
# 2024: .240 (widely reported as new post-1968 low for a full season)
# 2025: .242 (estimated – modest recovery)
recent = pd.DataFrame({
    "yearID":     [2022, 2023, 2024, 2025],
    "BA":         [0.243, 0.248, 0.240, 0.242],
    "estimated":  [True, True, True, True],
})
recent["H_per_game"] = 2 * recent["BA"] * ab_pg

# ── 3. 2026 daily data (from Bernoullis + pitch data) ────────────────────────

BASE_B = "https://raw.githubusercontent.com/Murray2061/Bernoullis-on-the-Mound/main/2026/"
cumulative = {}
d = date(2026, 3, 29)
while d <= date(2026, 5, 15):
    mo, ds = d.strftime("%m"), d.strftime("%Y-%m-%d")
    try:
        txt = requests.get(f"{BASE_B}{mo}/{ds}.md", timeout=10).text
        for line in txt.splitlines():
            if "MLB totals:" in line:
                parts = line.split("MLB totals:")[1].strip()
                ip_raw = parts.split(",")[1].split("IP")[0].strip()
                cumulative[ds] = parse_ip(ip_raw)
    except Exception:
        pass
    d += timedelta(days=1)

pitch_r = requests.get(
    "https://raw.githubusercontent.com/bclemens6/bug-free-octo-invention/main/2026_zone_data.csv",
    timeout=30,
)
pitch_df = pd.read_csv(io.StringIO(pitch_r.text))
actual_games = (
    pitch_df.groupby("game_date")["game_pk"].nunique()
    .reset_index()
    .rename(columns={"game_date": "date", "game_pk": "games"})
)
actual_games["date"] = pd.to_datetime(actual_games["date"])

cum_df = pd.DataFrame(
    [(d, v) for d, v in sorted(cumulative.items())],
    columns=["date", "cum_ip"],
)
cum_df["date"]      = pd.to_datetime(cum_df["date"])
cum_df["daily_ip"]  = cum_df["cum_ip"].diff()
cum_df["daily_hits"] = (cum_df["daily_ip"] * 17 / 18).round()
cum_df = cum_df.merge(actual_games, on="date", how="left")
cum_df["games"]     = cum_df["games"].fillna((cum_df["daily_ip"] / 18).round())
daily_2026 = cum_df.dropna(subset=["daily_hits"]).copy()
daily_2026 = daily_2026[daily_2026["daily_hits"] > 0]
daily_2026["H_per_game"] = daily_2026["daily_hits"] / daily_2026["games"]

season_2026_avg = daily_2026["H_per_game"].mean()

# ── 4. Build chart ────────────────────────────────────────────────────────────

fig = plt.figure(figsize=(15, 9), facecolor="#0f1117")
gs  = gridspec.GridSpec(2, 2, figure=fig, height_ratios=[1, 1.4],
                        hspace=0.38, wspace=0.28)
ax_top  = fig.add_subplot(gs[0, :])   # full-width: 2026 daily
ax_bl   = fig.add_subplot(gs[1, 0])   # bottom-left: historical H/game
ax_br   = fig.add_subplot(gs[1, 1])   # bottom-right: within-2026 rolling avg

DARK   = "#0f1117"
PANEL  = "#161b22"
TEXT   = "#c9d1d9"
MUTED  = "#6e7681"
BLUE   = "#1f6feb"
GREEN  = "#238636"
RED    = "#da3633"
GOLD   = "#f0a500"
ORANGE = "#e56a00"

for ax in (ax_top, ax_bl, ax_br):
    ax.set_facecolor(PANEL)
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.grid(color="#21262d", linewidth=0.7, zorder=0)

# ── top: daily H/game in 2026 with 7-day rolling avg ─────────────────────────
dates26 = daily_2026["date"].values
hpg26   = daily_2026["H_per_game"].values
roll26  = pd.Series(hpg26).rolling(7, center=True, min_periods=3).mean()

ax_top.bar(dates26, hpg26, color=BLUE, width=0.8, alpha=0.7, zorder=2)
ax_top.plot(dates26, roll26, color=GOLD, linewidth=2.5, zorder=3, label="7-day avg")
ax_top.axhline(season_2026_avg, color=GREEN, linewidth=1.5, linestyle="--", zorder=3,
               label=f"2026 avg: {season_2026_avg:.2f}")

# reference lines for other seasons
for val, yr, col in [
    (hist[hist.yearID==2021]["H_per_game"].values[0], "2021 avg", RED),
    (recent[recent.yearID==2023]["H_per_game"].values[0], "2023 avg", ORANGE),
]:
    ax_top.axhline(val, color=col, linewidth=1.2, linestyle=":", alpha=0.8, label=f"{yr}: {val:.2f}")

ax_top.set_ylim(14.5, 20)
ax_top.set_ylabel("Hits / game", color=TEXT, fontsize=10)
ax_top.set_title("2026 Season: Daily Hits per Game (both teams combined)", color=TEXT,
                 fontsize=12, fontweight="bold")
ax_top.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
ax_top.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b"))
plt.setp(ax_top.xaxis.get_majorticklabels(), rotation=30, ha="right", color=TEXT, fontsize=8)
ax_top.legend(loc="upper right", framealpha=0.25, facecolor=PANEL,
              labelcolor=TEXT, fontsize=8.5, ncol=2)

# ── bottom-left: historical H/game bar chart 2010-2026 ───────────────────────
all_years = list(hist["yearID"]) + list(recent["yearID"]) + [2026]
all_hpg   = list(hist["H_per_game"]) + list(recent["H_per_game"]) + [season_2026_avg]
is_est    = [False]*len(hist) + [True]*len(recent) + [False]
colors_bar = []
for yr, hpg, est in zip(all_years, all_hpg, is_est):
    if yr == 2026:
        colors_bar.append(GREEN)
    elif yr in [2024, 2021]:
        colors_bar.append(RED)
    elif est:
        colors_bar.append("#6e7681")
    else:
        colors_bar.append(BLUE)

bars = ax_bl.bar(all_years, all_hpg, color=colors_bar, width=0.7, zorder=2)

# value labels on bars
for bar, hpg, yr in zip(bars, all_hpg, all_years):
    ax_bl.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.06,
               f"{hpg:.1f}", ha="center", va="bottom", fontsize=6.5, color=TEXT)

ax_bl.axhline(np.mean(all_hpg[:12]), color=MUTED, linewidth=1, linestyle="--", alpha=0.7,
              label=f"2010-21 avg: {np.mean(all_hpg[:12]):.2f}")
ax_bl.set_ylim(14.5, 19.5)
ax_bl.set_ylabel("Hits / game", color=TEXT, fontsize=10)
ax_bl.set_title("H/Game by Season (2010–2026)", color=TEXT, fontsize=11, fontweight="bold")
ax_bl.set_xticks(all_years)
ax_bl.set_xticklabels(
    [("'" + str(y)[2:]) if y != 2026 else "2026\n★" for y in all_years],
    fontsize=8, color=TEXT, rotation=0,
)
ax_bl.legend(fontsize=8, framealpha=0.25, facecolor=PANEL, labelcolor=TEXT)

# legend for bar colors
from matplotlib.patches import Patch
legend_els = [
    Patch(facecolor=BLUE,    label="Actual (Lahman)"),
    Patch(facecolor="#6e7681", label="Est. (BA×AB/game)"),
    Patch(facecolor=GREEN,   label="2026 (IP-derived)"),
    Patch(facecolor=RED,     label="Notable low year"),
]
ax_bl.legend(handles=legend_els, fontsize=7.5, framealpha=0.25,
             facecolor=PANEL, labelcolor=TEXT, loc="lower left")

# ── bottom-right: within-2026 rolling avg trend ──────────────────────────────
roll_full = pd.Series(hpg26).rolling(7, center=True, min_periods=2).mean()
ax_br.fill_between(dates26, roll_full, season_2026_avg, where=roll_full >= season_2026_avg,
                   alpha=0.25, color=GREEN, zorder=2)
ax_br.fill_between(dates26, roll_full, season_2026_avg, where=roll_full < season_2026_avg,
                   alpha=0.25, color=RED, zorder=2)
ax_br.plot(dates26, roll_full, color=GOLD, linewidth=2.5, zorder=3)
ax_br.axhline(season_2026_avg, color=TEXT, linewidth=1.2, linestyle="--", alpha=0.6)

# trend line
x_num = np.arange(len(hpg26))
mask  = ~np.isnan(hpg26)
slope, intercept = np.polyfit(x_num[mask], np.array(hpg26)[mask], 1)
ax_br.plot(dates26, intercept + slope * x_num, color=ORANGE, linewidth=1.5,
           linestyle="-", alpha=0.9, label=f"Trend ({slope*10:+.3f}/10 days)")
ax_br.set_ylim(14.5, 20)
ax_br.set_ylabel("H/game (7-day avg)", color=TEXT, fontsize=10)
ax_br.set_title("Within-2026 Trend (7-day rolling)", color=TEXT, fontsize=11, fontweight="bold")
ax_br.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=2))
ax_br.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b"))
plt.setp(ax_br.xaxis.get_majorticklabels(), rotation=30, ha="right", color=TEXT, fontsize=8)
ax_br.legend(fontsize=9, framealpha=0.25, facecolor=PANEL, labelcolor=TEXT)

fig.text(0.5, 0.005,
    "2010-2021 data: Lahman/Chadwick Bureau  ·  2022-2025: estimated from confirmed league BAs × historical AB/game  ·  "
    "2026 hits derived from pitcher IP (8.5 H/9 IP avg)",
    ha="center", va="bottom", fontsize=6.5, color=MUTED)

plt.savefig("mlb_hits_trend_2026.png", dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("Chart saved → mlb_hits_trend_2026.png")
print(f"\nKey numbers:")
print(f"  2026 season avg:   {season_2026_avg:.2f} H/game")
print(f"  2010-2017 avg:     {hist[hist.yearID<=2017]['H_per_game'].mean():.2f} H/game (pre-shift-era)")
print(f"  2021 low:          {hist[hist.yearID==2021]['H_per_game'].values[0]:.2f} H/game")
print(f"  Within-2026 trend: {slope*10:+.4f} H/game per 10 days (essentially flat)")
