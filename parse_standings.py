#!/usr/bin/env python3
"""
Parse standings.jsp HTML to extract teams and match results.

This module parses the HTML response from standings.jsp to extract:
- Team standings (wins, losses, ties, points, goals, etc.)
- Match results/schedule (dates, teams, scores, fields)
"""
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import re


def parse_team_standings(html_content: str) -> List[Dict[str, Any]]:
    """
    Parse team standings table from standings.jsp HTML.
    
    Parameters
    ----------
    html_content : str
        The HTML content from standings.jsp
        
    Returns
    -------
    List[Dict[str, Any]]
        List of team standings dictionaries with keys:
        - team_name: str
        - wins: int
        - losses: int
        - ties: int
        - forfeits: int
        - points: int
        - goals_for: int
        - goals_against: int
        - goal_differential: int
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    teams: List[Dict[str, Any]] = []
    
    # Find the standings table (table with id="row")
    standings_table = soup.find('table', id='row')
    if not standings_table:
        return teams
    
    # Find all table rows in tbody
    tbody = standings_table.find('tbody')
    if not tbody:
        return teams
    
    rows = tbody.find_all('tr')
    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 9:  # Team, W, L, T, F, PTS, GF, GA, GD
            try:
                team_name = cells[0].get_text(strip=True)
                
                # Skip rows with empty team names
                if not team_name:
                    continue
                
                # Parse numeric values, handling negative numbers and empty strings
                def parse_int(value: str) -> int:
                    """Parse integer value, handling empty strings and negative numbers."""
                    value = value.strip()
                    if not value:
                        return 0
                    # Handle negative numbers (e.g., "-1", " -21")
                    return int(value)
                
                wins = parse_int(cells[1].get_text(strip=True))
                losses = parse_int(cells[2].get_text(strip=True))
                ties = parse_int(cells[3].get_text(strip=True))
                forfeits = parse_int(cells[4].get_text(strip=True))
                points = parse_int(cells[5].get_text(strip=True))
                goals_for = parse_int(cells[6].get_text(strip=True))
                goals_against = parse_int(cells[7].get_text(strip=True))
                goal_differential = parse_int(cells[8].get_text(strip=True))
                
                teams.append({
                    'team_name': team_name,
                    'wins': wins,
                    'losses': losses,
                    'ties': ties,
                    'forfeits': forfeits,
                    'points': points,
                    'goals_for': goals_for,
                    'goals_against': goals_against,
                    'goal_differential': goal_differential
                })
            except (ValueError, IndexError) as e:
                # Skip rows that don't match expected format
                continue
    
    return teams


def parse_match_results(html_content: str) -> List[Dict[str, Any]]:
    """
    Parse match results/schedule table from standings.jsp HTML.
    
    Parameters
    ----------
    html_content : str
        The HTML content from standings.jsp
        
    Returns
    -------
    List[Dict[str, Any]]
        List of match dictionaries with keys:
        - date: str
        - time: str
        - home_team: str
        - away_team: str
        - field: str
        - home_score: Optional[int]
        - away_score: Optional[int]
        - status: str (scheduled/completed)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    matches: List[Dict[str, Any]] = []
    
    # Find the schedule/results table (table with id="row2")
    schedule_table = soup.find('table', id='row2')
    if not schedule_table:
        return matches
    
    # Find all table rows in tbody
    tbody = schedule_table.find('tbody')
    if not tbody:
        return matches
    
    rows = tbody.find_all('tr')
    for row in rows:
        cells = row.find_all('td')
        # Expected columns: [Match ID], Day, Date, Time, Home Team, Home Score, Away Score, Away Team, Field
        # Some rows might have match ID in first cell, so we need to handle variable number of cells
        if len(cells) >= 7:
            try:
                # Find day, date, time - these are typically in cells 1, 2, 3 or 0, 1, 2
                # Look for date-like pattern (MM-DD-YY)
                day = ''
                date = ''
                time = ''
                home_idx = -1
                
                for i, cell in enumerate(cells):
                    text = cell.get_text(strip=True)
                    # Check if it's a day of week
                    if text in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
                        day = text
                        # Date should be next cell
                        if i + 1 < len(cells):
                            date_text = cells[i + 1].get_text(strip=True)
                            if re.match(r'\d{2}-\d{2}-\d{2}', date_text):
                                date = date_text
                                # Time should be after date
                                if i + 2 < len(cells):
                                    time = cells[i + 2].get_text(strip=True)
                                home_idx = i + 3
                        break
                
                # If we didn't find day, try to find date directly
                if not date:
                    for i, cell in enumerate(cells):
                        text = cell.get_text(strip=True)
                        if re.match(r'\d{2}-\d{2}-\d{2}', text):
                            date = text
                            # Previous cell might be day
                            if i > 0:
                                day = cells[i - 1].get_text(strip=True)
                            # Next cell should be time
                            if i + 1 < len(cells):
                                time = cells[i + 1].get_text(strip=True)
                            home_idx = i + 2
                            break
                
                # Find home team
                home_team = ''
                home_score: Optional[int] = None
                away_score: Optional[int] = None
                away_team = ''
                field = ''
                
                if home_idx >= 0 and home_idx < len(cells):
                    # Home team cell
                    home_cell = cells[home_idx]
                    home_link = home_cell.find('a')
                    if home_link:
                        home_team = home_link.get_text(strip=True)
                    else:
                        home_team = home_cell.get_text(strip=True)
                    
                    # Home score should be in next cell
                    if home_idx + 1 < len(cells):
                        score_text = cells[home_idx + 1].get_text(strip=True)
                        if score_text and score_text.isdigit():
                            home_score = int(score_text)
                    
                    # Away score should be after home score
                    if home_idx + 2 < len(cells):
                        score_text = cells[home_idx + 2].get_text(strip=True)
                        if score_text and score_text.isdigit():
                            away_score = int(score_text)
                    
                    # Away team should be after scores
                    away_idx = home_idx + 3
                    if away_idx < len(cells):
                        away_cell = cells[away_idx]
                        away_link = away_cell.find('a')
                        if away_link:
                            away_team = away_link.get_text(strip=True)
                        else:
                            away_team = away_cell.get_text(strip=True)
                    
                    # Field should be last cell
                    if len(cells) > away_idx + 1:
                        field = cells[away_idx + 1].get_text(strip=True)
                
                # Determine status
                status = 'completed' if (home_score is not None and away_score is not None) else 'scheduled'
                
                # Only add if we have essential data
                if date and home_team and away_team:
                    matches.append({
                        'date': f"{day} {date}" if day else date,
                        'time': time,
                        'home_team': home_team,
                        'away_team': away_team,
                        'field': field,
                        'home_score': home_score,
                        'away_score': away_score,
                        'status': status
                    })
            except (ValueError, IndexError) as e:
                # Skip rows that don't match expected format
                continue
    
    return matches


def parse_division_info(html_content: str) -> Dict[str, str]:
    """
    Parse division information from standings.jsp HTML.
    
    Parameters
    ----------
    html_content : str
        The HTML content from standings.jsp
        
    Returns
    -------
    Dict[str, str]
        Dictionary with keys:
        - division_name: str
        - season: str
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    info: Dict[str, str] = {}
    
    # Look for h1 tags that contain division and season info
    h1_tags = soup.find_all('h1')
    for h1 in h1_tags:
        text = h1.get_text(strip=True)
        if text:
            if 'division' in text.lower() or 'boys' in text.lower() or 'girls' in text.lower():
                info['division_name'] = text
            elif re.match(r'.*\d{4}', text):  # Looks like a year/season
                info['season'] = text
    
    return info


def parse_standings(html_content: str) -> Dict[str, Any]:
    """
    Parse complete standings.jsp HTML to extract all data.
    
    Parameters
    ----------
    html_content : str
        The HTML content from standings.jsp
        
    Returns
    -------
    Dict[str, Any]
        Dictionary containing:
        - division_info: Dict[str, str]
        - teams: List[Dict[str, Any]]
        - matches: List[Dict[str, Any]]
    """
    return {
        'division_info': parse_division_info(html_content),
        'teams': parse_team_standings(html_content),
        'matches': parse_match_results(html_content)
    }

