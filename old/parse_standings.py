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
    
    The match schedule table is typically located at the bottom of the page
    and contains a "Game No" column with match details.
    
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
    
    # First, try to find table with id="row2" (original expected structure)
    schedule_table = soup.find('table', id='row2')
    
    # If not found, check if match data is in the same standings table (id="row")
    # The "Game No" table might be in the same table, separated by a header row
    if not schedule_table:
        standings_table = soup.find('table', id='row')
        if standings_table:
            # Check if this table contains match data rows after the team standings
            # Look for a header row containing "Game No"
            all_rows = standings_table.find_all('tr')
            match_start_row = None
            
            for i, row in enumerate(all_rows):
                cells = row.find_all(['th', 'td'])
                cell_texts = [cell.get_text(strip=True).lower() for cell in cells]
                # Check if this row looks like a match header (contains "Game No" or similar)
                row_text = ' '.join(cell_texts)
                if any(keyword in row_text for keyword in ['game no', 'game', 'date', 'time', 'home', 'away', 'score']):
                    # Check if it has a different structure than team rows (team rows have 9 cells)
                    if len(cells) != 9 or 'team' not in row_text:
                        match_start_row = i
                        schedule_table = standings_table
                        break
            
            # If we found match data in the standings table, we'll need to skip team rows
            if match_start_row is not None:
                # Store the match start row index for later use
                pass
    
    # If still not found, look for any other table that contains "Game No" or match-related headers
    if not schedule_table:
        all_tables = soup.find_all('table')
        for table in all_tables:
            # Check if this table contains "Game No" or match-related headers
            table_text = table.get_text()
            headers = []
            thead = table.find('thead')
            if thead:
                headers = [th.get_text(strip=True).lower() for th in thead.find_all(['th', 'td'])]
            
            # Check for match-related keywords
            if any(keyword in ' '.join(headers).lower() or keyword in table_text.lower() 
                   for keyword in ['game no', 'game', 'date', 'home', 'away', 'score', 'field']):
                # Make sure it's not the standings table
                if table.get('id') != 'row':
                    schedule_table = table
                    break
            
            # Also check first row for match headers
            first_row = table.find('tr')
            if first_row:
                first_row_cells = [cell.get_text(strip=True).lower() for cell in first_row.find_all(['th', 'td'])]
                if any(keyword in ' '.join(first_row_cells) 
                       for keyword in ['game no', 'game', 'date', 'home', 'away']):
                    if table.get('id') != 'row':
                        schedule_table = table
                        break
    
    if not schedule_table:
        return matches
    
    # Find all table rows in tbody (or in the table itself if no tbody)
    tbody = schedule_table.find('tbody')
    if tbody:
        rows = tbody.find_all('tr')
    else:
        rows = schedule_table.find_all('tr')
    
    if not rows:
        return matches
    
    # Determine if we need to skip team rows (if match data is in same table)
    skip_team_rows = (schedule_table.get('id') == 'row')
    match_started = False
    
    for row in rows:
        cells = row.find_all('td')
        if not cells:
            # Try th cells if no td cells
            cells = row.find_all('th')
        
        # If we're in the standings table, skip rows that look like team standings
        if skip_team_rows and not match_started:
            # Team rows have 9 cells with specific structure
            if len(cells) == 9:
                # Check if this row looks like a match header instead
                cell_texts = [cell.get_text(strip=True).lower() for cell in cells]
                row_text = ' '.join(cell_texts)
                if any(keyword in row_text for keyword in ['game no', 'game', 'date', 'time']):
                    match_started = True
                else:
                    # This is a team row, skip it
                    continue
            elif len(cells) >= 7:
                # Different number of cells, might be match data
                match_started = True
        
        # Expected columns: Game No, Day, Date, Time, Home Team, Home Score, Away Score, Away Team, Field
        # Some rows might have match ID in first cell, so we need to handle variable number of cells
        if len(cells) >= 7:
            try:
                # Find day, date, time - these are typically in cells 1, 2, 3 or 0, 1, 2
                # The "Game No" table might have: Game No, Day, Date, Time, Home Team, Home Score, Away Score, Away Team, Field
                # Or it might start with Game No in first cell
                
                # First, check if first cell is "Game No" or a game number - if so, skip it
                start_idx = 0
                first_cell_text = cells[0].get_text(strip=True).lower() if cells else ''
                if 'game' in first_cell_text or (first_cell_text.isdigit() and len(first_cell_text) <= 3):
                    start_idx = 1  # Skip Game No column
                
                day = ''
                date = ''
                time = ''
                home_idx = -1
                
                # Look for date and time starting from start_idx
                for i in range(start_idx, len(cells)):
                    cell = cells[i]
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
                    for i in range(start_idx, len(cells)):
                        cell = cells[i]
                        text = cell.get_text(strip=True)
                        if re.match(r'\d{2}-\d{2}-\d{2}', text):
                            date = text
                            # Previous cell might be day
                            if i > start_idx:
                                prev_text = cells[i - 1].get_text(strip=True)
                                if prev_text in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
                                    day = prev_text
                            # Next cell should be time
                            if i + 1 < len(cells):
                                time = cells[i + 1].get_text(strip=True)
                            home_idx = i + 2
                            break
                
                # Find home team, scores, away team, and field
                # Structure: Game No, Day, Date, Time, Home Team, Home Score, Away Score, Away Team, Field
                home_team = ''
                home_score: Optional[int] = None
                away_score: Optional[int] = None
                away_team = ''
                field = ''
                
                # If we found date/time, the structure should be:
                # start_idx = Game No (if present)
                # start_idx+1 = Day
                # start_idx+2 = Date (if we found it)
                # start_idx+3 = Time
                # start_idx+4 = Home Team
                # start_idx+5 = Home Score
                # start_idx+6 = Away Score
                # start_idx+7 = Away Team
                # start_idx+8 = Field
                
                # If we found date, calculate indices based on that
                if date:
                    # We found date at index i, so:
                    # i-1 = Day (or start_idx if day wasn't found)
                    # i = Date
                    # i+1 = Time
                    # i+2 = Home Team
                    # i+3 = Home Score
                    # i+4 = Away Score
                    # i+5 = Away Team
                    # i+6 = Field
                    date_idx = -1
                    for idx in range(start_idx, len(cells)):
                        if cells[idx].get_text(strip=True) == date:
                            date_idx = idx
                            break
                    
                    if date_idx >= 0:
                        # Home team is 2 cells after date
                        if date_idx + 2 < len(cells):
                            home_cell = cells[date_idx + 2]
                            home_link = home_cell.find('a')
                            if home_link:
                                home_team = home_link.get_text(strip=True)
                            else:
                                home_team = home_cell.get_text(strip=True)
                        
                        # Home score is 3 cells after date
                        if date_idx + 3 < len(cells):
                            score_text = cells[date_idx + 3].get_text(strip=True)
                            if score_text and score_text.strip():
                                try:
                                    home_score = int(score_text)
                                except ValueError:
                                    pass
                        
                        # Away score is 4 cells after date
                        if date_idx + 4 < len(cells):
                            score_text = cells[date_idx + 4].get_text(strip=True)
                            if score_text and score_text.strip():
                                try:
                                    away_score = int(score_text)
                                except ValueError:
                                    pass
                        
                        # Away team is 5 cells after date
                        if date_idx + 5 < len(cells):
                            away_cell = cells[date_idx + 5]
                            away_link = away_cell.find('a')
                            if away_link:
                                away_team = away_link.get_text(strip=True)
                            else:
                                away_team = away_cell.get_text(strip=True)
                        
                        # Field is 6 cells after date
                        if date_idx + 6 < len(cells):
                            field = cells[date_idx + 6].get_text(strip=True)
                elif home_idx >= 0:
                    # Fallback: try to find home team at the expected index
                    if home_idx < len(cells):
                        home_cell = cells[home_idx]
                        home_link = home_cell.find('a')
                        if home_link:
                            home_team = home_link.get_text(strip=True)
                        else:
                            home_team = home_cell.get_text(strip=True)
                        
                        # Home score should be in next cell
                        if home_idx + 1 < len(cells):
                            score_text = cells[home_idx + 1].get_text(strip=True)
                            if score_text and score_text.strip():
                                try:
                                    home_score = int(score_text)
                                except ValueError:
                                    pass
                        
                        # Away score should be after home score
                        if home_idx + 2 < len(cells):
                            score_text = cells[home_idx + 2].get_text(strip=True)
                            if score_text and score_text.strip():
                                try:
                                    away_score = int(score_text)
                                except ValueError:
                                    pass
                        
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


def parse_csv_link(html_content: str) -> Optional[str]:
    """
    Parse CSV download link from standings.jsp HTML.
    
    The CSV link is typically at the bottom of the page in a div with
    class "exportlinks" with a link containing "export csv" class.
    
    Parameters
    ----------
    html_content : str
        The HTML content from standings.jsp
        
    Returns
    -------
    Optional[str]
        CSV download URL (relative or absolute), or None if not found
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the exportlinks div
    export_div = soup.find('div', class_='exportlinks')
    if not export_div:
        return None
    
    # Find the CSV link (has class "export csv")
    csv_link = export_div.find('a', class_='export csv')
    if not csv_link:
        # Try alternative: look for link containing "csv" in text or class
        csv_link = export_div.find('a', string=re.compile(r'CSV', re.I))
        if not csv_link:
            # Try finding any link with "csv" in href
            for link in export_div.find_all('a'):
                href = link.get('href', '')
                if 'csv' in href.lower() or 'd-49682-e=1' in href:
                    csv_link = link
                    break
    
    if csv_link:
        href = csv_link.get('href', '')
        if href:
            # Make it absolute URL if it's relative
            if href.startswith('/'):
                return f"https://www.gvsoccer.org{href}"
            elif href.startswith('http'):
                return href
            else:
                return f"https://www.gvsoccer.org/{href}"
    
    return None


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
        - csv_link: Optional[str] - CSV download URL
    """
    return {
        'division_info': parse_division_info(html_content),
        'teams': parse_team_standings(html_content),
        'matches': parse_match_results(html_content),
        'csv_link': parse_csv_link(html_content)
    }

