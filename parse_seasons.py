#!/usr/bin/env python3
"""
Parse seasons.jsp HTML to extract available divisions.

This module parses the HTML response from seasons.jsp to extract
the list of available divisions with their IDs and parameters.
"""
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import re


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
                divisions.append({
                    'division_id': parts[0].strip(),
                    'year_season': parts[1].strip(),
                    'season_id1': parts[2].strip(),
                    'season_id2': parts[3].strip(),
                    'season_name': parts[4].strip(),
                    'division_name': parts[5].strip(),
                    'season_type': parts[6].strip(),
                    'display_name': text
                })
            except (IndexError, ValueError):
                # Skip malformed entries
                continue
    
    return divisions

