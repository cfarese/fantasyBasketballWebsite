import math
import time
from main import get_roster_for_scoring_period, league, get_scoring_period_date
from nba_utils import ESPN_TEAM_MAPPING, calculate_live_projection, get_current_scoring_period
from live_projection import get_minutes_left_by_team, add_live_projections_to_matchup
import json
from config import WEEKLY_MATCHUPS_JSON

# ===== CONFIGURATION =====
# Set to True to use owner names instead of team names (e.g., "Christian's Team" instead of "284 lbs")
USE_SAFE_TEAM_NAMES = True
# =========================


def get_week_from_scoring_period(scoring_period):
    """
    Convert scoring period to week number.
    Week 1: Periods 1-6 (6 days)
    Week 2+: Periods 7-13, 14-20, etc. (7 days each)
    """
    if scoring_period <= 6:
        return 1
    else:
        # After week 1 (6 days), each week is 7 days
        return ((scoring_period - 7) // 7) + 2


def get_scoring_periods_in_week(week_number):
    """
    Get all scoring periods in a given week.
    Week 1: [1, 2, 3, 4, 5, 6] (6 days)
    Week 2: [7, 8, 9, 10, 11, 12, 13] (7 days)
    Week 3: [14, 15, 16, 17, 18, 19, 20] (7 days)
    etc.
    """
    if week_number == 1:
        return list(range(1, 7))  # Days 1-6
    else:
        # Week 2 starts at day 7, week 3 at day 14, etc.
        start_period = 7 + (week_number - 2) * 7
        return list(range(start_period, start_period + 7))


def win_probability(score_a, proj_a, score_b, proj_b, alpha=10.5,
                    remaining_a=None, remaining_b=None):
    """
    Calculate win probability for team A vs team B.
    
    Uses a simple normal distribution model based on expected totals
    and remaining point variance.

    Args:
        score_a: Current score for team A
        proj_a: Live projection for team A (expected final total)
        score_b: Current score for team B
        proj_b: Live projection for team B (expected final total)
        alpha: Uncertainty scaling factor (default 3.5)
               Higher = more uncertainty, more even probabilities
               Lower = less uncertainty, more confident in projections
        remaining_a: Optional explicitly supplied remaining expected points for A
        remaining_b: Optional explicitly supplied remaining expected points for B

    Returns:
        Tuple of (prob_a_wins, prob_b_wins)
    """
    # If remaining expected points weren't supplied, derive from proj - score
    if remaining_a is None:
        remaining_a = max(0.0, proj_a - score_a)
    if remaining_b is None:
        remaining_b = max(0.0, proj_b - score_b)

    # Expected final scores
    EA = proj_a  # or equivalently: score_a + remaining_a
    EB = proj_b  # or equivalently: score_b + remaining_b
    
    # Standard deviation based on remaining points
    # More remaining points = more uncertainty
    remaining_total = remaining_a + remaining_b
    denom = alpha * math.sqrt(max(remaining_total, 1e-9))
    
    # Z-score: how many standard deviations is the difference
    z = (EA - EB) / denom
    
    # Standard normal CDF using error function
    # This gives us P(team A wins)
    p_a = 0.5 * (1.0 + math.erf(z / math.sqrt(2)))
    
    # Clamp to valid probability range
    p_a = max(0.0, min(1.0, p_a))
    
    return p_a, 1.0 - p_a


def calculate_weekly_totals(box_id, week_number):
    """
    Calculate total live projections for both teams across all games in a week.
    Returns detailed JSON of each roster on each night with points, live projection, and static projection.
    """
    start_time = time.time()

    # Enable debug mode
    DEBUG = True

    def debug_print(message):
        if DEBUG:
            print(f"DEBUG - {message}")

    # Get team info
    team1_obj = league.box_scores()[box_id].home_team
    team2_obj = league.box_scores()[box_id].away_team
    team1_id = team1_obj.team_id
    team2_id = team2_obj.team_id
    team1_name = team1_obj.team_name
    team2_name = team2_obj.team_name
    
    # Extract owner information
    team1_owner = ""
    if team1_obj.owners:
        owner = team1_obj.owners[0]
        first = owner.get('firstName', '')
        last = owner.get('lastName', '')
        team1_owner = f"{first} {last}".strip() or owner.get('displayName', 'Unknown')
    
    team2_owner = ""
    if team2_obj.owners:
        owner = team2_obj.owners[0]
        first = owner.get('firstName', '')
        last = owner.get('lastName', '')
        team2_owner = f"{first} {last}".strip() or owner.get('displayName', 'Unknown')
    
    # Get team records
    team1_record = f"{team1_obj.wins}-{team1_obj.losses}"
    if team1_obj.ties > 0:
        team1_record += f"-{team1_obj.ties}"
    
    team2_record = f"{team2_obj.wins}-{team2_obj.losses}"
    if team2_obj.ties > 0:
        team2_record += f"-{team2_obj.ties}"
    
    # Use safe names if enabled
    if USE_SAFE_TEAM_NAMES:
        team1_display_name = f"{team1_owner.split()[0]}'s Team" if team1_owner else team1_name
        team2_display_name = f"{team2_owner.split()[0]}'s Team" if team2_owner else team2_name
    else:
        team1_display_name = team1_name
        team2_display_name = team2_name

    debug_print(f"Processing matchup: {team1_name} (ID: {team1_id}) vs {team2_name} (ID: {team2_id})")

    # Initialize weekly totals
    team1_total_points = 0.0
    team2_total_points = 0.0
    team1_total_live_proj = 0.0
    team2_total_live_proj = 0.0

    # Create detailed JSON structure
    detailed_results = {
        'team1': {
            'name': team1_display_name,
            'id': team1_id,
            'owner': team1_owner,
            'record': team1_record,
            'days': {}
        },
        'team2': {
            'name': team2_display_name,
            'id': team2_id,
            'owner': team2_owner,
            'record': team2_record,
            'days': {}
        },
        'totals': {}
    }

    # Get all scoring periods in this week
    scoring_periods = get_scoring_periods_in_week(week_number)
    current_period = get_current_scoring_period()
    debug_print(f"Scoring periods in week {week_number}: {scoring_periods}")
    debug_print(f"Current scoring period: {current_period}")

    # Process each scoring period
    for period in scoring_periods:
        debug_print(f"\n=== Processing period {period} ===")
        period_date = get_scoring_period_date(period)
        debug_print(f"Period date: {period_date}")

        # Initialize data structures for this day
        detailed_results['team1']['days'][period] = {
            'date': str(period_date),
            'players': [],
            'roster': {
                'PG': "Empty Slot",
                'SG': "Empty Slot",
                'SF': "Empty Slot",
                'PF': "Empty Slot",
                'C': "Empty Slot",
                'G': "Empty Slot",
                'F': "Empty Slot",
                'UTL': ["Empty Slot", "Empty Slot", "Empty Slot"],
                'BENCH': [],
                'IR': []
            }
        }
        detailed_results['team2']['days'][period] = {
            'date': str(period_date),
            'players': [],
            'roster': {
                'PG': "Empty Slot",
                'SG': "Empty Slot",
                'SF': "Empty Slot",
                'PF': "Empty Slot",
                'C': "Empty Slot",
                'G': "Empty Slot",
                'F': "Empty Slot",
                'UTL': ["Empty Slot", "Empty Slot", "Empty Slot"],
                'BENCH': [],
                'IR': []
            }
        }

        # Get rosters
        debug_print(f"Fetching rosters for period {period}...")
        try:
            team1_roster = get_roster_for_scoring_period(team1_id, period)
            debug_print(f"Team 1 roster count: {len(team1_roster) if team1_roster else 0}")
            team2_roster = get_roster_for_scoring_period(team2_id, period)
            debug_print(f"Team 2 roster count: {len(team2_roster) if team2_roster else 0}")

            # Debug: inspect first player structure
            if team1_roster and len(team1_roster) > 0:
                debug_print(f"Team 1 first player keys: {list(team1_roster[0].keys())}")
                if 'playerPoolEntry' in team1_roster[0]:
                    debug_print(f"playerPoolEntry keys: {list(team1_roster[0]['playerPoolEntry'].keys())}")
                else:
                    debug_print("No playerPoolEntry found for first player!")
                    debug_print(f"Full first player data: {team1_roster[0]}")
            else:
                debug_print("Team 1 roster is empty!")

            # Process team1 roster data
            for i, player in enumerate(team1_roster):
                debug_print(f"Processing Team 1 Player {i + 1}/{len(team1_roster)}")

                # Check player structure
                if 'lineupSlotId' not in player:
                    debug_print(f"No lineupSlotId found for player: {player}")
                    continue

                # Track points
                if player['lineupSlotId'] not in [12, 13]:  # Skip bench and IR
                    points = player.get('points', 0)
                    team1_total_points += points
                    debug_print(f"Adding {points} points to team1_total_points")

                # Extract player name
                player_name = "Empty Slot"  # Default

                # Check if this is the format with 'playerPoolEntry'
                if 'playerPoolEntry' in player:
                    if 'player' in player['playerPoolEntry']:
                        player_name = player['playerPoolEntry']['player'].get('fullName', "Unknown Player")
                        debug_print(f"Found player name via playerPoolEntry: {player_name}")
                    else:
                        debug_print(f"No player key in playerPoolEntry: {player['playerPoolEntry'].keys()}")
                # Check if this is an alternative format with direct 'player' access
                elif 'player' in player:
                    player_name = player['player'].get('fullName', "Unknown Player")
                    debug_print(f"Found player name via direct player access: {player_name}")
                # Check for other formats
                else:
                    debug_print(f"Unable to find player name. Available keys: {player.keys()}")
                    # Try different ways to get the player name
                    for key in ['name', 'fullName', 'lastName', 'firstName', 'displayName']:
                        if key in player:
                            player_name = player[key]
                            debug_print(f"Found player name via key '{key}': {player_name}")
                            break

                # Map lineup slot ID to position
                lineup_slot = player['lineupSlotId']
                debug_print(f"Player {player_name} has lineup slot ID: {lineup_slot}")

                if lineup_slot == 0:
                    debug_print(f"Assigning {player_name} to PG")
                    detailed_results['team1']['days'][period]['roster']['PG'] = player_name
                elif lineup_slot == 1:
                    debug_print(f"Assigning {player_name} to SG")
                    detailed_results['team1']['days'][period]['roster']['SG'] = player_name
                elif lineup_slot == 2:
                    debug_print(f"Assigning {player_name} to SF")
                    detailed_results['team1']['days'][period]['roster']['SF'] = player_name
                elif lineup_slot == 3:
                    debug_print(f"Assigning {player_name} to PF")
                    detailed_results['team1']['days'][period]['roster']['PF'] = player_name
                elif lineup_slot == 4:
                    debug_print(f"Assigning {player_name} to C")
                    detailed_results['team1']['days'][period]['roster']['C'] = player_name
                elif lineup_slot == 5:
                    debug_print(f"Assigning {player_name} to G")
                    detailed_results['team1']['days'][period]['roster']['G'] = player_name
                elif lineup_slot == 6:
                    debug_print(f"Assigning {player_name} to F")
                    detailed_results['team1']['days'][period]['roster']['F'] = player_name
                elif lineup_slot in [7, 8, 9]:
                    utl_index = lineup_slot - 7
                    debug_print(f"Assigning {player_name} to UTL[{utl_index}]")
                    detailed_results['team1']['days'][period]['roster']['UTL'][utl_index] = player_name
                elif lineup_slot == 12:
                    debug_print(f"Adding {player_name} to BENCH")
                    # Extract injury status from player name
                    clean_name = player_name.split(' (')[0] if '(' in player_name else player_name
                    injury_status = player_name.split(' (')[1].rstrip(')') if '(' in player_name else None
                    detailed_results['team1']['days'][period]['roster']['BENCH'].append({
                        'name': clean_name,
                        'injury_status': injury_status
                    })
                elif lineup_slot == 13:
                    debug_print(f"Adding {player_name} to IR")
                    # Extract injury status from player name
                    clean_name = player_name.split(' (')[0] if '(' in player_name else player_name
                    injury_status = player_name.split(' (')[1].rstrip(')') if '(' in player_name else None
                    detailed_results['team1']['days'][period]['roster']['IR'].append({
                        'name': clean_name,
                        'injury_status': injury_status
                    })
                else:
                    debug_print(f"Unknown lineup slot ID: {lineup_slot} for player {player_name}")

            # Process team2 roster data (similar to team1)
            for i, player in enumerate(team2_roster):
                debug_print(f"Processing Team 2 Player {i + 1}/{len(team2_roster)}")

                if 'lineupSlotId' not in player:
                    debug_print(f"No lineupSlotId found for player: {player}")
                    continue

                if player['lineupSlotId'] not in [12, 13]:
                    points = player.get('points', 0)
                    team2_total_points += points
                    debug_print(f"Adding {points} points to team2_total_points")

                player_name = "Empty Slot"

                if 'playerPoolEntry' in player:
                    if 'player' in player['playerPoolEntry']:
                        player_name = player['playerPoolEntry']['player'].get('fullName', "Unknown Player")
                    else:
                        debug_print(f"No player key in playerPoolEntry: {player['playerPoolEntry'].keys()}")
                elif 'player' in player:
                    player_name = player['player'].get('fullName', "Unknown Player")
                else:
                    for key in ['name', 'fullName', 'lastName', 'firstName', 'displayName']:
                        if key in player:
                            player_name = player[key]
                            break

                lineup_slot = player['lineupSlotId']

                if lineup_slot == 0:
                    detailed_results['team2']['days'][period]['roster']['PG'] = player_name
                elif lineup_slot == 1:
                    detailed_results['team2']['days'][period]['roster']['SG'] = player_name
                elif lineup_slot == 2:
                    detailed_results['team2']['days'][period]['roster']['SF'] = player_name
                elif lineup_slot == 3:
                    detailed_results['team2']['days'][period]['roster']['PF'] = player_name
                elif lineup_slot == 4:
                    detailed_results['team2']['days'][period]['roster']['C'] = player_name
                elif lineup_slot == 5:
                    detailed_results['team2']['days'][period]['roster']['G'] = player_name
                elif lineup_slot == 6:
                    detailed_results['team2']['days'][period]['roster']['F'] = player_name
                elif lineup_slot in [7, 8, 9]:
                    utl_index = lineup_slot - 7
                    detailed_results['team2']['days'][period]['roster']['UTL'][utl_index] = player_name
                elif lineup_slot == 12:
                    # Extract injury status from player name
                    clean_name = player_name.split(' (')[0] if '(' in player_name else player_name
                    injury_status = player_name.split(' (')[1].rstrip(')') if '(' in player_name else None
                    detailed_results['team2']['days'][period]['roster']['BENCH'].append({
                        'name': clean_name,
                        'injury_status': injury_status
                    })
                elif lineup_slot == 13:
                    # Extract injury status from player name
                    clean_name = player_name.split(' (')[0] if '(' in player_name else player_name
                    injury_status = player_name.split(' (')[1].rstrip(')') if '(' in player_name else None
                    detailed_results['team2']['days'][period]['roster']['IR'].append({
                        'name': clean_name,
                        'injury_status': injury_status
                    })

        except Exception as e:
            debug_print(f"Error processing roster data for period {period}: {str(e)}")
            import traceback
            debug_print(traceback.format_exc())
            # Continue with live projections even if roster data fails

        # Get live projections from the matchup data
        debug_print("Fetching live projections...")
        try:
            matchup_data = add_live_projections_to_matchup(box_id, period)
            if matchup_data is None:
                debug_print(f"No matchup data for period {period}")
                continue

            debug_print(f"Matchup data rows: {len(matchup_data)}")
            if len(matchup_data) > 0:
                debug_print(f"First row: {matchup_data[0]}")

            # Skip the header row [0] and process player rows [1:]
            for row_index, row in enumerate(matchup_data[1:], 1):
                print(row)
                debug_print(f"Processing matchup row {row_index}/{len(matchup_data) - 1}")
                position = row[0]
                
                # Extract data
                team2_name_raw = row[1]
                team1_name_raw = row[8]
                
                # Extract player names and injury status
                team1_player_name = team1_name_raw.split(' (')[0] if '(' in team1_name_raw else team1_name_raw
                team2_player_name = team2_name_raw.split(' (')[0] if '(' in team2_name_raw else team2_name_raw
                
                # Extract and normalize injury status (convert DAY_TO_DAY to DTD for consistency)
                team1_injury_raw = team1_name_raw.split(' (')[1].rstrip(')') if '(' in team1_name_raw else None
                team2_injury_raw = team2_name_raw.split(' (')[1].rstrip(')') if '(' in team2_name_raw else None
                
                # Normalize injury status
                team1_injury = team1_injury_raw.replace('_', '-') if team1_injury_raw else None
                team2_injury = team2_injury_raw.replace('_', '-') if team2_injury_raw else None
                
                # If this is a BENCH or IR row, update the roster data with injury status
                if position in ["BENCH", "IR"]:
                    debug_print(f"Processing {position} row: {team1_player_name} vs {team2_player_name}")
                    
                    # Update team1 BENCH/IR with injury status
                    for i, player in enumerate(detailed_results['team1']['days'][period]['roster'][position]):
                        if isinstance(player, dict) and player['name'] == team1_player_name:
                            detailed_results['team1']['days'][period]['roster'][position][i]['injury_status'] = team1_injury
                            debug_print(f"Updated team1 {position} player {team1_player_name} with injury status: {team1_injury}")
                            break
                    
                    # Update team2 BENCH/IR with injury status
                    for i, player in enumerate(detailed_results['team2']['days'][period]['roster'][position]):
                        if isinstance(player, dict) and player['name'] == team2_player_name:
                            detailed_results['team2']['days'][period]['roster'][position][i]['injury_status'] = team2_injury
                            debug_print(f"Updated team2 {position} player {team2_player_name} with injury status: {team2_injury}")
                            break
                    
                    continue

                team2_static_proj = float(row[2]) if isinstance(row[2], (int, float)) or (
                        isinstance(row[2], str) and row[2].strip() and row[2] != 'None') else 0.0
                team2_live_proj = float(row[3]) if isinstance(row[3], (int, float)) or (
                        isinstance(row[3], str) and row[3].strip() and row[3] != 'None') else 0.0
                team2_points = float(row[4]) if isinstance(row[4], (int, float)) or (
                        isinstance(row[4], str) and row[4].strip() and row[4] != 'None') else 0.0
                team1_points = float(row[5]) if isinstance(row[5], (int, float)) or (
                        isinstance(row[5], str) and row[5].strip() and row[5] != 'None') else 0.0
                team1_live_proj = float(row[6]) if isinstance(row[6], (int, float)) or (
                        isinstance(row[6], str) and row[6].strip() and row[6] != 'None') else 0.0
                team1_static_proj = float(row[7]) if isinstance(row[7], (int, float)) or (
                        isinstance(row[7], str) and row[7].strip() and row[7] != 'None') else 0.0

                debug_print(f"Position: {position}")
                debug_print(f"Team1: {team1_name_raw}, Points: {team1_points}, Live Proj: {team1_live_proj}")
                debug_print(f"Team2: {team2_name_raw}, Points: {team2_points}, Live Proj: {team2_live_proj}")

                # Add to running totals using proper logic:
                # - Use live projection if points > 0 (game has started)
                # - Use static projection if points == 0 (game hasn't started)
                # Team 1
                if team1_points > 0:
                    team1_total_live_proj += team1_live_proj
                    debug_print(f"Team1: Adding live projection {team1_live_proj} (game started)")
                else:
                    team1_total_live_proj += team1_static_proj
                    debug_print(f"Team1: Adding static projection {team1_static_proj} (game not started)")
                
                # Team 2
                if team2_points > 0:
                    team2_total_live_proj += team2_live_proj
                    debug_print(f"Team2: Adding live projection {team2_live_proj} (game started)")
                else:
                    team2_total_live_proj += team2_static_proj
                    debug_print(f"Team2: Adding static projection {team2_static_proj} (game not started)")

                # Add to detailed results
                detailed_results['team1']['days'][period]['players'].append({
                    'name': team1_player_name,
                    'position': position,
                    'points': team1_points,
                    'static_projection': team1_static_proj,
                    'live_projection': team1_live_proj,
                    'injury_status': team1_injury
                })
                detailed_results['team2']['days'][period]['players'].append({
                    'name': team2_player_name,
                    'position': position,
                    'points': team2_points,
                    'static_projection': team2_static_proj,
                    'live_projection': team2_live_proj,
                    'injury_status': team2_injury
                })

                # Since we have player data from matchup, let's try to use it to populate roster
                # (this could be a backup approach if the get_roster_for_scoring_period fails)

                # Check if the names in matchup data match with roster positions
                # If so, we might be able to infer the positions from the matchup data
                print(team1_player_name, team2_player_name)
                if team1_player_name and team1_player_name not in ["Empty Slot", "Unknown Player"]:
                    debug_print(f"Trying to place {team1_player_name} in Team 1 roster based on position {position}")
                    if position == "PG":
                        detailed_results['team1']['days'][period]['roster']['PG'] = team1_player_name
                    elif position == "SG":
                        detailed_results['team1']['days'][period]['roster']['SG'] = team1_player_name
                    elif position == "SF":
                        detailed_results['team1']['days'][period]['roster']['SF'] = team1_player_name
                    elif position == "PF":
                        detailed_results['team1']['days'][period]['roster']['PF'] = team1_player_name
                    elif position == "C":
                        detailed_results['team1']['days'][period]['roster']['C'] = team1_player_name
                    elif position == "G":
                        detailed_results['team1']['days'][period]['roster']['G'] = team1_player_name
                    elif position == "F":
                        detailed_results['team1']['days'][period]['roster']['F'] = team1_player_name
                    elif position == "UTL":
                        # Find the first empty UTL slot
                        for i in range(3):
                            if detailed_results['team1']['days'][period]['roster']['UTL'][i] == "Empty Slot":
                                detailed_results['team1']['days'][period]['roster']['UTL'][i] = team1_player_name
                                break

                if team2_player_name and team2_player_name not in ["Empty Slot", "Unknown Player"]:
                    debug_print(f"Trying to place {team2_player_name} in Team 2 roster based on position {position}")
                    if position == "PG":
                        detailed_results['team2']['days'][period]['roster']['PG'] = team2_player_name
                    elif position == "SG":
                        detailed_results['team2']['days'][period]['roster']['SG'] = team2_player_name
                    elif position == "SF":
                        detailed_results['team2']['days'][period]['roster']['SF'] = team2_player_name
                    elif position == "PF":
                        detailed_results['team2']['days'][period]['roster']['PF'] = team2_player_name
                    elif position == "C":
                        detailed_results['team2']['days'][period]['roster']['C'] = team2_player_name
                    elif position == "G":
                        detailed_results['team2']['days'][period]['roster']['G'] = team2_player_name
                    elif position == "F":
                        detailed_results['team2']['days'][period]['roster']['F'] = team2_player_name
                    elif position == "UTL":
                        # Find the first empty UTL slot
                        for i in range(3):
                            if detailed_results['team2']['days'][period]['roster']['UTL'][i] == "Empty Slot":
                                detailed_results['team2']['days'][period]['roster']['UTL'][i] = team2_player_name
                                break

        except Exception as e:
            debug_print(f"Error processing live projections for period {period}: {str(e)}")
            import traceback
            debug_print(traceback.format_exc())

    # Calculate win probabilities
    # Compute remaining expected points (live projection minus already scored)
    remaining_team1 = max(0.0, team1_total_live_proj - team1_total_points)
    remaining_team2 = max(0.0, team2_total_live_proj - team2_total_points)

    prob_team1, prob_team2 = win_probability(
        team1_total_points,
        team1_total_live_proj,
        team2_total_points,
        team2_total_live_proj,
        remaining_a=remaining_team1,
        remaining_b=remaining_team2
    )

    # Add totals to results
    detailed_results['totals'] = {
        'team1': {
            'points': team1_total_points,
            'live_projection': team1_total_live_proj,
            'win_probability': prob_team1 * 100
        },
        'team2': {
            'points': team2_total_points,
            'live_projection': team2_total_live_proj,
            'win_probability': prob_team2 * 100
        }
    }

    end_time = time.time()
    execution_time = end_time - start_time

    # Print matchup results
    print(f"\n{'=' * 50}")
    print(f"MATCHUP #{box_id + 1}: {team1_name} vs {team2_name} (WEEK {week_number})")
    print(f"{'=' * 50}")
    print(f"{team1_name} Points: {team1_total_points}")
    print(f"{team2_name} Points: {team2_total_points}")
    print(f"{team1_name} Live Projection: {team1_total_live_proj:.1f}")
    print(f"{team2_name} Live Projection: {team2_total_live_proj:.1f}")
    print(f"")
    print(f"{team1_name} Win Probability: {prob_team1 * 100:.1f}%")
    print(f"{team2_name} Win Probability: {prob_team2 * 100:.1f}%")
    print(f"{'=' * 50}\n")

    return detailed_results



if __name__ == "__main__":
    # Determine current week
    current_period = get_current_scoring_period()
    current_week = get_week_from_scoring_period(current_period)

    # Calculate weekly totals for all matchups
    start_time = time.time()

    all_matchups = {}

    for box_id in range(4):
        try:
            print(f"Processing matchup #{box_id + 1}...")
            matchup_results = calculate_weekly_totals(box_id, current_week)
            all_matchups[f'matchup_{box_id}'] = matchup_results
        except Exception as e:
            print(f"Error processing matchup #{box_id + 1}: {str(e)}")

    end_time = time.time()
    print(f"Total execution time for all matchups: {end_time - start_time:.2f} seconds")

    print(json.dumps(all_matchups, ensure_ascii=False))

    with open(WEEKLY_MATCHUPS_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_matchups, f, ensure_ascii=False, indent=4)
    print(f"Weekly matchups data saved to {WEEKLY_MATCHUPS_JSON}")