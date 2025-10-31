# Fantasy Basketball Projections Dashboard

Have you ever been mad that ESPN Fantasy Basketball doesn't have the same probability odds that ESPN Fantasy Football has? This is your solution.

This is a web application that displays real-time ESPN Fantasy Basketball matchup data with player projections, live game tracking, and win probability calculations.

## What This Does

This application fetches your ESPN Fantasy Basketball league data and displays:
- Current week's matchups with projected vs actual points
- Player-by-player breakdowns for each day
- Live updates during games with minutes remaining
- Win probability calculations for each matchup
- Injury status indicators
- Mobile-responsive interface

## Quick Start Guide

### Prerequisites

Before you begin, make sure you have:
- **Python 3.9 or higher** ([Download Python](https://www.python.org/downloads/))
- **PHP 7.0 or higher** (Usually pre-installed on Mac/Linux, [Download for Windows](https://www.php.net/downloads.php))
- An **ESPN Fantasy Basketball league**

### Step 1: Download the Project

```bash
git clone https://github.com/cfarese/fantasyBasketballWebsite.git
cd fantasyBasketball
```

Or download as ZIP and extract.

### Step 2: Install Python Libraries

```bash
pip install -r requirements.txt
```

This installs all required Python packages (ESPN API, NBA API, pandas, etc.)

### Step 3: Set Up Your ESPN Credentials

#### 3a. Get Your ESPN Credentials

1. **Open your ESPN Fantasy Basketball league** in a web browser (Chrome, Firefox, Safari, etc.)
2. **Log in** to your ESPN account
3. **Open Developer Tools:**
   - **Chrome/Edge:** Press `F12` or `Ctrl+Shift+I` (Windows) / `Cmd+Option+I` (Mac)
   - **Firefox:** Press `F12` or `Ctrl+Shift+I` (Windows) / `Cmd+Option+I` (Mac)
   - **Safari:** Enable Developer menu in Preferences → Advanced, then press `Cmd+Option+I`

4. **Navigate to Cookies:**
   - **Chrome/Edge:** Click "Application" tab → "Storage" → "Cookies" → Select the ESPN domain
   - **Firefox:** Click "Storage" tab → "Cookies" → Select the ESPN domain
   - **Safari:** Click "Storage" tab → "Cookies" → Select the ESPN domain

5. **Find and copy these values:**
   - `SWID` - Should look like `{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}`
   - `espn_s2` - A very long string (several hundred characters)

6. **Get your League ID:**
   - Look at your browser's URL bar: `https://fantasy.espn.com/basketball/league?leagueId=123456`
   - Your League ID is the number after `leagueId=` (e.g., `123456`)

#### 3b. Create Your .env File

1. **Copy the template file:**
   ```bash
   cp .env_template .env
   ```

2. **Edit the .env file** with your favorite text editor:
   ```bash
   nano .env
   # or
   notepad .env
   # or use any text editor
   ```

3. **Fill in your credentials:**
   ```env
   ESPN_LEAGUE_ID=123456  # Your league ID number
   ESPN_YEAR=2026  # For 2025-26 season, use 2026
   ESPN_SWID={XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}  # Include the curly braces
   ESPN_S2=AEBxyz...  # Your very long S2 cookie value
   ```

   **Important Notes:**
   - Keep the `{curly braces}` around your `SWID` value
   - The `ESPN_YEAR` is the **ending year** of the season (2025-26 season = 2026)
   - The `ESPN_S2` value is very long - make sure you copy it completely
   - Don't add spaces around the `=` sign

### Step 4: Generate Your Data

Run the data generator script:

```bash
cd backend
python weekly_totals.py
```

**What this does:**
- Fetches your league's current matchups from ESPN
- Gets player projections and stats
- Generates `projections/weekly_matchups.json` file
- Takes 30-60 seconds to complete

**You should see output like:**
```
Fetching data for matchup 1...
Fetching data for matchup 2...
...
Weekly matchups data saved to weekly_matchups.json
```

### Step 5: Start the Web Server

From the project root directory:

```bash
php -S localhost:8000
```

**Open your browser and go to:**
```
http://localhost:8000
```

🎉 **You should now see your fantasy basketball dashboard!**

## Keeping Data Fresh

### Option 1: Manual Updates (Recommended for Testing)

Run this whenever you want fresh data:

```bash
cd backend
python weekly_totals.py
```

Then refresh your browser.

### Option 2: Automatic Updates (Recommended for Production)

Run the auto-updater in the background:

```bash
cd backend
python updater.py
```

**Update Schedule:**
- Every 3 hours from 2am-11am EST (slower updates for morning)
- Every 5 minutes from 12pm-2am EST (frequent updates during games)

**To run in background (Linux/Mac):**
```bash
nohup python updater.py > updater.log 2>&1 &
```

**To stop the updater:**
```bash
ps aux | grep updater.py
kill [process_id]
```
                                   
## Configuration Options

### Team Names Display

Edit `backend/weekly_totals.py` line 11:

```python
USE_SAFE_TEAM_NAMES = True   # Shows "John's Team" instead of "Ball Hogs"
USE_SAFE_TEAM_NAMES = False  # Shows actual team names
```

### Season Configuration

Edit `backend/config.py`:

```python
SEASON_START_DATE = (2025, 10, 21)  # Your league's start date
SEASON_YEAR = 2026  # Ending year of season
```

### Custom ESPN API Path

If you need to use a custom fork of the ESPN API:

Edit `backend/config.py`:
```python
ESPN_API_PATH = "/path/to/your/espn-api"
```

## Troubleshooting

### "Error loading or parsing JSON file"

**Problem:** No data file exists yet.

**Solution:** Run `python backend/weekly_totals.py` to generate data.

---

### "ESPN API Authentication Fails"

**Problem:** Your SWID or S2 cookie is invalid or expired.

**Solution:**
1. ESPN cookies expire periodically (weeks/months)
2. Re-obtain your cookies following Step 3 above
3. Update your `.env` file with new values
4. Run `python backend/weekly_totals.py` again

---

### "Wrong Day or Week Displayed"

**Problem:** Season start date doesn't match your league.

**Solution:**
1. Check your ESPN league settings for the actual start date
2. Update `SEASON_START_DATE` in `backend/config.py`
3. Regenerate data: `python backend/weekly_totals.py`

---

### "No Projections Showing"

**Problem:** Projection CSV files are missing.

**Solution:**
```bash
cd backend
python sps_2.py  # Generate season stats
python combined_projector.py  # Generate projections
python weekly_totals.py  # Regenerate matchup data
```

---

### "Module Not Found" Errors

**Problem:** Python dependencies not installed.

**Solution:**
```bash
pip install -r requirements.txt
```

If using Python 3.8 or lower, install timezone backport:
```bash
pip install backports.zoneinfo
```

---

### Private League Access Issues

**Problem:** Your league is private and requires authentication.

**Solution:** 
- Make sure you're logged into ESPN when getting cookies
- Your SWID and S2 must be from an account that has access to the league
- Both cookies must be current and from the same browser session

## File Structure

```
fantasyBasketball/
├── backend/               # Python backend scripts
│   ├── config.py         # Configuration (edit this for season settings)
│   ├── weekly_totals.py  # Main data generator (run this for updates)
│   ├── updater.py        # Auto-update scheduler
│   └── ...
├── projections/          # Generated data (auto-created)
│   └── weekly_matchups.json  # Main data file used by website
├── index.php             # Website frontend
├── .env                  # Your ESPN credentials (create from template)
├── .env_template         # Template for .env file
└── requirements.txt      # Python dependencies
```

## Support

**Having issues?**
1. Check the [Troubleshooting](#troubleshooting) section above
2. Open an issue on [GitHub](https://github.com/cfarese/fantasyBasketballWebsite/issues)
3. Include error messages and what you've tried

**Working perfectly?**
⭐ Star the repo on GitHub!

## Credits

Built with:
- [ESPN API](https://github.com/cwendt94/espn-api) by cwendt94
- [NBA API](https://github.com/swar/nba_api) by swar
- [Bootstrap 5](https://getbootstrap.com/)

---

**Made for fantasy basketball enthusiasts who love data** 🏀📊
