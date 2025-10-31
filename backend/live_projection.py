# live_projection.py
from nba_api.live.nba.endpoints import scoreboard
import pandas as pd
from main import matchup_comparison, league
from tabulate import tabulate
from nba_utils import ESPN_TEAM_MAPPING, _clock_to_minutes, calculate_live_projection

BOXSCORE_ID = 3
SCORINGPERIOD_ID = 6


def minutes_left_today(period_len=12):
    """Get minutes left in all current NBA games."""
    sb = scoreboard.ScoreBoard()
    data = sb.get_dict()
    games = data.get("scoreboard", {}).get("games", [])

    rows = []
    for g in games:
        game_id = g.get("gameId")
        status = int(g.get("gameStatus", 0))
        status_text = g.get("gameStatusText", "")
        current_period = int(g.get("period", 0) or 0)
        regulation_periods = int(g.get("regulationPeriods", 4) or 4)
        clock_str = g.get("gameClock")

        home_abbr = g.get("homeTeam", {}).get("teamTricode", "")
        away_abbr = g.get("awayTeam", {}).get("teamTricode", "")

        if status == 3:
            minutes_left = 0.0
        elif status == 1:
            minutes_left = regulation_periods * period_len
        else:
            rem_this_period = _clock_to_minutes(clock_str)
            if current_period <= regulation_periods:
                full_periods_left = max(0, regulation_periods - current_period)
                minutes_left = rem_this_period + full_periods_left * period_len
            else:
                minutes_left = rem_this_period

        rows.append({
            "game_id": game_id,
            "matchup": f"{away_abbr} @ {home_abbr}",
            "status": status_text,
            "period": current_period,
            "clock_raw": clock_str,
            "minutes_left": round(minutes_left, 2),
        })

    return pd.DataFrame(rows)


def get_minutes_left_by_team():
    """
    Returns a dict mapping team tricode -> minutes_left in their current game.
    """
    df = minutes_left_today()
    team_minutes = {}

    print("DEBUG - Minutes left by team:")
    for _, row in df.iterrows():
        matchup = row['matchup']  # Format: "AWAY @ HOME"
        minutes_left = row['minutes_left']

        # Parse away and home teams
        if '@' in matchup:
            parts = matchup.split('@')
            away_team = parts[0].strip()
            home_team = parts[1].strip()

            team_minutes[away_team] = minutes_left
            team_minutes[home_team] = minutes_left

            print(f"  {away_team}: {minutes_left:.2f} minutes")
            print(f"  {home_team}: {minutes_left:.2f} minutes")

    return team_minutes


def get_player_team_tricode(player_name):
    """Get the NBA team tricode for a player by looking them up in the league."""
    if not player_name or player_name.strip() == "":
        return None

    # Clean up the name for matching
    cleaned_name = player_name.strip()

    # Create a direct mapping for team abbreviations to tricodes
    TEAM_ABBR_TO_TRICODE = {
        "ATL": "ATL", "BOS": "BOS", "NOP": "NOP", "CHI": "CHI", "CLE": "CLE",
        "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GSW": "GSW", "HOU": "HOU",
        "IND": "IND", "LAC": "LAC", "LAL": "LAL", "MIA": "MIA", "MIL": "MIL",
        "MIN": "MIN", "BKN": "BKN", "NYK": "NYK", "ORL": "ORL", "PHI": "PHI",
        "PHO": "PHX", "POR": "POR", "SAC": "SAC", "SAS": "SAS", "OKC": "OKC",
        "UTA": "UTA", "WAS": "WAS", "TOR": "TOR", "MEM": "MEM", "CHA": "CHA",
        "PHL": "PHI"  # Add any special cases/typos
    }

    print(f"Searching for team tricode for: '{cleaned_name}'")

    for team in league.teams:
        for player in team.roster:
            # Try exact name match
            if player.name == cleaned_name:
                # Get team abbreviation from player
                pro_team = player.proTeam
                print(f"  Found match: {player.name} -> {pro_team} -> {TEAM_ABBR_TO_TRICODE.get(pro_team)}")
                return TEAM_ABBR_TO_TRICODE.get(pro_team)

            # Try case-insensitive match
            if player.name.lower() == cleaned_name.lower():
                pro_team = player.proTeam
                print(
                    f"  Found case-insensitive match: {player.name} -> {pro_team} -> {TEAM_ABBR_TO_TRICODE.get(pro_team)}")
                return TEAM_ABBR_TO_TRICODE.get(pro_team)

            # Try substring match
            player_parts = player.name.lower().split()
            name_parts = cleaned_name.lower().split()
            if len(player_parts) >= 2 and len(name_parts) >= 2:
                if player_parts[0] == name_parts[0] and player_parts[-1] == name_parts[-1]:
                    pro_team = player.proTeam
                    print(f"  Found partial match: {player.name} -> {pro_team} -> {TEAM_ABBR_TO_TRICODE.get(pro_team)}")
                    return TEAM_ABBR_TO_TRICODE.get(pro_team)

    print(f"  No team found for {cleaned_name}")
    return None


def add_live_projections_to_matchup(box_id, scoring_period):
    """Gets matchup comparison data and adds live projection columns."""
    # Get the base matchup data
    matchup_data = matchup_comparison(box_id, scoring_period)

    if matchup_data is None:
        print("Could not get matchup data")
        return None

    # (no debug print) matchup_data is consumed below

    # Get minutes left by team
    team_minutes = get_minutes_left_by_team()

    # matchup_data format: [header_row, player_rows...]
    # Each player row: [Position, Team2Name, Projection, Points, Points, Projection, Team1Name]
    header = matchup_data[0]
    player_rows = matchup_data[1:]

    # Add live projection columns to header
    new_header = [
        header[0],  # Position
        header[1],  # Team2 Name
        header[2],  # Team2 Projection
        "Live Proj",  # NEW: Team2 Live Projection
        header[3],  # Team2 Points
        header[4],  # Team1 Points
        "Live Proj",  # NEW: Team1 Live Projection
        header[5],  # Team1 Projection
        header[6]  # Team1 Name
    ]

    # Standard position order
    standard_positions = ["PG", "SG", "SF", "PF", "C", "G", "F"]

    # Create a dictionary to track which positions we've seen
    seen_positions = {pos: False for pos in standard_positions}
    seen_utl = 0  # Track how many UTL positions we've seen

    # Start with an empty new rows list
    new_rows = []

    # First, add all standard positions in order, with empty slots if needed
    for pos in standard_positions:
        found_row = None
        for row in player_rows:
            if row[0] == pos:
                found_row = row
                break

        if found_row:
            # Position exists in data, process it
            team2_name = found_row[1]
            team2_proj = float(found_row[2]) if found_row[2] is not None and found_row[2] != '' else 0.0
            team2_points = float(found_row[3]) if found_row[3] is not None and found_row[3] != '' else 0.0
            team1_points = float(found_row[4]) if found_row[4] is not None and found_row[4] != '' else 0.0
            team1_proj = float(found_row[5]) if found_row[5] is not None and found_row[5] != '' else 0.0
            team1_name = found_row[6]

            # Calculate live projections
            team2_live_proj = 0.0
            if team2_name != "Empty Slot":
                team2_tricode = get_player_team_tricode(team2_name.split('(')[0].strip())
                team2_in_scoreboard = team2_tricode in team_minutes if team2_tricode else False
                team2_minutes_left = team_minutes.get(team2_tricode, 0.0) if team2_tricode else 0.0
                if team2_points > 0 or team2_proj > 0:
                    print(
                        f"DEBUG - {team2_name}: points={team2_points}, proj={team2_proj}, tricode={team2_tricode}, in_scoreboard={team2_in_scoreboard}, mins_left={team2_minutes_left}")
                team2_live_proj = calculate_live_projection(team2_points, team2_proj, team2_minutes_left,
                                                            scoring_period, team2_in_scoreboard)

            team1_live_proj = 0.0
            if team1_name != "Empty Slot":
                team1_tricode = get_player_team_tricode(team1_name.split('(')[0].strip())
                team1_in_scoreboard = team1_tricode in team_minutes if team1_tricode else False
                team1_minutes_left = team_minutes.get(team1_tricode, 0.0) if team1_tricode else 0.0
                if team1_points > 0 or team1_proj > 0:
                    print(
                        f"DEBUG - {team1_name}: points={team1_points}, proj={team1_proj}, tricode={team1_tricode}, in_scoreboard={team1_in_scoreboard}, mins_left={team1_minutes_left}")
                team1_live_proj = calculate_live_projection(team1_points, team1_proj, team1_minutes_left,
                                                            scoring_period, team1_in_scoreboard)

            new_rows.append([
                pos,
                team2_name,
                team2_proj,
                round(team2_live_proj, 1),
                team2_points,
                team1_points,
                round(team1_live_proj, 1),
                team1_proj,
                team1_name
            ])
            seen_positions[pos] = True
        else:
            # Position is missing, add empty slot
            new_rows.append([
                pos,
                "Empty Slot",
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                "Empty Slot"
            ])

    # Process UTL positions
    utl_rows = []
    for row in player_rows:
        if row[0] == "UTL":
            team2_name = row[1]
            team2_proj = float(row[2]) if row[2] is not None and row[2] != '' else 0.0
            team2_points = float(row[3]) if row[3] is not None and row[3] != '' else 0.0
            team1_points = float(row[4]) if row[4] is not None and row[4] != '' else 0.0
            team1_proj = float(row[5]) if row[5] is not None and row[5] != '' else 0.0
            team1_name = row[6]

            # Calculate live projections
            team2_live_proj = 0.0
            if team2_name != "Empty Slot":
                team2_tricode = get_player_team_tricode(team2_name.split('(')[0].strip())
                team2_in_scoreboard = team2_tricode in team_minutes if team2_tricode else False
                team2_minutes_left = team_minutes.get(team2_tricode, 0.0) if team2_tricode else 0.0
                if team2_points > 0 or team2_proj > 0:
                    print(
                        f"DEBUG - {team2_name}: points={team2_points}, proj={team2_proj}, tricode={team2_tricode}, in_scoreboard={team2_in_scoreboard}, mins_left={team2_minutes_left}")
                team2_live_proj = calculate_live_projection(team2_points, team2_proj, team2_minutes_left,
                                                            scoring_period, team2_in_scoreboard)

            team1_live_proj = 0.0
            if team1_name != "Empty Slot":
                team1_tricode = get_player_team_tricode(team1_name.split('(')[0].strip())
                team1_in_scoreboard = team1_tricode in team_minutes if team1_tricode else False
                team1_minutes_left = team_minutes.get(team1_tricode, 0.0) if team1_tricode else 0.0
                if team1_points > 0 or team1_proj > 0:
                    print(
                        f"DEBUG - {team1_name}: points={team1_points}, proj={team1_proj}, tricode={team1_tricode}, in_scoreboard={team1_in_scoreboard}, mins_left={team1_minutes_left}")
                team1_live_proj = calculate_live_projection(team1_points, team1_proj, team1_minutes_left,
                                                            scoring_period, team1_in_scoreboard)

            utl_rows.append([
                "UTL",
                team2_name,
                team2_proj,
                round(team2_live_proj, 1),
                team2_points,
                team1_points,
                round(team1_live_proj, 1),
                team1_proj,
                team1_name
            ])
            seen_utl += 1

    # Ensure we have exactly 3 UTL positions
    for i in range(seen_utl, 3):
        utl_rows.append([
            "UTL",
            "Empty Slot",
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            "Empty Slot"
        ])

    # Add UTL rows to main rows
    new_rows.extend(utl_rows)

    # Add bench and IR positions as they are
    for row in player_rows:
        if row[0] in ["BENCH", "IR"]:
            # Normalize values
            team2_name = row[1]
            team2_proj = float(row[2]) if row[2] is not None and row[2] != '' else 0.0
            team2_points = float(row[3]) if row[3] is not None and row[3] != '' else 0.0
            team1_points = float(row[4]) if row[4] is not None and row[4] != '' else 0.0
            team1_proj = float(row[5]) if row[5] is not None and row[5] != '' else 0.0
            team1_name = row[6]

            # Calculate live projections for bench/IR similar to other rows so columns align
            team2_live_proj = 0.0
            if team2_name != "Empty Slot":
                team2_tricode = get_player_team_tricode(team2_name.split('(')[0].strip())
                team2_in_scoreboard = team2_tricode in team_minutes if team2_tricode else False
                team2_minutes_left = team_minutes.get(team2_tricode, 0.0) if team2_tricode else 0.0
                team2_live_proj = calculate_live_projection(team2_points, team2_proj, team2_minutes_left,
                                                            scoring_period, team2_in_scoreboard)

            team1_live_proj = 0.0
            if team1_name != "Empty Slot":
                team1_tricode = get_player_team_tricode(team1_name.split('(')[0].strip())
                team1_in_scoreboard = team1_tricode in team_minutes if team1_tricode else False
                team1_minutes_left = team_minutes.get(team1_tricode, 0.0) if team1_tricode else 0.0
                team1_live_proj = calculate_live_projection(team1_points, team1_proj, team1_minutes_left,
                                                            scoring_period, team1_in_scoreboard)

            new_rows.append([
                row[0],
                team2_name,
                team2_proj,
                round(team2_live_proj, 1),
                team2_points,
                team1_points,
                round(team1_live_proj, 1),
                team1_proj,
                team1_name
            ])

    return [new_header] + new_rows


if __name__ == "__main__":
    # Show minutes left in all games
    df = minutes_left_today()
    print("\n=== Minutes Left in Today's Games ===")
    print(df.to_string(index=False))
    print()

    # Get matchup with live projections
    live_matchup = add_live_projections_to_matchup(BOXSCORE_ID, SCORINGPERIOD_ID)

    if live_matchup:
        print("\n=== Matchup with Live Projections ===")
        table = tabulate(
            live_matchup[1:],
            headers=live_matchup[0],
            tablefmt="grid"
        )
        print(table)