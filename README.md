# GVSA Soccer Scraper

This project scrapes team and match result data from the Grand Valley Soccer Association (GVSA) website (https://www.gvsoccer.org/) and stores it in a local SQLite database.

## Overview

The GVSA website uses a frame-based structure that makes direct scraping challenging. This scraper:

1. Analyzes mitmproxy logs to understand the website's API structure
2. Directly calls JSP endpoints to bypass the frame structure
3. Parses HTML responses to extract team standings and match results
4. Stores all data in a SQLite database for offline access

## Features

- Scrapes all divisions and seasons
- Extracts team standings (wins, losses, ties, points, goals, etc.)
- Extracts match results and schedules
- Stores data in SQLite database with proper relational structure
- Handles frame-based website architecture

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

### Testing the Parser

To test the HTML parser with the extracted data:

```bash
make test
```

## Project Structure

- `analyze_mitm.py` - Script to analyze mitmproxy logs using mitmproxy tools
- `extract_data.py` - Script to extract JSP responses from mitmproxy logs
- `parse_seasons.py` - Parser for seasons.jsp to extract division list
- `parse_standings.py` - Parser for standings.jsp to extract teams and matches
- `scraper.py` - Main scraper that orchestrates fetching and parsing
- `database.py` - Database interface for storing scraped data
- `mitm_logs/` - Directory containing mitmproxy capture logs

## Database Schema

The SQLite database contains three main tables:

### divisions
- Stores division information (ID, name, season, etc.)

### teams
- Stores team standings data
- Links to divisions via foreign key
- Contains: wins, losses, ties, forfeits, points, goals_for, goals_against, goal_differential

### matches
- Stores match results and schedules
- Links to divisions via foreign key
- Contains: date, time, home_team, away_team, field, home_score, away_score, status

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

- Python 3.8+
- mitmproxy (for analyzing logs)
- beautifulsoup4 (for HTML parsing)
- requests (for HTTP requests)
- lxml (for HTML parsing)

## Notes

- The scraper includes a 1-second delay between requests to be respectful to the server
- The website uses ISO-8859-1 encoding
- Some match results may be scheduled (not yet played) and won't have scores

## License

This project is for educational/personal use only. Please respect the website's terms of service and robots.txt.

