# GVSA Game Analysis

This project scrapes and analyzes team and match result data from the Grand Valley Soccer Association (GVSA) website (https://www.gvsoccer.org/) and stores it in a local SQLite database for analysis.

## About GVSA

The Grand Valley Soccer Association (GVSA) is a youth soccer organization that organizes leagues for teams across multiple age groups. The organization runs seasonal leagues (Fall and Spring) with divisions organized by:
- Age groups: U10 through U19 (under 10, under 11, etc.), with some combined groups like U15/16 and U17/19
- Gender: Separate divisions for Boys and Girls
- Skill level: Multiple divisions within each age group (e.g., Elite, 1st Division, 2nd Division, etc.)

Teams are organized by clubs and participate across multiple seasons, with players and teams naturally progressing through age groups as they get older.

## Overview

The GVSA website uses a frame-based structure that makes direct scraping challenging. This scraper:

1. Analyzes mitmproxy logs to understand the website's API structure
2. Directly calls JSP endpoints to bypass the frame structure
3. Parses HTML responses to extract team standings and match results
4. Stores all data in a SQLite database for offline access

## Features

### Data Collection
- Scrapes all divisions and seasons from gvsoccer.org
- Extracts team standings (wins, losses, ties, points, goals, etc.)
- Extracts match results and schedules
- Stores data in SQLite database with proper relational structure
- Handles frame-based website architecture

### Data Analysis
- **Team Progression Tracking**: Track teams through age group progression (U10 → U11 → U12 → U13 → U14)
- **Cross-Season Analysis**: Link teams across seasons using fuzzy matching and club associations
- **Statistical Analysis**: Analyze team performance, goal differentials, and league standings
- **Jupyter Notebook Support**: Interactive analysis environment for exploring the data

## Installation

1. Create and activate the virtual environment:
```bash
make install
```

This will:
- Create a Python virtual environment (`venv_gvsa_scrape`)
- Install all required dependencies

## Usage

### Scraping Data

To scrape all divisions and store data in the database:

```bash
make scrape
```

Or run directly:

```bash
./venv_gvsa_scrape/bin/python3 scraper.py [database_path]
```

The database path is optional (defaults to `gvsa_data.db`).

### Data Analysis with Jupyter Notebook

After scraping data, you can analyze it using the Jupyter notebook:

1. Start Jupyter:
```bash
./venv_gvsa_scrape/bin/jupyter notebook
```

2. Open `analysis.ipynb` to explore:
   - Database schema and relationships
   - Basic statistics (team counts, match counts, etc.)
   - Sample data from each table

### Team Progression Analysis

Track teams through age group progression:

```python
from team_progression import track_team_progression, find_team_progression_path

# Track all teams through U10-U14 progression
progressions = track_team_progression(min_age=10, max_age=14)

# Find progression for a specific team
team_path = find_team_progression_path("Rapids FC 15B Black")
```

### Testing the Parser

To test the HTML parser with the extracted data:

```bash
make test
```

## Project Structure

### Scraping Components
- `analyze_mitm.py` - Script to analyze mitmproxy logs using mitmproxy tools
- `extract_data.py` - Script to extract JSP responses from mitmproxy logs
- `parse_seasons.py` - Parser for seasons.jsp to extract division list
- `parse_standings.py` - Parser for standings.jsp to extract teams and matches
- `scraper.py` - Main scraper that orchestrates fetching and parsing
- `db_pony.py` - Database interface using PonyORM for storing scraped data
- `models.py` - PonyORM database models (Season, Division, Team, TeamSeason, Match, Club)
- `mitm_logs/` - Directory containing mitmproxy capture logs

### Analysis Components
- `team_progression.py` - Team progression tracking across age groups
- `analysis.ipynb` - Jupyter notebook for data exploration and analysis

## Database Schema

The SQLite database uses PonyORM and contains the following entities:

### Season
- Represents a soccer season (e.g., "Fall 2025", "Spring 2026")
- Fields: year_season, season_name, season_type, scraped_at

### Division
- Represents a division within a season (e.g., "U11 Boys 5th Division")
- Fields: division_id, division_name, season (FK), scraped_at
- Links to: Season, TeamSeason, Match

### Club
- Represents a soccer club (e.g., "NUSC", "Rapids FC")
- Fields: name, canonical_name (normalized for matching)
- Links to: Team

### Team
- Represents a team entity that persists across seasons
- Teams are matched across seasons using fuzzy string matching
- Fields: canonical_name, club (FK)
- Links to: Club, TeamSeason

### TeamSeason
- Represents a team's participation in a specific division/season
- Links teams to divisions and stores season-specific statistics
- Fields: team (FK), division (FK), team_name, wins, losses, ties, forfeits, points, goals_for, goals_against, goal_differential, scraped_at
- Links to: Team, Division, Match (home_matches, away_matches)

### Match
- Represents a soccer match
- Fields: division (FK), date, time, home_team (FK), away_team (FK), field, home_score, away_score, status, scraped_at

## How It Works

1. **Analysis Phase**: The mitmproxy logs are analyzed to identify:
   - JSP endpoints (`seasons.jsp`, `standings.jsp`)
   - POST request parameters
   - Response structure

2. **Scraping Phase**:
   - Fetches division list from `seasons.jsp`
   - For each division, fetches standings from `standings.jsp`
   - Parses HTML to extract teams and matches

3. **Storage Phase**:
   - Creates/updates division records
   - Stores team standings
   - Stores match results

## Requirements

### Core Dependencies
- Python 3.8+
- mitmproxy (for analyzing logs)
- beautifulsoup4 (for HTML parsing)
- requests (for HTTP requests)
- lxml (for HTML parsing)
- pony (PonyORM for database ORM)
- thefuzz (for fuzzy string matching)
- python-Levenshtein (for string matching performance)

### Analysis Dependencies
- jupyter (Jupyter notebook server)
- notebook (Jupyter notebook interface)
- pandas (data manipulation and analysis)
- numpy (numerical computing)
- matplotlib (plotting and visualization)
- seaborn (statistical data visualization)

All dependencies are listed in `requirements.txt` and installed automatically with `make install`.

## Notes

- The scraper includes a 1-second delay between requests to be respectful to the server
- The website uses ISO-8859-1 encoding
- Some match results may be scheduled (not yet played) and won't have scores

## License

This project is for educational/personal use only. Please respect the website's terms of service and robots.txt.

