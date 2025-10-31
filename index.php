<?php
// Load the JSON file
$json_file = 'projections/weekly_matchups.json';
$json_data = file_get_contents($json_file);
$matchups = json_decode($json_data, true);

if (!$matchups) {
    die("Error loading or parsing JSON file");
}

// Function to format a percentage
function formatPercentage($value) {
    return number_format($value, 1) . '%';
}

// Function to get day number within the week (resets each week)
function getDayOfWeek($scoring_period) {
    // Week 1: periods 1-6 (days 1-6)
    // Week 2+: periods 7-13, 14-20, etc. (days 1-7)
    if ($scoring_period <= 6) {
        return $scoring_period; // Week 1: days 1-6
    } else {
        // Week 2+: Calculate relative day number (1-7)
        $adjusted = $scoring_period - 7; // Subtract week 1
        return ($adjusted % 7) + 1;
    }
}

// Function to format injury status tag
function getInjuryTag($injury_status, $position = 'right') {
    if (!$injury_status) return '';
    
    $status_upper = strtoupper($injury_status);
    $class = 'injury-tag';
    
    // Map status to appropriate CSS class
    if ($status_upper === 'OUT' || $status_upper === 'O') {
        $class .= ' out';
        $display = 'O';
    } elseif ($status_upper === 'DAY-TO-DAY' || $status_upper === 'DTD' || $status_upper === 'DAY') {
        $class .= ' dtd';
        $display = 'DTD';
    } elseif ($status_upper === 'QUESTIONABLE' || $status_upper === 'Q') {
        $class .= ' questionable';
        $display = 'Q';
    } elseif ($status_upper === 'PROBABLE' || $status_upper === 'P') {
        $class .= ' probable';
        $display = 'P';
    } elseif ($status_upper === 'DOUBTFUL' || $status_upper === 'D') {
        $class .= ' questionable';
        $display = 'D';
    } else {
        // Default for any other status
        $display = substr($status_upper, 0, 3);
    }
    
    // Return just the tag - positioning will be handled by placement in HTML
    return '<span class="' . $class . '">' . $display . '</span>';
}

// Function to abbreviate long player names (first name to initial if > 18 chars)
function abbreviateName($name) {
    // Only abbreviate if name is long
    if (strlen($name) <= 18) {
        return $name;
    }
    
    // Split into parts
    $parts = explode(' ', $name);
    
    // If there are at least 2 parts, abbreviate first name
    if (count($parts) >= 2) {
        $parts[0] = substr($parts[0], 0, 1) . '.';
        return implode(' ', $parts);
    }
    
    return $name;
}

// Function to get team color based on win probability (smooth gradient)
function getTeamColor($probability) {
    // More distinct colors - big difference at 50/50, then gradual changes
    
    if ($probability >= 90) return "#0d7a2c"; // Very dark green
    if ($probability >= 80) return "#1a9240"; // Dark green
    if ($probability >= 70) return "#28a745"; // Green
    if ($probability >= 60) return "#3d9e50"; // Medium green (darker)
    if ($probability >= 55) return "#4d9e5a"; // Medium-light green (darker)
    if ($probability >= 50) return "#5da864"; // Light green (darker) - CLEAR WINNER
    if ($probability >= 45) return "#d9941f"; // Medium orange (darker) - CLEAR LOSER
    if ($probability >= 40) return "#e68a00"; // Orange (darker)
    if ($probability >= 30) return "#ff8020"; // Strong orange
    if ($probability >= 20) return "#ff6600"; // Dark orange
    if ($probability >= 10) return "#e65500"; // Very dark orange
    return "#cc0000"; // Dark red for very low probability
}

// Get scoring periods from the JSON data
$scoring_periods = [];
foreach ($matchups as $matchup_id => $matchup) {
    foreach ($matchup['team1']['days'] as $day => $day_data) {
        $scoring_periods[$day] = $day_data['date'];
    }
    break; // Just need one matchup to get the dates
}

// Find closest scoring period to today (using EST timezone)
date_default_timezone_set('America/New_York');
$today = date('Y-m-d');
$closest_period = 1; // Default to first day
$min_diff = PHP_INT_MAX;
foreach ($scoring_periods as $period => $date) {
    $diff = abs(strtotime($date) - strtotime($today));
    if ($diff < $min_diff) {
        $min_diff = $diff;
        $closest_period = $period;
    }
}

// Selected days for each matchup (from query parameters or default to closest period)
$selected_days = [];
foreach ($matchups as $matchup_id => $matchup) {
    $day_param = 'day_' . $matchup_id;
    $selected_days[$matchup_id] = isset($_GET[$day_param]) ? $_GET[$day_param] : $closest_period;
}

// Function to generate player tables HTML for a matchup
function generatePlayerTablesHTML($team1, $team2, $selected_day) {
    $html = '<div class="row team-names-row">
        <div class="col-md-6 text-center mb-3">
            <h4>' . htmlspecialchars($team2['name']) . '</h4>
        </div>
        <div class="col-md-6 text-center mb-3">
            <h4>' . htmlspecialchars($team1['name']) . '</h4>
        </div>
    </div>';

    $html .= '<div class="row player-details p-3">';

    // Away Team (team2) on Left
    $html .= '<div class="col-md-6">
        <table class="table table-sm centered-layout">
            <thead>
                <tr>
                    <th style="width: 15%">POS</th>
                    <th style="width: 35%">Player</th>
                    <th style="width: 25%">Projection</th>
                    <th style="width: 25%">Points</th>
                </tr>
            </thead>
            <tbody>';

    $team2_day_total = 0;
    $team2_day_proj = 0;

    // Check if selected day data exists
    if (isset($team2['days'][$selected_day])) {
        // Get roster data
        $roster = $team2['days'][$selected_day]['roster'] ?? null;

        // Standard positions to display
        $positions = [
                'PG' => 'PG',
                'SG' => 'SG',
                'SF' => 'SF',
                'PF' => 'PF',
                'C' => 'C',
                'G' => 'G',
                'F' => 'F'
        ];

        // Process standard positions
        foreach ($positions as $pos_key => $pos_label) {
            $player_name = isset($roster[$pos_key]) ? $roster[$pos_key] : "Empty Slot";

            // Find player's stats if they exist in the players array
            $player_points = "";
            $player_projection = "";
            $projDisplay = "";
            $injury_tag = "";

            if ($player_name != "Empty Slot") {
                foreach ($team2['days'][$selected_day]['players'] as $player) {
                    if ($player['name'] == $player_name) {
                        $player_points = $player['points'];
                        $team2_day_total += $player_points;
                        
                        // Get injury status tag (positioned on right for team2)
                        $injury_tag = isset($player['injury_status']) ? getInjuryTag($player['injury_status'], 'right') : '';

                        if ($player['points'] > 0) { // Game has started or finished
                            $projDisplay = number_format($player['live_projection'], 1);
                            // Always show static projection in parentheses when game has started
                            $projDisplay .= ' <span class="static-proj">(' . number_format($player['static_projection'], 1) . ')</span>';
                            $team2_day_proj += $player['live_projection'];
                        } else if ($player['static_projection'] > 0) { // Game hasn't started yet (but player is scheduled)
                            $projDisplay = number_format($player['static_projection'], 1);
                            $team2_day_proj += $player['static_projection'];
                            $player_points = "-"; // Show dash for scheduled but not yet played
                        } else { // Player not playing today
                            $projDisplay = "0.0";
                            $player_points = "0";
                        }
                        break;
                    }
                }
            }

            $html .= '<tr>';
            $html .= '<td><span class="position-badge">' . $pos_label . '</span></td>';
            $html .= '<td class="player-name"><span class="player-text">' . htmlspecialchars(abbreviateName($player_name)) . '</span>' . $injury_tag . '</td>';
            $html .= '<td>' . $projDisplay . '</td>';
            $html .= '<td class="points-col">' . $player_points . '</td>';
            $html .= '</tr>';
        }

        // Process UTL positions (up to 3)
        $utl_slots = $roster['UTL'] ?? ["Empty Slot", "Empty Slot", "Empty Slot"];
        for ($i = 0; $i < count($utl_slots); $i++) {
            $player_name = $utl_slots[$i];

            // Find player's stats
            $player_points = "";
            $player_projection = "";
            $projDisplay = "";
            $injury_tag = "";

            if ($player_name != "Empty Slot") {
                foreach ($team2['days'][$selected_day]['players'] as $player) {
                    if ($player['name'] == $player_name) {
                        $player_points = $player['points'];
                        $team2_day_total += $player_points;
                        
                        // Get injury status tag (positioned on right for team2)
                        $injury_tag = isset($player['injury_status']) ? getInjuryTag($player['injury_status'], 'right') : '';

                        if ($player['points'] > 0) { // Game has started or finished
                            $projDisplay = number_format($player['live_projection'], 1);
                            // Always show static projection in parentheses when game has started
                            $projDisplay .= ' <span class="static-proj">(' . number_format($player['static_projection'], 1) . ')</span>';
                            $team2_day_proj += $player['live_projection'];
                        } else if ($player['static_projection'] > 0) { // Game hasn't started yet (but player is scheduled)
                            $projDisplay = number_format($player['static_projection'], 1);
                            $team2_day_proj += $player['static_projection'];
                            $player_points = "-"; // Show dash for scheduled but not yet played
                        } else { // Player not playing today
                            $projDisplay = "0.0";
                            $player_points = "0";
                        }
                        break;
                    }
                }
            }

            $html .= '<tr>';
            $html .= '<td><span class="position-badge">UTL</span></td>';
            $html .= '<td class="player-name"><span class="player-text">' . htmlspecialchars(abbreviateName($player_name)) . '</span>' . $injury_tag . '</td>';
            $html .= '<td>' . $projDisplay . '</td>';
            $html .= '<td class="points-col">' . $player_points . '</td>';
            $html .= '</tr>';
        }

        // Process BENCH players
        $bench_players = $roster['BENCH'] ?? [];
        foreach ($bench_players as $player_data) {
            // Handle both old format (string) and new format (array with name and injury_status)
            if (is_array($player_data)) {
                $player_name = $player_data['name'];
                $injury_status = $player_data['injury_status'] ?? null;
            } else {
                $player_name = $player_data;
                $injury_status = null;
            }
            $injury_tag = getInjuryTag($injury_status);
            
            $html .= '<tr class="bench-row">';
            $html .= '<td><span class="position-badge bench-badge">BN</span></td>';
            $html .= '<td class="player-name"><span class="player-text">' . htmlspecialchars(abbreviateName($player_name)) . '</span>' . $injury_tag . '</td>';
            $html .= '<td></td>'; // Blank projection for bench
            $html .= '<td></td>'; // Blank points for bench
            $html .= '</tr>';
        }

        // Process IR players
        $ir_players = $roster['IR'] ?? [];
        foreach ($ir_players as $player_data) {
            // Handle both old format (string) and new format (array with name and injury_status)
            if (is_array($player_data)) {
                $player_name = $player_data['name'];
                $injury_status = $player_data['injury_status'] ?? null;
            } else {
                $player_name = $player_data;
                $injury_status = null;
            }
            $injury_tag = getInjuryTag($injury_status);
            
            $html .= '<tr class="ir-row">';
            $html .= '<td><span class="position-badge ir-badge">IR</span></td>';
            $html .= '<td class="player-name"><span class="player-text">' . htmlspecialchars(abbreviateName($player_name)) . '</span>' . $injury_tag . '</td>';
            $html .= '<td></td>'; // Blank projection for IR
            $html .= '<td></td>'; // Blank points for IR
            $html .= '</tr>';
        }

    } else {
        $html .= '<tr><td colspan="4" class="text-center">No data for this day</td></tr>';
    }

    $html .= '<tr class="table-secondary day-total-row">
                <td><strong>Day Total</strong></td>
                <td></td>
                <td><strong>' . number_format($team2_day_proj, 1) . '</strong></td>
                <td><strong>' . $team2_day_total . '</strong></td>
            </tr>
            </tbody>
        </table>
        </div>';

    // Home Team (team1) on Right - COMPLETELY REVERSED order
    $html .= '<div class="col-md-6">
        <table class="table table-sm centered-layout">
            <thead>
                <tr>
                    <th style="width: 25%">Points</th>
                    <th style="width: 25%">Projection</th>
                    <th style="width: 35%;">Player</th>
                    <th style="width: 15%">POS</th>
                </tr>
            </thead>
            <tbody>';

    $team1_day_total = 0;
    $team1_day_proj = 0;

    // Check if selected day data exists
    if (isset($team1['days'][$selected_day])) {
        // Get roster data
        $roster = $team1['days'][$selected_day]['roster'] ?? null;

        // Standard positions to display
        $positions = [
                'PG' => 'PG',
                'SG' => 'SG',
                'SF' => 'SF',
                'PF' => 'PF',
                'C' => 'C',
                'G' => 'G',
                'F' => 'F'
        ];

        // Process standard positions
        foreach ($positions as $pos_key => $pos_label) {
            $player_name = isset($roster[$pos_key]) ? $roster[$pos_key] : "Empty Slot";

            // Find player's stats if they exist in the players array
            $player_points = "";
            $player_projection = "";
            $projDisplay = "";
            $injury_tag = "";

            if ($player_name != "Empty Slot") {
                foreach ($team1['days'][$selected_day]['players'] as $player) {
                    if ($player['name'] == $player_name) {
                        $player_points = $player['points'];
                        $team1_day_total += $player_points;
                        
                        // Get injury status tag (positioned on left for team1)
                        $injury_tag = isset($player['injury_status']) ? getInjuryTag($player['injury_status'], 'left') : '';

                        if ($player['points'] > 0) { // Game has started or finished
                            $projDisplay = number_format($player['live_projection'], 1);
                            // Always show static projection in parentheses when game has started
                            $projDisplay .= ' <span class="static-proj">(' . number_format($player['static_projection'], 1) . ')</span>';
                            $team1_day_proj += $player['live_projection'];
                        } else if ($player['static_projection'] > 0) { // Game hasn't started yet (but player is scheduled)
                            $projDisplay = number_format($player['static_projection'], 1);
                            $team1_day_proj += $player['static_projection'];
                            $player_points = "-"; // Show dash for scheduled but not yet played
                        } else { // Player not playing today
                            $projDisplay = "0.0";
                            $player_points = "0";
                        }
                        break;
                    }
                }
            }

            $html .= '<tr>';
            $html .= '<td class="points-col">' . $player_points . '</td>'; // FIRST: Points
            $html .= '<td>' . $projDisplay . '</td>'; // SECOND: Projection
            $html .= '<td class="player-name"><span class="player-text">' . htmlspecialchars(abbreviateName($player_name)) . '</span>' . $injury_tag . '</td>'; // THIRD: Player
            $html .= '<td><span class="position-badge">' . $pos_label . '</span></td>'; // FOURTH: Position
            $html .= '</tr>';
        }

        // Process UTL positions (up to 3)
        $utl_slots = $roster['UTL'] ?? ["Empty Slot", "Empty Slot", "Empty Slot"];
        for ($i = 0; $i < count($utl_slots); $i++) {
            $player_name = $utl_slots[$i];

            // Find player's stats
            $player_points = "";
            $player_projection = "";
            $projDisplay = "";
            $injury_tag = "";

            if ($player_name != "Empty Slot") {
                foreach ($team1['days'][$selected_day]['players'] as $player) {
                    if ($player['name'] == $player_name) {
                        $player_points = $player['points'];
                        $team1_day_total += $player_points;
                        
                        // Get injury status tag (positioned on left for team1)
                        $injury_tag = isset($player['injury_status']) ? getInjuryTag($player['injury_status'], 'left') : '';

                        if ($player['points'] > 0) { // Game has started or finished
                            $projDisplay = number_format($player['live_projection'], 1);
                            // Always show static projection in parentheses when game has started
                            $projDisplay .= ' <span class="static-proj">(' . number_format($player['static_projection'], 1) . ')</span>';
                            $team1_day_proj += $player['live_projection'];
                        } else if ($player['static_projection'] > 0) { // Game hasn't started yet (but player is scheduled)
                            $projDisplay = number_format($player['static_projection'], 1);
                            $team1_day_proj += $player['static_projection'];
                            $player_points = "-"; // Show dash for scheduled but not yet played
                        } else { // Player not playing today
                            $projDisplay = "0.0";
                            $player_points = "0";
                        }
                        break;
                    }
                }
            }

            $html .= '<tr>';
            $html .= '<td class="points-col">' . $player_points . '</td>'; // FIRST: Points
            $html .= '<td>' . $projDisplay . '</td>'; // SECOND: Projection
            $html .= '<td class="player-name"><span class="player-text">' . htmlspecialchars(abbreviateName($player_name)) . '</span>' . $injury_tag . '</td>'; // THIRD: Player
            $html .= '<td><span class="position-badge">UTL</span></td>'; // FOURTH: Position
            $html .= '</tr>';
        }

        // Process BENCH players
        $bench_players = $roster['BENCH'] ?? [];
        foreach ($bench_players as $player_data) {
            // Handle both old format (string) and new format (array with name and injury_status)
            if (is_array($player_data)) {
                $player_name = $player_data['name'];
                $injury_status = $player_data['injury_status'] ?? null;
            } else {
                $player_name = $player_data;
                $injury_status = null;
            }
            $injury_tag = getInjuryTag($injury_status);
            
            $html .= '<tr class="bench-row">';
            $html .= '<td></td>'; // Blank points for bench
            $html .= '<td></td>'; // Blank projection for bench
            $html .= '<td class="player-name"><span class="player-text">' . htmlspecialchars(abbreviateName($player_name)) . '</span>' . $injury_tag . '</td>';
            $html .= '<td><span class="position-badge bench-badge">BN</span></td>';
            $html .= '</tr>';
        }

        // Process IR players
        $ir_players = $roster['IR'] ?? [];
        foreach ($ir_players as $player_data) {
            // Handle both old format (string) and new format (array with name and injury_status)
            if (is_array($player_data)) {
                $player_name = $player_data['name'];
                $injury_status = $player_data['injury_status'] ?? null;
            } else {
                $player_name = $player_data;
                $injury_status = null;
            }
            $injury_tag = getInjuryTag($injury_status);
            
            $html .= '<tr class="ir-row">';
            $html .= '<td></td>'; // Blank points for IR
            $html .= '<td></td>'; // Blank projection for IR
            $html .= '<td class="player-name"><span class="player-text">' . htmlspecialchars(abbreviateName($player_name)) . '</span>' . $injury_tag . '</td>';
            $html .= '<td><span class="position-badge ir-badge">IR</span></td>';
            $html .= '</tr>';
        }

    } else {
        $html .= '<tr><td colspan="4" class="text-center">No data for this day</td></tr>';
    }

    $html .= '<tr class="table-secondary day-total-row">
                <td><strong>' . $team1_day_total . '</strong></td>
                <td><strong>' . number_format($team1_day_proj, 1) . '</strong></td>
                <td></td>
                <td><strong>Day Total</strong></td>
            </tr>
            </tbody>
        </table>
        </div>';

    $html .= '</div>'; // End of player-details row

    return $html;
}

// Handle AJAX request to update matchup data for a specific day
if (isset($_GET['ajax']) && isset($_GET['matchupId']) && isset($_GET['day'])) {
    $matchup_id = $_GET['matchupId'];
    $selected_day = $_GET['day'];

    if (isset($matchups[$matchup_id])) {
        $matchup = $matchups[$matchup_id];
        $team1 = $matchup['team1'];
        $team2 = $matchup['team2'];

        $html = generatePlayerTablesHTML($team1, $team2, $selected_day);

        header('Content-Type: application/json');
        echo json_encode(['html' => $html]);
        exit;
    }
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fantasy Basketball Weekly Matchups</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            padding: 20px;
            background-color: #0a002a; /* Much darker blue */
            color: #ffffff;
        }
        .container {
            max-width: 1200px;
        }
        .matchup-card {
            margin-bottom: 30px;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            background-color: #10004d; /* Dark blue for cards */
            cursor: pointer;
        }
        .matchup-header {
            background-color: #07002a; /* Very dark blue for headers */
            color: white;
            padding: 15px;
            font-weight: bold;
        }
        .team-section {
            padding: 15px;
            border-bottom: 1px solid #1e0082;
        }
        .team-name {
            font-size: 1.25rem;
            font-weight: bold;
        }
        .team-record {
            font-size: 0.85rem;
            font-weight: normal;
            opacity: 0.8;
            margin-left: 0.5rem;
        }
        .team-stats {
            margin-top: 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .team-stats .projection {
            font-size: 0.9rem;
            color: #aaa;
        }
        .team-stats .points {
            font-size: 2rem;
            font-weight: bold;
        }
        .probability-bar {
            height: 30px;
            margin: 15px 0;
            border-radius: 5px;
            overflow: hidden;
        }
        .progress-segment {
            height: 100%;
            float: left;
            text-align: center;
            color: white;
            line-height: 30px;
        }
        .position-badge {
            background-color: #1a0066;
            color: white;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 0.8rem;
        }
        .static-proj {
            font-size: 0.8rem;
            color: #a8a8ff; /* Lighter blue for secondary text */
        }
        .centered-layout td {
            text-align: center;
        }
        .player-name {
            text-align: left;
        }
        .injury-tag {
            display: inline-block;
            margin-left: 5px;
            padding: 2px 6px;
            font-size: 0.75rem;
            font-weight: bold;
            border-radius: 3px;
            background-color: #ff6b6b;
            color: white;
        }
        .injury-tag.out {
            background-color: #dc3545;
        }
        .injury-tag.dtd {
            background-color: #ffc107;
            color: #000;
        }
        .injury-tag.questionable {
            background-color: #ff9800;
        }
        .injury-tag.probable {
            background-color: #17a2b8;
        }
        .points-col {
            font-weight: bold;
        }
        .table {
            color: #ffffff;
            margin-bottom: 0;
        }
        .table-secondary {
            background-color: #1a0066 !important;
            color: white;
        }
        .table>:not(caption)>*>* {
            background-color: transparent;
            border-color: #1e0082;
        }
        .form-select, .form-control {
            background-color: #1a0066;
            border-color: #1e0082;
            color: white;
        }
        .form-select:focus, .form-control:focus {
            background-color: #1a0066;
            border-color: #2d0099;
            color: white;
            box-shadow: 0 0 0 0.25rem rgba(72, 36, 214, 0.25);
        }
        .form-select option {
            background-color: #1a0066;
            color: white;
        }
        label {
            color: white;
        }
        h1, h4 {
            color: #ffffff;
        }
        .toggle-button {
            background-color: #1a0066;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 5px;
            margin: 10px 0;
            cursor: pointer;
            font-weight: bold;
        }
        .toggle-button:hover {
            background-color: #2d0099;
        }
        .hidden {
            display: none;
        }
        .matchup-day-select {
            background-color: #1a0066;
            border: 1px solid #2d0099;
            color: white;
            border-radius: 5px;
            padding: 5px;
            margin-bottom: 15px;
            display: inline-block;
        }
        .details-content {
            transition: all 0.3s ease;
        }
        .matchup-clickable {
            cursor: pointer;
        }
        
        /* ========== DESKTOP ALIGNMENT (≥992px) ========== */
        @media (min-width: 992px) {
            /* Enable flexbox for player name cells to reorder injury tags */
            .player-details .player-name {
                display: flex !important;
                align-items: center !important;
                gap: 5px !important;
            }
            
            /* TEAM2 (Left Side / Away Team) - Desktop-Left */
            .player-details > div:first-child table th:nth-child(1),
            .player-details > div:first-child table td:nth-child(1) {
                text-align: center !important; /* POS - center */
            }
            
            .player-details > div:first-child table th:nth-child(2),
            .player-details > div:first-child table td:nth-child(2) {
                text-align: left !important; /* Player - left */
            }
            
            /* TEAM2: Injury tag on RIGHT (player name first, then tag) */
            .player-details > div:first-child .player-name .player-text {
                order: 1;
            }
            .player-details > div:first-child .player-name .injury-tag {
                order: 2;
            }
            
            .player-details > div:first-child table th:nth-child(3),
            .player-details > div:first-child table td:nth-child(3) {
                text-align: right !important; /* Projection - right */
            }
            
            .player-details > div:first-child table th:nth-child(4),
            .player-details > div:first-child table td:nth-child(4) {
                text-align: right !important; /* Points - right */
            }
            
            /* TEAM1 (Right Side / Home Team) - Desktop-Right */
            .player-details > div:last-child table th:nth-child(1),
            .player-details > div:last-child table td:nth-child(1) {
                text-align: left !important; /* Points - left */
            }
            
            .player-details > div:last-child table th:nth-child(2),
            .player-details > div:last-child table td:nth-child(2) {
                text-align: left !important; /* Projection - left */
            }
            
            .player-details > div:last-child table th:nth-child(3),
            .player-details > div:last-child table td:nth-child(3) {
                text-align: right !important; /* Player - right */
                justify-content: flex-end !important;
            }
            
            /* TEAM1: Injury tag on LEFT (tag first, then player name) */
            .player-details > div:last-child .player-name .player-text {
                order: 2;
            }
            .player-details > div:last-child .player-name .injury-tag {
                order: 1;
            }
            
            .player-details > div:last-child table th:nth-child(4),
            .player-details > div:last-child table td:nth-child(4) {
                text-align: center !important; /* POS - center */
            }
        }
        
        /* On mobile, only the header area is clickable, not the whole section */
        @media (max-width: 991px) {
            .team-section {
                cursor: default;
            }
            
            .matchup-header-click {
                cursor: pointer;
            }
        }
        .chevron-icon {
            transition: transform 0.3s ease;
            display: inline-block;
            margin-left: 10px;
        }
        .chevron-down {
            transform: rotate(0deg);
        }
        .chevron-up {
            transform: rotate(-180deg);
        }
        /* New styles for bench and IR players */
        .bench-row, .ir-row {
            background-color: #0d0035 !important; /* Slightly darker background for bench/IR */
            opacity: 0.8;
        }
        .bench-badge {
            background-color: #1a0080;
        }
        .ir-badge {
            background-color: #800020;
        }
        /* Player name handling for long names */
        .player-name {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 100%;
        }
        
        /* Responsive stacking for narrow screens */
        @media (max-width: 991px) {
            /* Stack tables vertically when screen is narrow */
            .player-details > div[class*="col-md-6"] {
                flex: 0 0 100%;
                max-width: 100%;
                margin-bottom: 20px;
            }
            
            /* Add separator between stacked tables */
            .player-details > div[class*="col-md-6"]:first-child {
                border-bottom: 2px solid #4824d6;
                padding-bottom: 20px;
            }
        }
        
        /* Even narrower screens - make table more compact */
        @media (max-width: 768px) {
            .table th, .table td {
                padding: 0.3rem;
                font-size: 0.85rem;
            }
            
            .position-badge {
                padding: 2px 6px;
                font-size: 0.7rem;
            }
            
            .injury-tag {
                padding: 1px 4px;
                font-size: 0.65rem;
            }
        }
        
        /* Mobile optimization for very small screens */
        @media (max-width: 991px) {
            /* On mobile, force any desktop-right elements to be left-aligned */
            .desktop-right { text-align: left !important; }
            /* Make container full width with less padding */
            .container {
                padding-left: 5px;
                padding-right: 5px;
            }
            
            .matchup-card {
                margin-bottom: 1rem;
                padding: 0.5rem;
            }
            
            /* Make header more compact */
            .matchup-header {
                font-size: 0.9rem;
                padding: 0.5rem;
            }
            
            /* Mobile-optimized team section */
            .team-section {
                padding: 0.5rem !important;
            }
            
            .team-section .row {
                margin: 0;
            }
            
            /* Smaller team names but more readable */
            .team-name {
                font-size: 1rem;
                font-weight: 700;
                line-height: 1.2;
                margin-bottom: 0.3rem;
                text-align: center;
            }
            
            /* Mobile record styling */
            .team-record {
                font-size: 0.75rem;
                display: block;
                margin-top: 0.2rem;
                margin-left: 0;
            }
            
            /* Reorganize team stats for mobile */
            .team-stats {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 0.2rem;
            }
            
            .team-stats .points {
                font-size: 1.8rem;
                font-weight: 800;
                line-height: 1;
            }
            
            .team-stats .projection {
                font-size: 0.75rem;
                opacity: 0.9;
            }
            
            /* Better spacing for team columns */
            .team-section .col-md-6 {
                padding: 0.5rem;
            }
            
            /* Make the right-aligned team actually center on mobile */
            .team-section .col-md-6.text-md-end {
                text-align: center !important;
            }
            
            /* Even more compact tables */
            .table {
                font-size: 0.75rem;
            }
            
            .table th, .table td {
                padding: 0.2rem;
                font-size: 0.75rem;
            }
            
            /* Adjust column widths for mobile - BOTH TEAMS IDENTICAL */
            /* Apply widths based on natural nth-child position for both teams */
            .player-details > div:first-child table th:nth-child(1),
            .player-details > div:first-child table td:nth-child(1),
            .player-details > div:last-child table th:nth-child(4),
            .player-details > div:last-child table td:nth-child(4) {
                width: 12%; /* POS column */
            }
            
            .player-details > div:first-child table th:nth-child(2),
            .player-details > div:first-child table td:nth-child(2),
            .player-details > div:last-child table th:nth-child(3),
            .player-details > div:last-child table td:nth-child(3) {
                width: 45%; /* Player column */
            }
            
            .player-details > div:first-child table th:nth-child(3),
            .player-details > div:first-child table td:nth-child(3),
            .player-details > div:last-child table th:nth-child(2),
            .player-details > div:last-child table td:nth-child(2) {
                width: 21%; /* Projection column */
            }
            
            .player-details > div:first-child table th:nth-child(4),
            .player-details > div:first-child table td:nth-child(4),
            .player-details > div:last-child table th:nth-child(1),
            .player-details > div:last-child table td:nth-child(1) {
                width: 21%; /* Points column */
            }
            
            /* Smaller badges */
            .position-badge {
                padding: 1px 4px;
                font-size: 0.6rem;
            }
            
            .injury-tag {
                padding: 1px 3px;
                font-size: 0.55rem;
            }
            
            /* More compact player names */
            .player-name {
                font-size: 0.75rem;
            }
            
            /* Adjust static projection parentheses */
            .static-proj {
                font-size: 0.65rem;
            }
            
            /* Smaller day selector */
            .matchup-day-select {
                font-size: 0.8rem;
                padding: 3px;
            }
            
            /* Reduce spacing in player details */
            .player-details {
                padding: 0.5rem !important;
            }
            
            .player-details > div[class*="col-md-6"] {
                margin-bottom: 15px;
                padding: 0;
            }
            
            /* Make probability bar text smaller */
            .probability-bar {
                font-size: 0.75rem;
            }
            
            /* ========== MOBILE ALIGNMENT (<450px) ========== */
            /* Apply flexbox to BOTH teams for uniform behavior */
            .player-details > div:first-child table thead tr,
            .player-details > div:first-child table tbody tr,
            .player-details > div:last-child table thead tr,
            .player-details > div:last-child table tbody tr {
                display: flex;
            }
            
            /* TEAM2: No reordering needed, just flexbox for consistency */
            .player-details > div:first-child table th:nth-child(1),
            .player-details > div:first-child table td:nth-child(1) {
                order: 1; /* POS stays at position 1 */
            }
            
            .player-details > div:first-child table th:nth-child(2),
            .player-details > div:first-child table td:nth-child(2) {
                order: 2; /* Player stays at position 2 */
            }
            
            .player-details > div:first-child table th:nth-child(3),
            .player-details > div:first-child table td:nth-child(3) {
                order: 3; /* Projection stays at position 3 */
            }
            
            .player-details > div:first-child table th:nth-child(4),
            .player-details > div:first-child table td:nth-child(4) {
                order: 4; /* Points stays at position 4 */
            }
            
            /* TEAM1: Reorder columns - Points(1) → Projection(2) → Player(3) → POS(4) becomes POS → Player → Projection → Points */
            .player-details > div:last-child table th:nth-child(1),
            .player-details > div:last-child table td:nth-child(1) {
                order: 4; /* Points moves to position 4 */
            }
            
            .player-details > div:last-child table th:nth-child(2),
            .player-details > div:last-child table td:nth-child(2) {
                order: 3; /* Projection moves to position 3 */
            }
            
            .player-details > div:last-child table th:nth-child(3),
            .player-details > div:last-child table td:nth-child(3) {
                order: 2; /* Player moves to position 2 */
            }
            
            .player-details > div:last-child table th:nth-child(4),
            .player-details > div:last-child table td:nth-child(4) {
                order: 1; /* POS moves to position 1 */
            }
            
            /* MOBILE - UNIFIED ALIGNMENT FOR BOTH TEAMS */
            /* Enable flexbox for player name cells on mobile */
            .player-details .player-name {
                display: flex !important;
                align-items: center !important;
                gap: 5px !important;
            }
            
            /* MOBILE: Injury tag ALWAYS on RIGHT (player name first, then tag) */
            .player-details .player-name .player-text {
                order: 1;
            }
            .player-details .player-name .injury-tag {
                order: 2;
            }
            
            /* Reset table layout to allow flexbox to work properly */
            .player-details table {
                table-layout: fixed !important;
                width: 100% !important;
            }
            
            /* Ensure uniform padding for all table cells - critical for alignment */
            .player-details table th,
            .player-details table td {
                padding: 0.2rem !important;
                box-sizing: border-box !important;
                vertical-align: middle !important;
            }
            
            /* POS Column - Left aligned */
            .player-details > div:first-child table th:nth-child(1),
            .player-details > div:first-child table td:nth-child(1),
            .player-details > div:last-child table th:nth-child(4),
            .player-details > div:last-child table td:nth-child(4) {
                text-align: left !important;
            }
            
            /* Player Column - Left aligned */
            .player-details > div:first-child table th:nth-child(2),
            .player-details > div:first-child table td:nth-child(2),
            .player-details > div:last-child table th:nth-child(3),
            .player-details > div:last-child table td:nth-child(3) {
                text-align: left !important;
            }
            
            /* Projection Column - Center aligned */
            .player-details > div:first-child table th:nth-child(3),
            .player-details > div:first-child table td:nth-child(3),
            .player-details > div:last-child table th:nth-child(2),
            .player-details > div:last-child table td:nth-child(2) {
                text-align: center !important;
            }
            
            /* Points Column - Center aligned */
            .player-details > div:first-child table th:nth-child(4),
            .player-details > div:first-child table td:nth-child(4),
            .player-details > div:last-child table th:nth-child(1),
            .player-details > div:last-child table td:nth-child(1) {
                text-align: center !important;
            }
            
            /* Day Total Row - Left align the text and prevent wrapping */
            .day-total-row td {
                white-space: nowrap !important;
                text-align: left !important;
            }
            
            /* Hide team names on mobile - they're already shown in the collapsed matchup header */
            .team-names-row {
                display: none !important;
            }
        }
    </style>
    <script>
        // Initialize all matchup details as collapsed
        document.addEventListener('DOMContentLoaded', function() {
            const allDetails = document.querySelectorAll('[id^="matchupDetails"]');
            allDetails.forEach(detail => {
                detail.classList.add('hidden');
            });
        });
    </script>
</head>
<body>
<div class="container">
    <h1 class="text-center mb-4">Fantasy Basketball Weekly Matchups</h1>

    <?php foreach ($matchups as $matchup_id => $matchup): ?>
        <?php
        $team1 = $matchup['team1'];  // Home team
        $team2 = $matchup['team2'];  // Away team (visiting team)
        $totals = $matchup['totals'];
        $team1_win_prob = $totals['team1']['win_probability'];
        $team2_win_prob = $totals['team2']['win_probability'];
        $selected_day = $selected_days[$matchup_id];
        ?>

        <div class="matchup-card mb-5">
            <!-- Header and Summary - Always visible and clickable -->
            <div class="matchup-header">
                Matchup #<?= substr($matchup_id, -1) + 1 ?>
            </div>

            <div class="team-section" id="teamSection<?= $matchup_id ?>">
                <div class="row matchup-header-click" onclick="toggleMatchupDetails('<?= $matchup_id ?>')"
                    <!-- Left side: Away Team (team2) -->
                    <div class="col-md-6">
                        <div class="team-name" style="color: <?= getTeamColor($team2_win_prob) ?>;">
                            <?= htmlspecialchars($team2['name']) ?>
                            <span class="team-record">(<?= htmlspecialchars($team2['record']) ?>)</span>
                        </div>
                        <div class="team-stats">
                            <span class="projection">Projected Total: <?= number_format($totals['team2']['live_projection'], 1) ?></span>
                            <span class="points"><?= $totals['team2']['points'] ?></span>
                        </div>
                    </div>
                    <!-- Right side: Home Team (team1) -->
                    <div class="col-md-6 text-md-end">
                        <div class="team-name" style="color: <?= getTeamColor($team1_win_prob) ?>;">
                            <?= htmlspecialchars($team1['name']) ?>
                            <span class="team-record">(<?= htmlspecialchars($team1['record']) ?>)</span>
                        </div>
                        <div class="team-stats team1-stats">
                            <span class="points"><?= $totals['team1']['points'] ?></span>
                            <span class="projection">Projected Total: <?= number_format($totals['team1']['live_projection'], 1) ?></span>
                        </div>
                    </div>
                </div>

                <div class="probability-bar" onclick="if(window.innerWidth > 450) toggleMatchupDetails('<?= $matchup_id ?>')">
                    <div class="progress-segment" style="width: <?= min(max($team2_win_prob, 1), 99) ?>%; background-color: <?= getTeamColor($team2_win_prob) ?>;">
                        <?= $team2_win_prob >= 2 ? formatPercentage($team2_win_prob) : '' ?>
                    </div>
                    <div class="progress-segment" style="width: <?= min(max($team1_win_prob, 1), 99) ?>%; background-color: <?= getTeamColor($team1_win_prob) ?>;">
                        <?= $team1_win_prob >= 2 ? formatPercentage($team1_win_prob) : '' ?>
                    </div>
                </div>

                <!-- Expand/Collapse indicator -->
                <div class="text-center mt-2" onclick="toggleMatchupDetails('<?= $matchup_id ?>')">
                    <span class="chevron-icon chevron-down" id="chevron<?= $matchup_id ?>">▼</span>
                </div>
            </div>

            <!-- Detailed Content - Hidden by default -->
            <div class="details-content hidden" id="matchupDetails<?= $matchup_id ?>">
                <!-- Per-matchup day selection -->
                <div class="d-flex justify-content-center mt-3 mb-3">
                    <div class="matchup-day-select">
                        <div class="d-flex align-items-center">
                            <label for="daySelect<?= $matchup_id ?>" class="me-2">Select Day:</label>
                            <select id="daySelect<?= $matchup_id ?>" class="form-select form-select-sm" style="width: auto;"
                                    onchange="updateMatchupDay('<?= $matchup_id ?>', this.value)">
                                <?php foreach ($scoring_periods as $period => $date): ?>
                                    <option value="<?= $period ?>" <?= $selected_day == $period ? 'selected' : '' ?>>
                                        Day <?= getDayOfWeek($period) ?> - <?= $date ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- Dynamic player tables content -->
                <div id="playerTables<?= $matchup_id ?>">
                    <?php echo generatePlayerTablesHTML($team1, $team2, $selected_day); ?>
                </div>
            </div>
        </div>
    <?php endforeach; ?>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
<script>
    // Toggle matchup details
    function toggleMatchupDetails(matchupId) {
        const detailsElement = document.getElementById('matchupDetails' + matchupId);
        const chevronElement = document.getElementById('chevron' + matchupId);

        if (detailsElement.classList.contains('hidden')) {
            detailsElement.classList.remove('hidden');
            chevronElement.classList.remove('chevron-down');
            chevronElement.classList.add('chevron-up');
            chevronElement.innerHTML = '▲';
            sessionStorage.setItem('matchup_' + matchupId + '_expanded', 'true');
        } else {
            detailsElement.classList.add('hidden');
            chevronElement.classList.remove('chevron-up');
            chevronElement.classList.add('chevron-down');
            chevronElement.innerHTML = '▼';
            sessionStorage.setItem('matchup_' + matchupId + '_expanded', 'false');
        }
    }

    // Update matchup day via AJAX
    function updateMatchupDay(matchupId, day) {
        // Make AJAX request
        fetch('?ajax=1&matchupId=' + matchupId + '&day=' + day)
            .then(response => response.json())
            .then(data => {
                // Update the player tables
                document.getElementById('playerTables' + matchupId).innerHTML = data.html;

                // Store the selected day in session storage
                sessionStorage.setItem('matchup_' + matchupId + '_day', day);

                // Update URL without refreshing page (optional)
                const url = new URL(window.location);
                url.searchParams.set('day_' + matchupId, day);
                window.history.pushState({}, '', url);
            })
            .catch(error => {
                console.error('Error updating matchup data:', error);
            });
    }

    // Initialize states from session storage on page load
    document.addEventListener('DOMContentLoaded', function() {
        <?php foreach ($matchups as $matchup_id => $matchup): ?>
        const stored<?= $matchup_id ?> = sessionStorage.getItem('matchup_<?= $matchup_id ?>_expanded');
        // Only expand if explicitly set to true in session storage
        if (stored<?= $matchup_id ?> === 'true') {
            const details = document.getElementById('matchupDetails<?= $matchup_id ?>');
            const chevron = document.getElementById('chevron<?= $matchup_id ?>');
            details.classList.remove('hidden');
            chevron.classList.remove('chevron-down');
            chevron.classList.add('chevron-up');
            chevron.innerHTML = '▲';
        }

        // Restore saved day if available
        const savedDay<?= $matchup_id ?> = sessionStorage.getItem('matchup_<?= $matchup_id ?>_day');
        if (savedDay<?= $matchup_id ?> && document.getElementById('daySelect<?= $matchup_id ?>').value !== savedDay<?= $matchup_id ?>) {
            document.getElementById('daySelect<?= $matchup_id ?>').value = savedDay<?= $matchup_id ?>;
            updateMatchupDay('<?= $matchup_id ?>', savedDay<?= $matchup_id ?>);
        }
        <?php endforeach; ?>
    });
</script>
</body>
</html>