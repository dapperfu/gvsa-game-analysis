#!/usr/bin/env python3
"""
Parse CSV data from GVSA standings export.

This module parses CSV data exported from standings.jsp to extract
teams and match results more reliably than HTML parsing.
"""
from typing import List, Dict, Any, Optional
import csv
import io
import re


def parse_csv_standings(csv_content: str) -> Dict[str, Any]:
    """
    Parse CSV content from standings.jsp export.
    
    The CSV typically contains both team standings and match results.
    CSV files use positional format (no headers):
    - Matches: Game No, Day, Date, Time, Home Team, Home Score, Away Score, Away Team, Field
    - Teams: Team, Wins, Losses, Ties, Forfeits, Points, GF, GA, GD (if headers present)
    
    Parameters
    ----------
    csv_content : str
        CSV content as string
        
    Returns
    -------
    Dict[str, Any]
        Dictionary containing:
        - teams: List[Dict[str, Any]]
        - matches: List[Dict[str, Any]]
    """
    teams: List[Dict[str, Any]] = []
    matches: List[Dict[str, Any]] = []
    
    # Parse CSV - try both DictReader (with headers) and reader (positional)
    csv_reader = csv.reader(io.StringIO(csv_content))
    first_row = next(csv_reader, None)
    
    if first_row is None:
        return {'teams': teams, 'matches': matches}
    
    # Determine if this is teams or matches CSV by examining first row
    # Matches CSV typically starts with game number (e.g., "1461-3", "1473-2")
    # Teams CSV typically has headers or starts with team name
    is_matches = False
    is_teams = False
    has_headers = False
    
    # Check if first row looks like a header row (contains "Team", "Wins", etc.)
    if len(first_row) > 0:
        first_col_lower = first_row[0].strip().lower() if first_row[0] else ''
        if first_col_lower in ['team', 'game no', 'game']:
            # Has headers, reset and use DictReader
            has_headers = True
            csv_reader_dict = csv.DictReader(io.StringIO(csv_content))
            fieldnames = csv_reader_dict.fieldnames
            if fieldnames:
                is_teams = any(col.lower() in ['team', 'wins', 'losses', 'points'] for col in fieldnames)
                is_matches = any(col.lower() in ['game no', 'game', 'date', 'home team', 'away team'] for col in fieldnames)
        else:
            # No headers, positional format - check structure
            # Matches have 9 columns: Game No, Day, Date, Time, Home Team, Home Score, Away Score, Away Team, Field
            if len(first_row) >= 8:
                # Check if first column looks like a game number (e.g., "1461-3", "1473-2")
                game_no_pattern = re.match(r'^\d+-\d+', first_row[0].strip())
                if game_no_pattern:
                    is_matches = True
                    has_headers = False
    
    # Set up the appropriate reader based on what we detected
    if has_headers and (is_teams or is_matches):
        csv_reader = csv.DictReader(io.StringIO(csv_content))
    elif is_matches:
        # Positional format for matches
        csv_reader = csv.reader(io.StringIO(csv_content))
    else:
        # Unknown format, try positional
        csv_reader = csv.reader(io.StringIO(csv_content))
    
    if is_teams:
        # Teams CSV with headers
        for row in csv_reader:
            team_name = row.get('Team', '').strip()
            if not team_name:
                continue
            
            def parse_int(value: str) -> int:
                """Parse integer, handling empty strings."""
                value = str(value).strip()
                if not value:
                    return 0
                try:
                    return int(value)
                except ValueError:
                    return 0
            
            teams.append({
                'team_name': team_name,
                'wins': parse_int(row.get('Wins', '0')),
                'losses': parse_int(row.get('Losses', '0')),
                'ties': parse_int(row.get('Ties', '0')),
                'forfeits': parse_int(row.get('Forfeits', '0')),
                'points': parse_int(row.get('PTS', row.get('Points', '0'))),
                'goals_for': parse_int(row.get('GF', row.get('Goals For', '0'))),
                'goals_against': parse_int(row.get('GA', row.get('Goals Against', '0'))),
                'goal_differential': parse_int(row.get('GD', row.get('Goal Differential', '0')))
            })
    
    if is_matches:
        # Matches CSV - handle both DictReader (headers) and positional
        for row in csv_reader:
            if isinstance(row, dict):
                # Has headers
                home_team = row.get('Home Team', '').strip()
                away_team = row.get('Away Team', '').strip()
                date = row.get('Date', '').strip()
                time = row.get('Time', '').strip()
                field = row.get('Field', '').strip()
                home_score_str = row.get('Home Score', row.get('Score', '')).strip()
                away_score_str = row.get('Away Score', '').strip()
                day = row.get('Day', '').strip()
            else:
                # Positional format: Game No, Day, Date, Time, Home Team, Home Score, Away Score, Away Team, Field
                if len(row) < 8:
                    continue
                home_team = row[4].strip() if len(row) > 4 else ''
                away_team = row[7].strip() if len(row) > 7 else ''
                date = row[2].strip() if len(row) > 2 else ''
                time = row[3].strip() if len(row) > 3 else ''
                field = row[8].strip() if len(row) > 8 else ''
                home_score_str = row[5].strip() if len(row) > 5 else ''
                away_score_str = row[6].strip() if len(row) > 6 else ''
                day = row[1].strip() if len(row) > 1 else ''
            
            if not home_team or not away_team:
                continue
            
            # Parse scores with forfeit handling (Option B: winner=1, loser=NULL)
            home_score: Optional[int] = None
            away_score: Optional[int] = None
            
            # Check for forfeits (WF = Win Forfeit, LF = Loss Forfeit)
            home_is_wf = home_score_str.upper() == 'WF'
            home_is_lf = home_score_str.upper() == 'LF'
            away_is_wf = away_score_str.upper() == 'WF'
            away_is_lf = away_score_str.upper() == 'LF'
            
            if home_is_wf and away_is_lf:
                # Home team won by forfeit
                home_score = 1
                away_score = None
            elif home_is_lf and away_is_wf:
                # Away team won by forfeit
                home_score = None
                away_score = 1
            elif home_is_wf or home_is_lf or away_is_wf or away_is_lf:
                # Invalid state - both should be WF/LF or neither
                # Skip this row or handle as scheduled
                continue
            else:
                # Regular scores - parse as integers
                if home_score_str and home_score_str.isdigit():
                    home_score = int(home_score_str)
                if away_score_str and away_score_str.isdigit():
                    away_score = int(away_score_str)
            
            # Determine status
            # Match is completed if both scores are set (including forfeits where winner=1)
            # or if it's a forfeit (one score is 1, other is None)
            is_forfeit = (home_score == 1 and away_score is None) or (away_score == 1 and home_score is None)
            has_scores = home_score is not None and away_score is not None
            status = 'completed' if (has_scores or is_forfeit) else 'scheduled'
            
            # Combine day and date if available
            if day and date:
                date = f"{day} {date}"
            
            matches.append({
                'date': date,
                'time': time,
                'home_team': home_team,
                'away_team': away_team,
                'field': field,
                'home_score': home_score,
                'away_score': away_score,
                'status': status
            })
    
    return {
        'teams': teams,
        'matches': matches
    }


def download_csv_standings(url: str, division_param: str, session) -> Optional[str]:
    """
    Download CSV data from standings.jsp.
    
    Parameters
    ----------
    url : str
        Base URL for standings.jsp
    division_param : str
        Division parameter string
    session : requests.Session
        Requests session object
        
    Returns
    -------
    Optional[str]
        CSV content as string, or None if download fails
    """
    # Try different methods to get CSV
    
    # Method 1: Add format=csv parameter
    try:
        response = session.post(url, data={'division': division_param, 'format': 'csv'}, timeout=30)
        response.raise_for_status()
        if 'text/csv' in response.headers.get('Content-Type', '') or response.text.strip().startswith('Game No'):
            return response.text
    except Exception:
        pass
    
    # Method 2: Use CSV endpoint
    try:
        csv_url = url.replace('.jsp', '.csv')
        response = session.post(csv_url, data={'division': division_param}, timeout=30)
        response.raise_for_status()
        if response.text.strip() and (',' in response.text[:100] or response.text.startswith('Game No')):
            return response.text
    except Exception:
        pass
    
    # Method 3: Add ?export=csv query parameter
    try:
        response = session.post(url + '?export=csv', data={'division': division_param}, timeout=30)
        response.raise_for_status()
        if response.text.strip() and (',' in response.text[:100] or response.text.startswith('Game No')):
            return response.text
    except Exception:
        pass
    
    return None

