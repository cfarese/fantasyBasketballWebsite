"""
Configuration file for all file paths and constants used across the fantasy basketball project.
"""
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
PROJECTIONS_DIR = BASE_DIR / "projections"

# ESPN API custom path (if needed)
ESPN_API_PATH = "/Users/christian/Desktop/PyCharmProjects/espn-api"

# CSV Files
FANTASY_PROJECTIONS_CSV = PROJECTIONS_DIR / "fantasy_projections_output.csv"
NBA_PER_GAME_CSV = PROJECTIONS_DIR / "nba_per_game_2025_26.csv"
WEIGHTED_PER36_CSV = PROJECTIONS_DIR / "weighted_per36_projection.csv"
CURRENT_SEASON_STATS_CSV = PROJECTIONS_DIR / "current_season_stats.csv"
SPS_CSV = PROJECTIONS_DIR / "sps.csv"
SPS_1_CSV = PROJECTIONS_DIR / "sps_1.csv"
LIVE_PROJECTIONS_CSV = PROJECTIONS_DIR / "live_projections.csv"

# JSON Files
WEEKLY_MATCHUPS_JSON = PROJECTIONS_DIR / "weekly_matchups.json"

# Text Files
FILE1_TXT = PROJECTIONS_DIR / "file1.txt"
FILE2_TXT = PROJECTIONS_DIR / "file2.txt"

# Projection weights
PROJECTION_WEIGHT = 7/8
SPS_WEIGHT = 1/8

# NBA Season Configuration
SEASON_START_DATE = (2025, 10, 21)  # (year, month, day)
SEASON_YEAR = 2026

# Convert Path objects to strings for backward compatibility
def get_path_str(path):
    """Convert Path object to string"""
    return str(path)
