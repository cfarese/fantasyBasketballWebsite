# pip install nba_api pandas
import time
import math
import unicodedata
import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats
from config import NBA_PER_GAME_CSV, SEASON_YEAR

# =======================
# CONFIGURATION
# =======================
SEASON = f"{SEASON_YEAR-1}-{str(SEASON_YEAR)[-2:]}"  # Format: "2025-26"
SEASON_TYPE = "Regular Season"     # "Pre Season", "Regular Season", "Playoffs"
OUTPUT_CSV = str(NBA_PER_GAME_CSV)
# =======================

# --- helper: remove accents / diacritics from names ---
def normalize_name(name: str) -> str:
    """Convert accented/unicode names like 'Dončić' → 'Doncic'."""
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")

# --- helper: truncate to 1 decimal place (toward zero) ---
def trunc1(x: float) -> float:
    if pd.isna(x):
        return x
    return math.trunc(x * 10) / 10.0

# --- fetch per-game player stats from NBA API ---
print(f"Fetching {SEASON_TYPE} stats for {SEASON}... (may take a few seconds)")
time.sleep(0.6)  # small delay helps avoid rate limits

stats = leaguedashplayerstats.LeagueDashPlayerStats(
    season=SEASON,
    season_type_all_star=SEASON_TYPE,
    per_mode_detailed="PerGame",
    measure_type_detailed_defense="Base",
    pace_adjust="N",
    plus_minus="N",
    rank="N"
)

df = stats.get_data_frames()[0]

# --- normalize player names ---
df["PLAYER_NAME"] = df["PLAYER_NAME"].apply(normalize_name)

# Ensure the columns we need exist; if not, create as zeros to be safe
for col in ["FGM","FGA","FTM","FTA","FG3M","REB","AST","STL","BLK","TOV","PTS","MIN"]:
    if col not in df.columns:
        df[col] = 0.0

# --- fantasy points per game using your scoring ---
fpts_pg = (
      2  * df["FGM"]
    + (-1)* df["FGA"]
    + 1  * df["FTM"]
    + (-1)* df["FTA"]
    + 1  * df["FG3M"]
    + 1  * df["REB"]
    + 2  * df["AST"]
    + 4  * df["STL"]
    + 4  * df["BLK"]
    + (-2)* df["TOV"]
    + 1  * df["PTS"]
)

# --- convert to per-36 minutes ---
# Handle zero-minute rows safely: if MIN == 0, set per-36 to 0
df["Fantasy Points per 36"] = fpts_pg.where(df["MIN"] > 0, 0) * (36 / df["MIN"].replace(0, pd.NA))
df["Fantasy Points per 36"] = df["Fantasy Points per 36"].fillna(0).map(trunc1)

# --- optional: keep tidy column order ---
keep_cols = [
    "PLAYER_ID","PLAYER_NAME","TEAM_ID","TEAM_ABBREVIATION","AGE","GP","W","L",
    "MIN","PTS","REB","AST","STL","BLK","TOV","PF",
    "FGM","FGA","FG_PCT","FG3M","FG3A","FG3_PCT","FTM","FTA","FT_PCT",
    "OREB","DREB","PLUS_MINUS","Fantasy Points per 36"
]
df = df[[c for c in keep_cols if c in df.columns]]

# --- save to CSV ---
df.to_csv(OUTPUT_CSV, index=False)
print(f"✅ Saved {len(df)} player rows to {OUTPUT_CSV}")
