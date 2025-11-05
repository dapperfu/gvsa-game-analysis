#!/usr/bin/env python3
"""
Team progression tracking across age groups.

This module provides functionality to track teams through age group progression
(U10 -> U11 -> U12 -> U13 -> U14) across multiple seasons, understanding that
teams may change roster but essentially remain the same team as players age.
"""
from typing import List, Dict, Any, Optional, Set, Tuple
import re
from pony.orm import db_session, select
from .models import db, Team, TeamSeason, Division, Season
from .age_progression import calculate_age_group, extract_season_year


def extract_age_group(division_name: str) -> Optional[Tuple[int, int]]:
    """
    Extract age group from division name.
    
    Handles formats like:
    - "U10 Boys 1st Division" -> (10, 10)
    - "U11 Girls 2nd Division" -> (11, 11)
    - "U15/16 Boys Elite" -> (15, 16)
    - "U17/19 Girls" -> (17, 19)
    
    Parameters
    ----------
    division_name : str
        Division name to parse
        
    Returns
    -------
    Optional[Tuple[int, int]]
        (min_age, max_age) tuple, or None if no age group found
    """
    # Match patterns like U10, U11, U15/16, U17/19
    # Pattern 1: U15/16 or U17/19 (range)
    range_pattern = r'U(\d{1,2})/(\d{1,2})'
    match = re.search(range_pattern, division_name)
    if match:
        min_age = int(match.group(1))
        max_age = int(match.group(2))
        return (min_age, max_age)
    
    # Pattern 2: U10, U11, U12, etc. (single age)
    single_pattern = r'U(\d{1,2})\b'
    match = re.search(single_pattern, division_name)
    if match:
        age = int(match.group(1))
        return (age, age)
    
    return None


def get_age_group_label(age_group: Optional[Tuple[int, int]]) -> str:
    """
    Get a human-readable label for an age group.
    
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


@db_session
def track_team_progression(team: Optional[Team] = None, 
                          club_name: Optional[str] = None,
                          min_age: int = 10,
                          max_age: int = 14) -> List[Dict[str, Any]]:
    """
    Track team progression through age groups across seasons.
    
    This function finds teams that appear in multiple age groups over time,
    showing how teams progress from U10 through U14 (or specified range).
    
    Parameters
    ----------
    team : Optional[Team]
        Specific team to track. If None, tracks all teams.
    club_name : Optional[str]
        Filter by club name. If specified, only tracks teams from this club.
    min_age : int
        Minimum age group to include (default: 10)
    max_age : int
        Maximum age group to include (default: 14)
        
    Returns
    -------
    List[Dict[str, Any]]
        List of progression records, each containing:
        - team_id: int
        - team_name: str
        - club_name: Optional[str]
        - progression: List[Dict] with age_group, season, division info
    """
    # Build query
    if team:
        teams_query = [team]
    elif club_name:
        from .db_pony import TeamMatcher
        normalized_club = TeamMatcher.normalize_name(club_name)
        teams_query = list(select(t for t in Team if t.club and 
                                 t.club.canonical_name == normalized_club))
    else:
        teams_query = list(select(t for t in Team))
    
    progressions: List[Dict[str, Any]] = []
    
    for team_obj in teams_query:
        # Get all TeamSeason records for this team
        team_seasons = list(select(ts for ts in TeamSeason if ts.team == team_obj))
        
        if not team_seasons:
            continue
        
        # Build progression map: age_group -> list of appearances
        progression_map: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
        
        for team_season in team_seasons:
            division = team_season.division
            age_group = extract_age_group(division.division_name)
            
            # Filter by age range if specified
            if age_group:
                age_min, age_max = age_group
                # Check if this age group overlaps with our range of interest
                if age_max < min_age or age_min > max_age:
                    continue
            
            if not age_group:
                continue
            
            if age_group not in progression_map:
                progression_map[age_group] = []
            
            progression_map[age_group].append({
                'season': division.season.season_name,
                'year': division.season.year,
                'season_type': division.season.season_type,
                'division_name': division.division_name,
                'division_id': division.id,
                'team_name': team_season.team_name,
                'wins': team_season.wins,
                'losses': team_season.losses,
                'ties': team_season.ties,
                'points': team_season.points,
                'goals_for': team_season.goals_for,
                'goals_against': team_season.goals_against,
            })
        
        # Only include teams that appear in multiple age groups
        if len(progression_map) < 2:
            continue
        
        # Sort progression by age group
        sorted_ages = sorted(progression_map.keys())
        
        progression_data = []
        for age_group in sorted_ages:
            # Sort appearances within each age group by season
            appearances = sorted(progression_map[age_group], 
                              key=lambda x: (x['year'], x['season_type']))
            progression_data.append({
                'age_group': get_age_group_label(age_group),
                'age_min': age_group[0],
                'age_max': age_group[1],
                'appearances': appearances
            })
        
        progressions.append({
            'team_id': team_obj.id,
            'team_name': team_obj.canonical_name,
            'club_name': team_obj.club.name if team_obj.club else None,
            'progression': progression_data,
            'age_groups_played': len(progression_map),
            'total_seasons': len(team_seasons)
        })
    
    # Sort by number of age groups played (most diverse first)
    progressions.sort(key=lambda x: (x['age_groups_played'], x['total_seasons']), 
                     reverse=True)
    
    return progressions


@db_session
def get_teams_by_age_group(age_group: Tuple[int, int], 
                          gender: Optional[str] = None) -> List[TeamSeason]:
    """
    Get all teams that played in a specific age group.
    
    Parameters
    ----------
    age_group : Tuple[int, int]
        Age group (min_age, max_age)
    gender : Optional[str]
        Filter by gender ("Boys" or "Girls"). If None, returns all.
        
    Returns
    -------
    List[TeamSeason]
        List of TeamSeason records for teams in this age group
    """
    min_age, max_age = age_group
    age_label = get_age_group_label(age_group)
    
    # Find divisions matching this age group
    divisions = list(select(d for d in Division if age_label in d.division_name))
    
    # Filter by gender if specified
    if gender:
        divisions = [d for d in divisions if gender in d.division_name]
    
    # Get all team seasons for these divisions
    team_seasons = list(select(ts for ts in TeamSeason 
                               if ts.division in divisions))
    
    return team_seasons


@db_session
def find_team_progression_path(team_name: str) -> Optional[Dict[str, Any]]:
    """
    Find the progression path for a specific team by name.
    
    Parameters
    ----------
    team_name : str
        Team name to search for
        
    Returns
    -------
    Optional[Dict[str, Any]]
        Progression data for the team, or None if not found
    """
    from db_pony import TeamMatcher
    
    # Find matching team
    normalized = TeamMatcher.normalize_name(team_name)
    team = Team.get(canonical_name=normalized)
    
    if not team:
        # Try fuzzy matching
        all_teams = list(select(t for t in Team))
        matched = TeamMatcher.find_matching_team(team_name, all_teams)
        if matched:
            team = matched
        else:
            return None
    
    progressions = track_team_progression(team=team)
    if progressions:
        return progressions[0]
    
    return None


@db_session
def build_team_record_across_seasons(birth_year: int, gender: str, club_name: str) -> Dict[str, Any]:
    """
    Build comprehensive team record showing progression across seasons.
    
    Shows how a team progresses through age groups:
    - U11 in 2020 -> U12 in 2021 -> U13 in 2022, etc.
    Includes all divisions, statistics, and matches.
    
    Parameters
    ----------
    birth_year : int
        Birth year of the players
    gender : str
        "Boys" or "Girls"
    club_name : str
        Club name
        
    Returns
    -------
    Dict[str, Any]
        Comprehensive team record with:
        - birth_year: int
        - gender: str
        - club_name: str
        - team_entity: Optional[Team]
        - seasons: List[Dict] - chronological list of seasons with:
            - season_name: str
            - year_season: str
            - season_type: str
            - expected_age_group: str
            - actual_divisions: List[Dict] - divisions they played in
            - stats: Dict - aggregated statistics
    """
    from db_pony import TeamMatcher
    
    normalized_club = TeamMatcher.normalize_name(club_name)
    
    # Find team(s) matching birth year, gender, and club
    teams = list(select(
        t for t in Team
        if t.birth_year == birth_year
        and t.gender == gender
        and t.base_club_name == normalized_club
    ))
    
    if not teams:
        return {
            'birth_year': birth_year,
            'gender': gender,
            'club_name': club_name,
            'team_entity': None,
            'seasons': []
        }
    
    # Use the first matching team (or combine if multiple)
    team = teams[0]
    
    # Get all TeamSeason records for this team, ordered chronologically
    team_seasons = list(select(
        ts for ts in TeamSeason
        if ts.team == team
    ))
    
    # Sort by season (year, season_type)
    # Note: season_type is now an enum, but comparison still works
    team_seasons.sort(key=lambda ts: (
        ts.division.season.year,
        ts.division.season.season_type
    ))
    
    # Group by season and build record
    season_records: Dict[str, Dict[str, Any]] = {}
    
    for team_season in team_seasons:
        division = team_season.division
        season = division.season
        
        # Create season key
        season_key = f"{season.year}_{season.season_type}"
        
        if season_key not in season_records:
            # Calculate expected age group for this season
            season_year = extract_season_year(season)
            expected_age_group = None
            if season_year:
                season_type_str = season.season_type
                age_group_tuple = calculate_age_group(birth_year, season_year, season_type_str)
                if age_group_tuple:
                    expected_age_group = get_age_group_label(age_group_tuple)
            
            season_records[season_key] = {
                'season_name': season.season_name,
                'year': season.year,
                'season_type': season.season_type,
                'expected_age_group': expected_age_group,
                'actual_divisions': [],
                'stats': {
                    'total_wins': 0,
                    'total_losses': 0,
                    'total_ties': 0,
                    'total_points': 0,
                    'total_goals_for': 0,
                    'total_goals_against': 0,
                    'matches_played': 0
                }
            }
        
        # Add division info
        actual_age_group = extract_age_group(division.division_name)
        season_records[season_key]['actual_divisions'].append({
            'division_name': division.division_name,
            'age_group': get_age_group_label(actual_age_group) if actual_age_group else None,
            'team_name': team_season.team_name,
            'wins': team_season.wins,
            'losses': team_season.losses,
            'ties': team_season.ties,
            'points': team_season.points,
            'goals_for': team_season.goals_for,
            'goals_against': team_season.goals_against
        })
        
        # Aggregate stats
        stats = season_records[season_key]['stats']
        stats['total_wins'] += team_season.wins
        stats['total_losses'] += team_season.losses
        stats['total_ties'] += team_season.ties
        stats['total_points'] += team_season.points
        stats['total_goals_for'] += team_season.goals_for
        stats['total_goals_against'] += team_season.goals_against
        
        # Count matches
        stats['matches_played'] += len(team_season.home_matches) + len(team_season.away_matches)
    
    # Convert to sorted list
    seasons_list = sorted(
        season_records.values(),
        key=lambda x: (x['year'], x['season_type'])
    )
    
    return {
        'birth_year': birth_year,
        'gender': gender,
        'club_name': club_name,
        'team_entity': team,
        'seasons': seasons_list,
        'total_seasons': len(seasons_list),
        'age_groups_played': len(set(
            get_age_group_label(extract_age_group(div['division_name']))
            for season in seasons_list
            for div in season['actual_divisions']
            if extract_age_group(div['division_name'])
        ))
    }


@db_session
def find_team_lineage(team: Team) -> List[TeamSeason]:
    """
    Find all TeamSeason records for a team, ordered chronologically.
    
    Shows how team progressed through age groups over time.
    
    Parameters
    ----------
    team : Team
        Team entity
        
    Returns
    -------
    List[TeamSeason]
        List of TeamSeason records, ordered chronologically
    """
    team_seasons = list(select(
        ts for ts in TeamSeason
        if ts.team == team
    ))
    
    # Sort by season (year, season_type), then by division name
    # Note: season_type is now an enum, but comparison still works
    team_seasons.sort(key=lambda ts: (
        ts.division.season.year,
        ts.division.season.season_type,
        ts.division.division_name
    ))
    
    return team_seasons

