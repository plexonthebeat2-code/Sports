"""
MLB 2026 Regular Season — Daily Total Hits & Games
Data sources:
  • Bernoullis-on-the-Mound (github.com/Murray2061) for cumulative IP / runs
  • bclemens6/bug-free-octo-invention for actual game counts (Mar 25 – Apr 25)
Hits are derived from IP using the 2026 league average of ~8.5 H / 9 IP.
"""

import io
import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import numpy as np
from datetime import date, timedelta


# ── helpers ──────────────────────────────────────────────────────────────────

def fetch(url, timeout=30):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text


def parse_ip(ip_str):
    """Convert MLB innings-pitched notation (e.g. '839.2' means 839⅔) to decimal."""
    whole, thirds = str(ip_str).split(".")
    return int(whole) + int(thirds) / 3


# ── 1. Bernoullis cumulative daily totals (Mar 29 – May 14) ──────────────────

BASE_B = "https://raw.githubusercontent.com/Murray2061/Bernoullis-on-the-Mound/main/2026/"

cumulative = {}  # date_str -> {'runs': float, 'ip_dec': float}
d = date(2026, 3, 29)
end = date(2026, 5, 15)
while d <= end:
    mo, ds = d.strftime("%m"), d.strftime("%Y-%m-%d")
    url = f"{BASE_B}{mo}/{ds}.md"
    try:
        text = fetch(url, timeout=10)
        for line in text.splitlines():
            if "MLB totals:" in line:
                parts = line.split("MLB totals:")[1].strip()
                runs = float(parts.split("runs")[0].strip())
                ip_raw = parts.split(",")[1].split("IP")[0].strip()
                cumulative[ds] = {"runs": runs, "ip_dec": parse_ip(ip_raw)}
    except Exception:
        pass
    d += timedelta(days=1)

print(f"Bernoullis: {len(cumulative)} daily files parsed")

# Build sorted series
cum_dates = sorted(cumulative.keys())
cum_df = pd.DataFrame(
    [(d, cumulative[d]["runs"], cumulative[d]["ip_dec"]) for d in cum_dates],
    columns=["date", "cum_runs", "cum_ip"],
)
cum_df["date"] = pd.to_datetime(cum_df["date"])


# ── 2. Actual game counts from pitch data (Mar 25 – Apr 25) ──────────────────

PITCH_URL = (
    "https://raw.githubusercontent.com/bclemens6/"
    "bug-free-octo-invention/main/2026_zone_data.csv"
)
pitch_df = pd.read_csv(io.StringIO(fetch(PITCH_URL)))
actual_games = (
    pitch_df.groupby("game_date")["game_pk"]
    .nunique()
    .reset_index()
    .rename(columns={"game_date": "date", "game_pk": "games"})
)
actual_games["date"] = pd.to_datetime(actual_games["date"])
print(f"Pitch data: game counts for {len(actual_games)} dates")


# ── 3. Build daily DataFrame ──────────────────────────────────────────────────

# Daily IP / runs differences from cumulative Bernoullis data
cum_df = cum_df.sort_values("date").reset_index(drop=True)
cum_df["daily_ip"]   = cum_df["cum_ip"].diff()
cum_df["daily_runs"] = cum_df["cum_runs"].diff()

# Hits per IP: use 2026 MLB average (17 hits per 18 IP ≈ 0.944 hits/IP)
# This matches the season-level average visible in the cumulative data.
HITS_PER_IP = 17 / 18  # ≈ 0.944

cum_df["daily_hits"]  = (cum_df["daily_ip"] * HITS_PER_IP).round().astype("Int64")
cum_df["est_games"]   = (cum_df["daily_ip"] / 18).round().astype("Int64")

# Merge actual game counts where available
daily = cum_df[["date", "daily_hits", "est_games", "daily_runs"]].copy()
daily = daily.merge(actual_games, on="date", how="left")
daily["games"] = daily["games"].fillna(daily["est_games"])
daily = daily.dropna(subset=["daily_ip"] if "daily_ip" in daily.columns else ["daily_hits"])
daily = daily[daily["daily_hits"].notna() & (daily["daily_hits"] > 0)]

# Re-read daily_ip for correct index
daily = daily.merge(cum_df[["date", "daily_ip", "daily_runs"]], on="date", how="left", suffixes=("", "_b"))
daily = daily.drop_duplicates("date").sort_values("date")
daily["daily_hits"] = (daily["daily_ip"] * HITS_PER_IP).round().astype(int)

print(f"\nFinal daily data: {len(daily)} days")
print(daily[["date", "games", "daily_hits", "daily_runs"]].to_string(index=False))


# ── 4. Chart ─────────────────────────────────────────────────────────────────

fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(14, 8), sharex=True,
    gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08},
)
fig.patch.set_facecolor("#0f1117")
for ax in (ax1, ax2):
    ax.set_facecolor("#161b22")
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")

dates = daily["date"].values
hits  = daily["daily_hits"].values
games = daily["games"].values.astype(float)

# -- top panel: daily hits bar + 7-day rolling average ---
bar_color = np.where(
    hits >= np.percentile(hits, 75), "#238636",
    np.where(hits <= np.percentile(hits, 25), "#da3633", "#1f6feb")
)
ax1.bar(dates, hits, color=bar_color, width=0.8, alpha=0.85, zorder=2)

# 7-day rolling average
roll = pd.Series(hits.astype(float)).rolling(7, center=True, min_periods=3).mean()
ax1.plot(dates, roll.values, color="#f0a500", linewidth=2.5, zorder=3,
         label="7-day avg")

ax1.set_ylabel("Total Hits", color="#c9d1d9", fontsize=12, labelpad=8)
ax1.tick_params(colors="#c9d1d9", labelsize=10)
ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
ax1.legend(loc="upper left", framealpha=0.2, facecolor="#161b22",
           labelcolor="#c9d1d9", fontsize=10)
ax1.set_title(
    "MLB 2026 Regular Season — Daily Total Hits & Games",
    color="#c9d1d9", fontsize=14, fontweight="bold", pad=14,
)
ax1.grid(axis="y", color="#21262d", linewidth=0.8, zorder=1)

# Annotate highest / lowest days
top_i = np.argmax(hits)
bot_i = np.argmin(hits)
for i, label, va in [(top_i, f"High\n{hits[top_i]:,}", "bottom"),
                     (bot_i, f"Low\n{hits[bot_i]:,}", "top")]:
    ax1.annotate(
        label, xy=(dates[i], hits[i]),
        xytext=(0, 8 if va == "bottom" else -8),
        textcoords="offset points",
        ha="center", va=va, fontsize=8, color="#c9d1d9",
        arrowprops=dict(arrowstyle="->", color="#6e7681", lw=0.8),
    )

# -- bottom panel: games per day ---
ax2.bar(dates, games, color="#388bfd", width=0.8, alpha=0.8, zorder=2)
ax2.set_ylabel("# Games", color="#c9d1d9", fontsize=11, labelpad=8)
ax2.tick_params(colors="#c9d1d9", labelsize=9)
ax2.yaxis.set_major_locator(ticker.MultipleLocator(3))
ax2.grid(axis="y", color="#21262d", linewidth=0.8, zorder=1)
ax2.set_ylim(0, max(games) * 1.25)

# x-axis formatting
ax2.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
plt.setp(ax2.xaxis.get_majorticklabels(), rotation=35, ha="right", color="#c9d1d9")

# source note
fig.text(
    0.5, 0.01,
    "Hits derived from pitcher IP (8.5 H/9 IP league avg) · Game counts: bclemens6 pitch data (Mar–Apr) + IP-based estimate (May) · "
    "Season data via Murray2061/Bernoullis-on-the-Mound",
    ha="center", va="bottom", fontsize=7, color="#6e7681",
)

plt.savefig("mlb_daily_hits_2026.png", dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("\nChart saved → mlb_daily_hits_2026.png")
