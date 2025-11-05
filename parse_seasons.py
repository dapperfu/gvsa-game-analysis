#!/usr/bin/env python3
"""
Parse seasons.jsp HTML to extract available divisions and seasons.

This module parses the HTML response from seasons.jsp to extract
the list of available divisions with their IDs and parameters, and
also identifies available seasons to scrape.
"""
from typing import List, Dict, Any, Set, Tuple
from bs4 import BeautifulSoup
import re


def parse_seasons_list(html_content: str) -> List[Dict[str, str]]:
    """
    Parse available seasons from seasons.jsp HTML.
    
    Looks for a season selector or extracts unique seasons from divisions.
    
    Parameters
    ----------
    html_content : str
        The HTML content from seasons.jsp
        
    Returns
    -------
    List[Dict[str, str]]
        List of season dictionaries with keys:
        - year_season: str
        - season_name: str
        - season_type: str
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    seasons: Set[Tuple[str, str, str]] = set()
    
    # Look for a season selector
    season_select = soup.find('select', {'name': 'season'})
    if season_select:
        options = season_select.find_all('option')
        for option in options:
            value = option.get('value', '')
            text = option.get_text(strip=True)
            if value and value != 'Seasons' and text and text != '-Select Season-':
                # Parse season value format: "year_season,season_id1,season_id2,season_name"
                # Example: "2025/2026 ,      2775,      2846,Fall 2025                     "
                parts = value.split(',')
                if len(parts) >= 4:
                    year_season = parts[0].strip()
                    season_id1 = parts[1].strip() if len(parts) > 1 else ''
                    season_id2 = parts[2].strip() if len(parts) > 2 else ''
                    season_name = parts[3].strip()
                    # Determine season type from name (case-insensitive)
                    season_name_lower = season_name.lower()
                    if 'spring' in season_name_lower:
                        season_type = 'S'
                    elif 'fall' in season_name_lower:
                        season_type = 'F'
                    else:
                        season_type = 'F'  # Default to Fall
                    # Store full value for later use
                    seasons.add((year_season, season_name, season_type, value))
                elif len(parts) >= 1:
                    # Fallback: try to extract from text
                    year_season = parts[0].strip() if parts[0].strip() else text
                    season_name = text
                    text_lower = text.lower()
                    season_type = 'S' if 'spring' in text_lower else 'F'
                    seasons.add((year_season, season_name, season_type))
    
    # If no season selector, extract from divisions
    if not seasons:
        divisions = parse_divisions(html_content)
        for div in divisions:
            seasons.add((
                div['year_season'],
                div['season_name'],
                div['season_type']
            ))
    
    result = []
    for item in sorted(seasons):
        if len(item) == 4:
            y, s, t, v = item
            result.append({
                'year_season': y,
                'season_name': s,
                'season_type': t,
                'season_value': v  # Full value for POST requests
            })
        else:
            y, s, t = item
            result.append({
                'year_season': y,
                'season_name': s,
                'season_type': t,
                'season_value': None
            })
    return result


def parse_divisions(html_content: str) -> List[Dict[str, Any]]:
    """
    Parse divisions from seasons.jsp HTML.
    
    Parameters
    ----------
    html_content : str
        The HTML content from seasons.jsp
        
    Returns
    -------
    List[Dict[str, Any]]
        List of division dictionaries with keys:
        - division_id: str
        - year_season: str (e.g., "2025/2026")
        - season_id1: str
        - season_id2: str
        - season_name: str (e.g., "Fall 2025")
        - division_name: str (e.g., "U11 Boys 5th Division")
        - season_type: str (e.g., "F" for Fall)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    divisions: List[Dict[str, Any]] = []
    
    # Find the select element with division options
    select = soup.find('select', {'name': 'division'})
    if not select:
        return divisions
    
    options = select.find_all('option')
    for option in options:
        value = option.get('value', '')
        text = option.get_text(strip=True)
        
        # Skip the default "Select Division" option
        if value == 'Divisions' or not value:
            continue
        
        # Parse the value format: "division_id,year/season,season_id1,season_id2,season_name,division_name,season_type"
        parts = value.split(',')
        if len(parts) >= 7:
            try:
                season_name = parts[4].strip()
                season_type_from_html = parts[6].strip()
                
                # Override season_type from HTML if it's wrong - check season_name instead
                season_name_lower = season_name.lower()
                if 'spring' in season_name_lower:
                    season_type = 'S'
                elif 'fall' in season_name_lower:
                    season_type = 'F'
                else:
                    # Fall back to HTML value
                    season_type = season_type_from_html if season_type_from_html in ('F', 'S') else 'F'
                
                division_id = parts[0].strip()
                division_name = parts[5].strip()
                
                # Validate division_id is present and not empty
                if not division_id:
                    # Skip divisions without valid division_id
                    continue
                
                # Validate division_name matches dropdown text (should be 1:1)
                # Normalize both for comparison (remove extra whitespace)
                text_normalized = ' '.join(text.split())
                division_name_normalized = ' '.join(division_name.split())
                
                # They should match (dropdown text is the display name)
                # If they don't match exactly, use the dropdown text as the authoritative source
                if text_normalized != division_name_normalized:
                    # Use dropdown text as division_name (it's the authoritative source)
                    division_name = text_normalized
                
                divisions.append({
                    'division_id': division_id,
                    'year_season': parts[1].strip(),  # Keep for POST requests only
                    'season_id1': parts[2].strip(),
                    'season_id2': parts[3].strip(),
                    'season_name': season_name,
                    'division_name': division_name,
                    'season_type': season_type,
                    'display_name': text  # Display name from HTML option text
                })
            except (IndexError, ValueError):
                # Skip malformed entries
                continue
    
    return divisions
