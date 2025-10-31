import sys
import os
from dotenv import load_dotenv
from config import ESPN_API_PATH, WEIGHTED_PER36_CSV, SEASON_START_DATE
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.insert(0, ESPN_API_PATH)
from espn_api.basketball import League
import requests
from tabulate import tabulate
import pandas as pd
import subprocess
import datetime
from nba_api.stats.endpoints import scoreboardv2
import unicodedata

# Initialize the league
league = League(
    league_id=int(os.getenv('ESPN_LEAGUE_ID')),
    year=int(os.getenv('ESPN_YEAR')),
    swid=os.getenv('ESPN_SWID'),
    espn_s2=os.getenv('ESPN_S2')
)

subprocess.run([sys.executable, "combined_projector.py"], check=True)

def get_roster_for_scoring_period(team_id, scoring_period):
    league_id = os.getenv('ESPN_LEAGUE_ID')
    year = os.getenv('ESPN_YEAR')
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{year}/segments/0/leagues/{league_id}"

    cookies = {
        'swid': os.getenv('ESPN_SWID'),
        'espn_s2': os.getenv('ESPN_S2')
    }

    params = {
        'forTeamId': team_id,
        'scoringPeriodId': scoring_period,
        'view': 'mRoster'
    }

    response = requests.get(url, cookies=cookies, params=params)
    if response.status_code == 200:
        data = response.json()

        # Find the team's roster
        for team in data.get('teams', []):
            if team['id'] == team_id:
                roster = team.get('roster', {})
                entries = roster.get('entries', [])

                result = []
                for entry in entries:
                    player_data = entry.get('playerPoolEntry', {}).get('player', {})
                    player_name = player_data.get('fullName', 'Unknown Player')
                    
                    # Get the player's pro team
                    pro_team_id = player_data.get('proTeamId', 0)
                    # Map pro team ID to team name/tricode
                    # We'll get this from defaultPositionId and proTeamId
                    # ESPN uses proTeamId, but we need the team name
                    # The API might provide it in another field

                    # Find stats for this specific scoring period
                    points = 0
                    player_stats = player_data.get('stats', [])
                    for stat in player_stats:
                        # Look for stats with statSplitTypeId = 5 (specific game stats)
                        if stat.get('statSplitTypeId') == 5 and stat.get('scoringPeriodId') == scoring_period:
                            points = stat.get('appliedTotal', 0)
                            break

                    # Get the lineup position
                    lineup_slot = entry.get('lineupSlotId', 0)

                    result.append({
                        'name': player_name,
                        'points': points,
                        'lineupSlotId': lineup_slot,
                        'proTeamId': pro_team_id
                    })

                # Sort by lineup position
                result.sort(key=lambda x: x['lineupSlotId'])
                return result

    return []

def get_scoring_period_date(scoring_period):
    """
    Calculate the date for a given scoring period.
    Scoring period 1 starts on October 21, 2025.
    Each scoring period is one day.
    """
    start_date = datetime.date(*SEASON_START_DATE)
    # Scoring period 1 = Oct 21, scoring period 2 = Oct 22, etc.
    period_date = start_date + datetime.timedelta(days=(scoring_period - 1))
    return period_date

def get_teams_playing_for_period(scoring_period):
    """
    Get all teams playing during a given scoring period (one day).
    Returns a set of team tricodes.
    """
    # NBA team ID to tricode mapping
    nba_team_id_to_tricode = {
        1610612737: 'ATL', 1610612738: 'BOS', 1610612739: 'CLE', 1610612740: 'NOP',
        1610612741: 'CHI', 1610612742: 'DAL', 1610612743: 'DEN', 1610612744: 'GSW',
        1610612745: 'HOU', 1610612746: 'LAC', 1610612747: 'LAL', 1610612748: 'MIA',
        1610612749: 'MIL', 1610612750: 'MIN', 1610612751: 'BKN', 1610612752: 'NYK',
        1610612753: 'ORL', 1610612754: 'IND', 1610612755: 'PHI', 1610612756: 'PHX',
        1610612757: 'POR', 1610612758: 'SAC', 1610612759: 'SAS', 1610612760: 'OKC',
        1610612761: 'TOR', 1610612762: 'UTA', 1610612763: 'MEM', 1610612764: 'WAS',
        1610612765: 'DET', 1610612766: 'CHA'
    }
    
    teams_playing = set()
    period_date = get_scoring_period_date(scoring_period)
    #print(f"\n=== DEBUG: get_teams_playing_for_period ===")
    #print(f"Scoring period: {scoring_period}")
    #print(f"Period date: {period_date}")
    
    # Check games on this specific day only
    date_str = period_date.strftime('%m/%d/%Y')
    #print(f"\nChecking games for: {date_str}")
    
    try:
        # Use scoreboardv2 for any date (past, present, or future)
        scoreboard_data = scoreboardv2.ScoreboardV2(game_date=date_str)
        games = scoreboard_data.get_dict()['resultSets'][0]['rowSet']
        #print(f"  Found {len(games)} games")
        
        for game in games:
            # Extract team IDs from game data (indices 6 and 7 are home/away team IDs)
            home_team_id = game[6]
            away_team_id = game[7]
            
            # Convert team IDs to tricodes
            home_tricode = nba_team_id_to_tricode.get(home_team_id, None)
            away_tricode = nba_team_id_to_tricode.get(away_team_id, None)
            
            #print(f"    Game: {home_tricode} (ID: {home_team_id}) vs {away_tricode} (ID: {away_team_id})")
            
            if home_tricode:
                teams_playing.add(home_tricode)
            if away_tricode:
                teams_playing.add(away_tricode)
    except Exception as e:
        # If the API fails for a future date or other reason, continue
        print(f"  ERROR: Could not fetch games for {date_str}: {e}")
        pass
    
    #print(f"\nTotal teams playing on this date: {teams_playing}")
    return teams_playing

def get_nba_team_tricode(pro_team_name):
    """
    Map ESPN pro team names to NBA team tricodes.
    """
    team_mapping = {
        'Atlanta Hawks': 'ATL',
        'Boston Celtics': 'BOS',
        'Brooklyn Nets': 'BKN',
        'Charlotte Hornets': 'CHA',
        'Chicago Bulls': 'CHI',
        'Cleveland Cavaliers': 'CLE',
        'Dallas Mavericks': 'DAL',
        'Denver Nuggets': 'DEN',
        'Detroit Pistons': 'DET',
        'Golden State Warriors': 'GSW',
        'Houston Rockets': 'HOU',
        'Indiana Pacers': 'IND',
        'LA Clippers': 'LAC',
        'Los Angeles Clippers': 'LAC',
        'Los Angeles Lakers': 'LAL',
        'LA Lakers': 'LAL',
        'Memphis Grizzlies': 'MEM',
        'Miami Heat': 'MIA',
        'Milwaukee Bucks': 'MIL',
        'Minnesota Timberwolves': 'MIN',
        'New Orleans Pelicans': 'NOP',
        'New York Knicks': 'NYK',
        'Oklahoma City Thunder': 'OKC',
        'Orlando Magic': 'ORL',
        'Philadelphia 76ers': 'PHI',
        'Phoenix Suns': 'PHX',
        'Portland Trail Blazers': 'POR',
        'Sacramento Kings': 'SAC',
        'San Antonio Spurs': 'SAS',
        'Toronto Raptors': 'TOR',
        'Utah Jazz': 'UTA',
        'Washington Wizards': 'WAS'
    }
    return team_mapping.get(pro_team_name, None)

def standardize_name(name):
    # Remove accents and convert to ASCII
    return unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII').lower()


def matchup_comparison(box_id, scoringperiod):
    team1_id = league.box_scores()[box_id].home_team.team_id
    team2_id = league.box_scores()[box_id].away_team.team_id
    team1_roster = get_roster_for_scoring_period(team1_id, scoringperiod)
    team2_roster = get_roster_for_scoring_period(team2_id, scoringperiod)

    # Set position names for all players
    for player in team1_roster + team2_roster:
        match player["lineupSlotId"]:
            case 0:
                player.update({"Position": "PG"})
            case 1:
                player.update({"Position": "SG"})
            case 2:
                player.update({"Position": "SF"})
            case 3:
                player.update({"Position": "PF"})
            case 4:
                player.update({"Position": "C"})
            case 5:
                player.update({"Position": "G"})
            case 6:
                player.update({"Position": "F"})
            case 11:
                player.update({"Position": "UTL"})
            case 12:
                player.update({"Position": "BENCH"})
            case 13:
                player.update({"Position": "IR"})

    # Load projections
    try:
        df = pd.read_csv(WEIGHTED_PER36_CSV)
        #print("Using projections from weighted_per36_projection.csv")
    except FileNotFoundError:
        #print("Projection file not found!")
        return None

    # Create standardized names in projection dataframe for better matching
    df['Player_Standardized'] = df['Player'].apply(standardize_name)

    # Get injury information
    injuredListName = []
    injuredListInjury = []
    for leagueteam in league.teams:
        if leagueteam.team_id == team1_id or leagueteam.team_id == team2_id:
            for player in leagueteam.roster:
                if player.injuryStatus != "ACTIVE":
                    injuredListName.append(player.name)
                    injuredListInjury.append(player.injuryStatus)

    injury_dict = dict(zip(injuredListName, injuredListInjury))

    # Get team names
    team1_name = ""
    team2_name = ""
    for leagueteam in league.teams:
        if leagueteam.team_id == team1_id:
            team1_name = leagueteam.team_name
        elif leagueteam.team_id == team2_id:
            team2_name = leagueteam.team_name

    # Get teams playing during this scoring period
    teams_playing = get_teams_playing_for_period(scoringperiod)
    #print(f"Teams playing in scoring period {scoringperiod}: {teams_playing}")
    
    # ESPN pro team ID to NBA tricode mapping
    espn_team_mapping = {
        1: 'ATL', 2: 'BOS', 3: 'NOP', 4: 'CHI', 5: 'CLE', 6: 'DAL', 7: 'DEN',
        8: 'DET', 9: 'GSW', 10: 'HOU', 11: 'IND', 12: 'LAC', 13: 'LAL',
        14: 'MIA', 15: 'MIL', 16: 'MIN', 17: 'BKN', 18: 'NYK', 19: 'ORL',
        20: 'PHI', 21: 'PHX', 22: 'POR', 23: 'SAC', 24: 'SAS', 25: 'OKC',
        26: 'UTA', 27: 'WAS', 28: 'TOR', 29: 'MEM', 30: 'CHA'
    }
    
    # Assign projections to all players
    #print(f"\n=== DEBUG: Assigning Projections ===")
    for idx, player in enumerate(team1_roster + team2_roster):
        #print(f"\n--- Player {idx + 1}: {player['name']} ---")
        player_name_std = standardize_name(player["name"])
        #print(f"  Standardized name: {player_name_std}")
        
        # Get player's NBA team
        pro_team_id = player.get('proTeamId', 0)
        #print(f"  ESPN proTeamId: {pro_team_id}")
        player_team_tricode = espn_team_mapping.get(pro_team_id, None)
        #print(f"  Mapped to NBA tricode: {player_team_tricode}")
        
        # Check if player's team is playing during this scoring period
        is_playing = player_team_tricode and player_team_tricode in teams_playing
        #print(f"  Is team in teams_playing? {player_team_tricode in teams_playing if player_team_tricode else 'N/A (no tricode)'}")
        #print(f"  is_playing: {is_playing}")

        # Check if player is OUT - set projection to 0 ONLY if they haven't already played (points == 0)
        if player["name"] in injury_dict and injury_dict[player["name"]] == "OUT":
            if player.get("points", 0) == 0:  # Only zero out projection if game hasn't been played yet
                #print(f"  -> Setting projection to 0 (Player is OUT and hasn't played)")
                player["Projection"] = 0
                continue
            else:
                #print(f"  -> Player is OUT now but already played (has {player['points']} points), keeping projection")
                pass  # Continue to assign projection normally
        
        # If player's team is not playing, set projection to 0 ONLY if they haven't already played
        if not is_playing:
            if player.get("points", 0) == 0:  # Only zero out if game hasn't been played yet
                #print(f"  -> Setting projection to 0 (Team not playing)")
                player["Projection"] = 0
                continue
            else:
                #print(f"  -> Team not playing now but player already played (has {player['points']} points), keeping projection")
                pass  # Continue to assign projection normally

        # Find player in projections
        player_row = df[df['Player_Standardized'] == player_name_std]
        #print(f"  Found in projections CSV? {not player_row.empty}")
        if not player_row.empty:
            projection_value = player_row['PerGame_Projection'].values[0]
            #print(f"  Projection value from CSV: {projection_value}")
            player["Projection"] = projection_value
        else:
            #print(f"  -> Setting projection to 0 (Not found in CSV)")
            player["Projection"] = 0

    # Build position-indexed lists for both teams so we can align rows by Position
    def build_pos_map(roster):
        pos_map = {}
        for p in roster:
            pos = p.get('Position', 'NONE')
            pos_map.setdefault(pos, []).append(p)
        # sort each position list by lineupSlotId to keep original ordering
        for lst in pos_map.values():
            lst.sort(key=lambda x: x.get('lineupSlotId', 0))
        return pos_map

    team1_by_pos = build_pos_map(team1_roster)
    team2_by_pos = build_pos_map(team2_roster)

    def fmt_team1(player):
        if not player:
            return [0, 0, 'Empty Slot']
        name = player.get('name', 'Empty Slot')
        if name in injury_dict:
            name = f"{name} ({injury_dict[name]})"
        return [player.get('points', 0), player.get('Projection', 0), name]

    def fmt_team2(player, pos):
        if not player:
            return [pos, 'Empty Slot', 0, 0]
        name = player.get('name', 'Empty Slot')
        if name in injury_dict:
            name = f"{name} ({injury_dict[name]})"
        return [player.get('Position', pos), name, player.get('Projection', 0), player.get('points', 0)]

    headerlist = ["Position", team2_name, "Projection", "Points", "Points", "Projection", team1_name]
    bigarr = []

    # Standard positions in order
    standard_positions = ["PG", "SG", "SF", "PF", "C", "G", "F"]

    # For each standard position, take the next player from each team's position list (or None)
    for pos in standard_positions:
        t2_player = team2_by_pos.get(pos, []).pop(0) if team2_by_pos.get(pos) else None
        t1_player = team1_by_pos.get(pos, []).pop(0) if team1_by_pos.get(pos) else None

        arr2 = fmt_team2(t2_player, pos)
        arr1 = fmt_team1(t1_player)
        bigarr.append(arr2 + arr1)

    # UTL slots: up to 3
    for _ in range(3):
        t2_player = team2_by_pos.get('UTL', []).pop(0) if team2_by_pos.get('UTL') else None
        t1_player = team1_by_pos.get('UTL', []).pop(0) if team1_by_pos.get('UTL') else None
        arr2 = fmt_team2(t2_player, 'UTL')
        arr1 = fmt_team1(t1_player)
        bigarr.append(arr2 + arr1)

    # BENCH and IR: pair remaining players by position-bucket order so bench lists line up
    def append_pairs(pos_name):
        t2_list = team2_by_pos.get(pos_name, [])
        t1_list = team1_by_pos.get(pos_name, [])
        max_len = max(len(t1_list), len(t2_list))
        for i in range(max_len):
            t2_player = t2_list[i] if i < len(t2_list) else None
            t1_player = t1_list[i] if i < len(t1_list) else None
            arr2 = fmt_team2(t2_player, pos_name)
            arr1 = fmt_team1(t1_player)
            bigarr.append(arr2 + arr1)

    append_pairs('BENCH')
    append_pairs('IR')

    table = tabulate(
        bigarr,
        headers=["Position", team2_name, "Projection", "Points", "Points", "Projection", team1_name],
        tablefmt="grid"
    )
    #print(table)
    print(f"Scoring Period: {scoringperiod}")

    return [headerlist] + bigarr


# Use it with:
#get_matchup_comparison(league, 5)
# Or for a specific scoring period:
# get_matchup_comparison(league, 5)

team1_id = league.box_scores()[3].home_team.team_id
team2_id = league.box_scores()[3].away_team.team_id

print(team1_id, team2_id)
matchup_comparison(3, 5)
