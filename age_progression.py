#!/usr/bin/env python3
"""
Age group progression calculator for tracking teams across seasons.

This module calculates expected age groups based on birth year and season,
accounting for age cutoff dates and seasonal progression.
"""
from typing import Optional, Tuple, List
from datetime import datetime
from pony.orm import db_session, select
from models import Season, Division


# Age cutoff date: typically August 1 for US soccer
# Players must be age X on or before Aug 1 to play in U(X+1) age group
AGE_CUTOFF_MONTH = 8
AGE_CUTOFF_DAY = 1


def calculate_age_group(birth_year: int, season_year: int, season_type: str) -> Optional[Tuple[int, int]]:
    """
    Calculate expected age group (U-age) based on birth year and season.
    
    Age cutoff logic:
    - Age cutoff is typically Aug 1
    - For Fall season: Use Aug 1 of the season start year
    - For Spring season: Use Aug 1 of the previous calendar year (since Spring follows Fall)
    
    Examples:
    - Fall 2020, birth year 2013 -> Age 7 on Aug 1, 2020 -> U8 (turns 8 during season)
    - Spring 2021, birth year 2013 -> Age 7 on Aug 1, 2020 -> U8 (same age group as Fall 2020)
    - Fall 2021, birth year 2013 -> Age 8 on Aug 1, 2021 -> U9 (age up from previous year)
    
    Parameters
    ----------
    birth_year : int
        Birth year of the players
    season_year : int
        Year of the season (extract from year_season or season_name)
    season_type : str
        "F" for Fall, "S" for Spring
        
    Returns
    -------
    Optional[Tuple[int, int]]
        (min_age, max_age) tuple representing age group, or None if calculation fails
    """
    # Normalize season_type to handle enum values or strings
    if isinstance(season_type, str):
        season_type_upper = season_type.upper()
    else:
        # Handle enum
        season_type_upper = str(season_type).upper()
    
    # Determine the cutoff date to use
    if season_type_upper in ('F', 'FALL'):
        # Fall season: use Aug 1 of the season start year
        cutoff_year = season_year
    elif season_type_upper in ('S', 'SPRING'):
        # Spring season: use Aug 1 of the previous calendar year
        # (Spring 2021 uses Aug 1, 2020 cutoff)
        cutoff_year = season_year - 1
    else:
        # Default to season year if unknown
        cutoff_year = season_year
    
    # Calculate age on Aug 1 of cutoff year
    age_on_cutoff = cutoff_year - birth_year
    
    # Age group is U(age + 1) because players turn that age during the season
    # e.g., age 7 on Aug 1 -> U8 (they turn 8 during the season)
    u_age = age_on_cutoff + 1
    
    # Validate reasonable age range (U5 to U19)
    if u_age < 5 or u_age > 19:
        return None
    
    return (u_age, u_age)


def extract_season_year(season: Season) -> Optional[int]:
    """
    Extract the primary year from a season object.
    
    Parameters
    ----------
    season : Season
        Season entity
        
    Returns
    -------
    Optional[int]
        Primary year of the season, or None if extraction fails
    """
    # Try to extract from year_season (e.g., "2020/2021" -> 2020)
    if season.year_season:
        year_match = season.year_season.split('/')[0]
        try:
            return int(year_match)
        except ValueError:
            pass
    
    # Try to extract from season_name (e.g., "Fall 2020" -> 2020)
    if season.season_name:
        import re
        year_match = re.search(r'\b(20\d{2})\b', season.season_name)
        if year_match:
            try:
                return int(year_match.group(1))
            except ValueError:
                pass
    
    return None


@db_session
def find_expected_divisions(birth_year: int, gender: str, season: Season) -> List[Division]:
    """
    Find divisions matching expected age group and gender for a team.
    
    Parameters
    ----------
    birth_year : int
        Birth year of the players
    gender : str
        "Boys" or "Girls"
    season : Season
        Season to search in
        
    Returns
    -------
    List[Division]
        List of matching divisions
    """
    # Calculate expected age group
    season_year = extract_season_year(season)
    if not season_year:
        return []
    
    season_type_str = season.season_type.value
    age_group = calculate_age_group(birth_year, season_year, season_type_str)
    if not age_group:
        return []
    
    min_age, max_age = age_group
    age_label = f"U{min_age}"
    if min_age != max_age:
        age_label = f"U{min_age}/{max_age}"
    
    # Search for divisions in this season matching age group and gender
    gender_short = gender[0].upper() if gender else None
    
    divisions = list(select(
        d for d in Division
        if d.season == season
        and age_label in d.division_name
        and (gender_short == 'B' and 'Boys' in d.division_name or
             gender_short == 'G' and 'Girls' in d.division_name)
    ))
    
    return divisions


def get_age_group_label(age_group: Optional[Tuple[int, int]]) -> str:
    """
    Get human-readable label for an age group.
    
    Parameters
    ----------
    age_group : Optional[Tuple[int, int]]
        Age group tuple (min_age, max_age)
        
    Returns
    -------
    str
        Age group label (e.g., "U10", "U15/16")
    """
    if not age_group:
        return "Unknown"
    
    min_age, max_age = age_group
    if min_age == max_age:
        return f"U{min_age}"
    else:
        return f"U{min_age}/{max_age}"


