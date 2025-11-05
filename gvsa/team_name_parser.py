#!/usr/bin/env python3
"""
Natural Language Processing for parsing team names.

This module provides comprehensive parsing of team names to extract:
- Club name (e.g., "PASS FC", "Holland Rovers")
- Birth year (e.g., 2013 from "2013B")
- Gender (Boys/Girls from "B"/"G")
- Designation/color (e.g., "Red", "White", "Green", "Black", "Navy")
"""
from typing import Dict, Any, Optional, List
import re


def parse_team_name(team_name: str) -> Dict[str, Any]:
    """
    Parse a team name to extract structured information.
    
    Handles patterns like:
    - "2013B" -> birth_year=2013, gender="Boys"
    - "2010G" -> birth_year=2010, gender="Girls"
    - "PASS FC 2013B - White" -> club="PASS FC", birth_year=2013, gender="Boys", designation="White"
    - "Aguilas 2013B - Rovers" -> club="Aguilas", birth_year=2013, gender="Boys", designation="Rovers"
    - "CATS FC '04 BLACK" -> club="CATS FC", birth_year=2004, gender="Boys", designation="BLACK"
    
    Parameters
    ----------
    team_name : str
        Original team name to parse
        
    Returns
    -------
    Dict[str, Any]
        Dictionary containing:
        - club_name: Optional[str] - Extracted club name
        - birth_year: Optional[int] - Birth year (e.g., 2013)
        - gender: Optional[str] - "Boys" or "Girls"
        - designation: Optional[str] - Color/descriptor (e.g., "Red", "White")
        - original_name: str - Original team name
        - parsed: bool - Whether parsing was successful
    """
    original_name = team_name.strip()
    result: Dict[str, Any] = {
        'club_name': None,
        'birth_year': None,
        'gender': None,
        'designation': None,
        'original_name': original_name,
        'parsed': False
    }
    
    if not team_name or not team_name.strip():
        return result
    
    # Normalize the name for parsing
    name = team_name.strip()
    
    # Pattern 1: Two-digit year with apostrophe (e.g., "'04B", "'13G")
    # Check this first before 4-digit patterns
    apostrophe_pattern = r"'(\d{2})[BG]\b"
    match = re.search(apostrophe_pattern, name, re.IGNORECASE)
    
    if match:
        two_digit = int(match.group(1))
        # Assume years 00-30 are 2000-2030, 31-99 are 1931-1999
        if two_digit <= 30:
            birth_year = 2000 + two_digit
        else:
            birth_year = 1900 + two_digit
        
        result['birth_year'] = birth_year
        
        # Extract gender
        gender_char = name[match.end() - 1].upper()
        if gender_char == 'B':
            result['gender'] = 'Boys'
        elif gender_char == 'G':
            result['gender'] = 'Girls'
        
        # Extract club name
        club_part = name[:match.start()].strip()
        if club_part:
            club_part = re.sub(r'\s+', ' ', club_part)
            club_part = club_part.strip(' -')
            if club_part:
                result['club_name'] = club_part
        
        # Extract designation
        designation_part = name[match.end():].strip()
        if designation_part:
            designation_part = re.sub(r'^[-\s]+', '', designation_part)
            designation_part = designation_part.strip()
            if designation_part:
                result['designation'] = designation_part
        
        result['parsed'] = True
        return result
    
    # Pattern 2: Four-digit year followed by B or G (e.g., "2013B", "2010G")
    year_gender_pattern = r"(\d{4})[BG]\b"
    match = re.search(year_gender_pattern, name, re.IGNORECASE)
    
    if match:
        birth_year = int(match.group(1))
        
        result['birth_year'] = birth_year
        
        # Extract gender from the pattern
        gender_char = name[match.end() - 1].upper()
        if gender_char == 'B':
            result['gender'] = 'Boys'
        elif gender_char == 'G':
            result['gender'] = 'Girls'
        
        # Extract club name (everything before the year pattern)
        club_part = name[:match.start()].strip()
        if club_part:
            # Clean up common prefixes/suffixes
            club_part = re.sub(r'\s+', ' ', club_part)
            club_part = club_part.strip(' -')
            if club_part:
                result['club_name'] = club_part
        
        # Extract designation (everything after the year+gender pattern)
        designation_part = name[match.end():].strip()
        if designation_part:
            # Remove common separators
            designation_part = re.sub(r'^[-\s]+', '', designation_part)
            designation_part = designation_part.strip()
            if designation_part:
                result['designation'] = designation_part
        
        result['parsed'] = True
        return result
    
    # Pattern 3: Two-digit year with apostrophe but no B/G (e.g., "'04 BLACK")
    # Try to infer gender from designation or context
    apostrophe_no_gender = r"'(\d{2})\b"
    match = re.search(apostrophe_no_gender, name)
    if match:
        two_digit = int(match.group(1))
        if two_digit <= 30:
            birth_year = 2000 + two_digit
        else:
            birth_year = 1900 + two_digit
        
        result['birth_year'] = birth_year
        
        # Try to infer gender from context
        name_lower = name.lower()
        if 'boys' in name_lower or ' boy' in name_lower:
            result['gender'] = 'Boys'
        elif 'girls' in name_lower or ' girl' in name_lower:
            result['gender'] = 'Girls'
        
        # Extract club name
        club_part = name[:match.start()].strip()
        if club_part:
            club_part = re.sub(r'\s+', ' ', club_part)
            club_part = club_part.strip(' -')
            if club_part:
                result['club_name'] = club_part
        
        # Extract designation
        designation_part = name[match.end():].strip()
        if designation_part:
            designation_part = re.sub(r'^[-\s]+', '', designation_part)
            designation_part = designation_part.strip()
            if designation_part:
                result['designation'] = designation_part
        
        if result['birth_year']:
            result['parsed'] = True
            return result
    
    # Pattern 4: Try to find just year patterns without explicit B/G
    # Look for 4-digit years that might be birth years (2000-2030 range)
    year_only_pattern = r'\b(20[0-3]\d)\b'
    matches = list(re.finditer(year_only_pattern, name))
    
    if matches:
        # Try to infer gender from context (Boys/Girls in name)
        gender = None
        name_lower = name.lower()
        if 'boys' in name_lower or ' boy' in name_lower:
            gender = 'Boys'
        elif 'girls' in name_lower or ' girl' in name_lower:
            gender = 'Girls'
        
        # Use the most likely birth year (usually the first 4-digit year)
        birth_year = int(matches[0].group(1))
        result['birth_year'] = birth_year
        if gender:
            result['gender'] = gender
        
        # Extract club name
        club_part = name[:matches[0].start()].strip()
        if club_part:
            club_part = re.sub(r'\s+', ' ', club_part)
            club_part = club_part.strip(' -')
            if club_part:
                result['club_name'] = club_part
        
        # Extract designation (after the year)
        designation_part = name[matches[0].end():].strip()
        if designation_part:
            designation_part = re.sub(r'^[-\s]+', '', designation_part)
            designation_part = designation_part.strip()
            if designation_part:
                result['designation'] = designation_part
        
        if result['birth_year']:
            result['parsed'] = True
    
    return result


def normalize_team_identifier(parsed: Dict[str, Any]) -> str:
    """
    Create a canonical identifier for matching teams across seasons.
    
    Combines club + birth_year + gender + designation (if available).
    Used for matching teams that represent the same group of players.
    
    Parameters
    ----------
    parsed : Dict[str, Any]
        Parsed team name data from parse_team_name()
        
    Returns
    -------
    str
        Normalized identifier string
    """
    parts: List[str] = []
    
    # Club name (normalized)
    if parsed.get('club_name'):
        club = parsed['club_name'].strip().upper()
        club = re.sub(r'\s+', ' ', club)
        parts.append(club)
    
    # Birth year
    if parsed.get('birth_year'):
        parts.append(str(parsed['birth_year']))
    
    # Gender
    if parsed.get('gender'):
        gender_short = parsed['gender'][0].upper()  # 'B' or 'G'
        parts.append(gender_short)
    
    # Designation (optional, for differentiation)
    if parsed.get('designation'):
        designation = parsed['designation'].strip().upper()
        designation = re.sub(r'\s+', ' ', designation)
        # Normalize common variations
        designation = re.sub(r'\s*-\s*', '', designation)
        parts.append(designation)
    
    return '|'.join(parts) if parts else parsed.get('original_name', '').upper()


def extract_base_identifier(parsed: Dict[str, Any]) -> str:
    """
    Extract base identifier without designation (for matching teams that may have
    designation added in later years).
    
    Parameters
    ----------
    parsed : Dict[str, Any]
        Parsed team name data from parse_team_name()
        
    Returns
    -------
    str
        Base identifier (club + birth_year + gender, no designation)
    """
    parts: List[str] = []
    
    # Club name
    if parsed.get('club_name'):
        club = parsed['club_name'].strip().upper()
        club = re.sub(r'\s+', ' ', club)
        parts.append(club)
    
    # Birth year
    if parsed.get('birth_year'):
        parts.append(str(parsed['birth_year']))
    
    # Gender
    if parsed.get('gender'):
        gender_short = parsed['gender'][0].upper()
        parts.append(gender_short)
    
    return '|'.join(parts) if parts else parsed.get('original_name', '').upper()

