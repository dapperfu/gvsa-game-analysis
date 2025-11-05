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
    
    # Parse CSV
    csv_reader = csv.DictReader(io.StringIO(csv_content))
    
    # Check if this is team standings or matches
    # Team standings typically have: Team, Wins, Losses, Ties, etc.
    # Matches typically have: Game No, Date, Time, Home Team, Away Team, etc.
    
    fieldnames = csv_reader.fieldnames
    if not fieldnames:
        return {'teams': teams, 'matches': matches}
    
    # Determine if this is teams or matches CSV
    is_teams = any(col.lower() in ['team', 'wins', 'losses', 'points'] for col in fieldnames)
    is_matches = any(col.lower() in ['game no', 'game', 'date', 'home team', 'away team'] for col in fieldnames)
    
    # Reset reader
    csv_reader = csv.DictReader(io.StringIO(csv_content))
    
    if is_teams:
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
        for row in csv_reader:
            # Match CSV structure: Game No, Day, Date, Time, Home Team, Home Score, Away Score, Away Team, Field
            home_team = row.get('Home Team', '').strip()
            away_team = row.get('Away Team', '').strip()
            date = row.get('Date', '').strip()
            
            if not home_team or not away_team:
                continue
            
            # Parse scores
            home_score_str = row.get('Home Score', row.get('Score', '')).strip()
            away_score_str = row.get('Away Score', '').strip()
            
            home_score: Optional[int] = None
            away_score: Optional[int] = None
            
            if home_score_str and home_score_str.isdigit():
                home_score = int(home_score_str)
            if away_score_str and away_score_str.isdigit():
                away_score = int(away_score_str)
            
            # Determine status
            status = 'completed' if (home_score is not None and away_score is not None) else 'scheduled'
            
            # Get day if available
            day = row.get('Day', '').strip()
            if day and date:
                date = f"{day} {date}"
            
            matches.append({
                'date': date,
                'time': row.get('Time', '').strip(),
                'home_team': home_team,
                'away_team': away_team,
                'field': row.get('Field', '').strip(),
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

