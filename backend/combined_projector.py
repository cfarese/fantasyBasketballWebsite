import os
import sys
import math
import subprocess
import unicodedata
import pandas as pd
from config import FANTASY_PROJECTIONS_CSV, NBA_PER_GAME_CSV, WEIGHTED_PER36_CSV, PROJECTION_WEIGHT, SPS_WEIGHT

# ---- CONFIG ----
PROJECTIONS_CSV = str(FANTASY_PROJECTIONS_CSV)
SPS_EXPECTED    = str(NBA_PER_GAME_CSV)
OUTPUT_CSV      = str(WEIGHTED_PER36_CSV)

W_PROJ = PROJECTION_WEIGHT
W_SPS  = SPS_WEIGHT
# ---------------

def normalize_ascii_capitalized(s: str) -> str:
    """Convert to ASCII and use proper capitalization (e.g. 'Luka Doncic')."""
    if pd.isna(s):
        return None
    # Normalize to remove accents
    clean = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    # Lowercase everything, then title case it
    clean = clean.strip().title()
    return clean

def trunc1(x: float) -> float:
    """Truncate (not round) to 1 decimal place."""
    if pd.isna(x):
        return 0.0
    return math.trunc(x * 10) / 10.0

def find_name_col(df: pd.DataFrame) -> str:
    for c in ["PLAYER_NAME", "Player", "player_name", "Name"]:
        if c in df.columns:
            return c
    return df.columns[0]

def find_sps_csv() -> str | None:
    if os.path.exists(SPS_EXPECTED):
        return SPS_EXPECTED
    return None

def main():
    print("Running sps_2.py...")
    subprocess.run([sys.executable, "sps_2.py"], check=True)

    sps_csv = find_sps_csv()
    if not sps_csv:
        raise SystemExit(f"Could not find sps_2 output.")
    if not os.path.exists(PROJECTIONS_CSV):
        raise SystemExit(f"Missing projections CSV: {PROJECTIONS_CSV}")

    proj = pd.read_csv(PROJECTIONS_CSV)
    sps  = pd.read_csv(sps_csv)

    proj_name_col = find_name_col(proj)
    sps_name_col  = find_name_col(sps)

    proj_fpts_col = proj.columns[-1]
    sps_fpts_col  = sps.columns[-1]

    # Normalize ASCII and proper capitalization
    proj["NAME_CLEAN"] = proj[proj_name_col].map(normalize_ascii_capitalized)
    sps["NAME_CLEAN"]  = sps[sps_name_col].map(normalize_ascii_capitalized)

    proj_small = proj[["NAME_CLEAN", proj_fpts_col]].rename(columns={proj_fpts_col: "PROJ_FPTS36"})
    sps_small  = sps[["NAME_CLEAN", sps_fpts_col, "MIN"]].rename(columns={sps_fpts_col: "SPS_FPTS36"})

    # Full outer merge so no players are dropped
    merged = pd.merge(proj_small, sps_small, on="NAME_CLEAN", how="outer")

    merged["PROJ_FPTS36"] = pd.to_numeric(merged["PROJ_FPTS36"], errors="coerce").fillna(0)
    merged["SPS_FPTS36"]  = pd.to_numeric(merged["SPS_FPTS36"], errors="coerce").fillna(0)
    merged["MIN"] = pd.to_numeric(merged["MIN"], errors="coerce").fillna(0)

    # Handle case where one projection is 0 - use the other entirely
    def calculate_projection(row):
        proj_val = row["PROJ_FPTS36"]
        sps_val = row["SPS_FPTS36"]
        
        # If one is 0, use the other entirely
        if proj_val == 0 and sps_val > 0:
            return trunc1(sps_val)
        elif sps_val == 0 and proj_val > 0:
            return trunc1(proj_val)
        # Otherwise use weighted average
        else:
            return trunc1(W_PROJ * proj_val + W_SPS * sps_val)
    
    merged["Per36_Projection"] = merged.apply(calculate_projection, axis=1)
    
    # Calculate per-game projection: points_per_36 * minutes / 36
    merged["PerGame_Projection"] = (merged["Per36_Projection"] * merged["MIN"] / 36).apply(trunc1)

    # Output clean name, projection, and minutes
    out = merged[["NAME_CLEAN", "Per36_Projection", "PerGame_Projection", "MIN"]].rename(columns={"NAME_CLEAN": "Player", "MIN": "Minutes_Per_Game"})
    out.to_csv(OUTPUT_CSV, index=False)
    print(f"✅ Wrote {len(out)} rows to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
