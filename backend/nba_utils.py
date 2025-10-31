# nba_utils.py
import re
import datetime
from zoneinfo import ZoneInfo
from config import SEASON_START_DATE

# ESPN pro team ID to NBA tricode mapping
ESPN_TEAM_MAPPING = {
    1: 'ATL', 2: 'BOS', 3: 'NOP', 4: 'CHI', 5: 'CLE', 6: 'DAL', 7: 'DEN',
    8: 'DET', 9: 'GSW', 10: 'HOU', 11: 'IND', 12: 'LAC', 13: 'LAL',
    14: 'MIA', 15: 'MIL', 16: 'MIN', 17: 'BKN', 18: 'NYK', 19: 'ORL',
    20: 'PHI', 21: 'PHX', 22: 'POR', 23: 'SAC', 24: 'SAS', 25: 'OKC',
    26: 'UTA', 27: 'WAS', 28: 'TOR', 29: 'MEM', 30: 'CHA'
}

def get_current_scoring_period():
    """
    Calculate the current scoring period based on today's date (EST timezone).
    Scoring period 1 = October 21, 2025.
    """
    start_date = datetime.date(*SEASON_START_DATE)
    now = datetime.datetime.now(ZoneInfo('America/New_York'))
    today = now.date()
    days_since_start = (today - start_date).days
    current_period = days_since_start + 1

    # If it's the next calendar day but before noon EST, show the previous scoring period.
    # This keeps the website displaying the prior day's matchup until 12:00 EST
    # on the following day.
    try:
        noon = datetime.time(12, 0)
        if now.time() < noon and days_since_start >= 1:
            return max(1, current_period - 1)
    except Exception:
        # In case of any unexpected datetime issues, fall back to date-only behavior
        pass

    return max(1, current_period)  # Ensure at least period 1

def _clock_to_minutes(clock_str: str) -> float:
    """Accepts 'MM:SS' or 'PT08M34.00S'. Returns minutes as float."""
    if not clock_str or not isinstance(clock_str, str):
        return 0.0
    s = clock_str.strip()

    if s.startswith("PT"):
        m = re.search(r"PT(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?", s)
        if m:
            mm = float(m.group(1) or 0)
            ss = float(m.group(2) or 0)
            return mm + ss / 60.0

    if ":" in s:
        mm, ss = s.split(":")[:2]
        return int(mm) + int(ss) / 60.0

    return 0.0


def calculate_live_projection(current_points, projected_points, minutes_left, scoringperiod_ID, team_in_scoreboard=True):
    """
    Calculate live projection based on current points, projected points, and minutes left.
    """
    # If we couldn't determine the player's team
    if scoringperiod_ID < get_current_scoring_period():
        return current_points
    elif get_current_scoring_period() > scoringperiod_ID:
        return projected_points

    if minutes_left == 0 and not team_in_scoreboard:
        # If they've already scored points, use those
        if current_points > 0:
            return current_points
        # If they have a projection but no points yet, use static projection
        elif projected_points > 0:
            return projected_points
        # Otherwise, just return 0
        else:
            return 0

    # For games that have finished
    if team_in_scoreboard and minutes_left <= 0:
        return current_points

    # For games that haven't started
    if team_in_scoreboard and minutes_left >= 48:
        return projected_points

    # For games in progress
    total_minutes = 48.0
    ratio = minutes_left / total_minutes
    remaining_points = (0.75 * projected_points * ratio) + (0.25 * current_points * ratio)

    return current_points + remaining_points