#!/usr/bin/env python3
"""
Team matching candidates for manual review.

This module provides functionality to generate candidate matches for teams,
allowing manual review to learn correct parsing patterns.
"""
from typing import List, Dict, Any, Optional
from pony.orm import db_session, select
from models import Team, TeamSeason, Division
from team_name_parser import parse_team_name, extract_base_identifier
from db_pony import TeamMatcher


@db_session
def get_matching_candidates(team_name: str) -> Dict[str, Any]:
    """
    Get multiple candidate matches for a team name for manual review.
    
    Returns various matching options based on different strategies:
    1. Exact name match
    2. Parsed birth year + gender + club match
    3. Base identifier match (without designation)
    4. Fuzzy string match
    
    Parameters
    ----------
    team_name : str
        Team name to find candidates for
        
    Returns
    -------
    Dict[str, Any]
        Dictionary containing:
        - original_name: str
        - parsed: Dict - parsed team name data
        - candidates: List[Dict] - candidate matches with confidence scores
        - recommended_match: Optional[int] - index of recommended match
    """
    # Parse the team name
    parsed = parse_team_name(team_name)
    
    candidates: List[Dict[str, Any]] = []
    
    # Strategy 1: Exact canonical name match
    normalized = TeamMatcher.normalize_name(team_name)
    exact_match = Team.get(canonical_name=normalized)
    if exact_match:
        candidates.append({
            'team': exact_match,
            'match_type': 'exact_name',
            'confidence': 100,
            'reason': 'Exact canonical name match'
        })
    
    # Strategy 2: Birth year + gender + club match
    if parsed.get('parsed') and parsed.get('birth_year') and parsed.get('gender'):
        birth_year = parsed['birth_year']
        gender = parsed['gender']
        club_name = parsed.get('club_name')
        
        if club_name:
            matched = TeamMatcher.find_team_by_birth_year(
                birth_year, gender, club_name, parsed.get('designation')
            )
            if matched and matched not in [c['team'] for c in candidates if 'team' in c]:
                confidence = 95
                if parsed.get('designation') and matched.designation:
                    if matched.designation.upper() == parsed['designation'].upper():
                        confidence = 100
                candidates.append({
                    'team': matched,
                    'match_type': 'birth_year_club',
                    'confidence': confidence,
                    'reason': f'Birth year {birth_year}, {gender}, club {club_name} match'
                })
    
    # Strategy 3: Base identifier match (without designation)
    if parsed.get('parsed') and parsed.get('birth_year') and parsed.get('gender'):
        base_id = extract_base_identifier(parsed)
        if base_id:
            # Find teams with matching base identifier
            base_teams = list(select(
                t for t in Team
                if t.birth_year == parsed['birth_year']
                and t.gender == parsed['gender']
                and t.base_club_name == TeamMatcher.normalize_name(parsed.get('club_name', ''))
            ))
            
            for team in base_teams:
                if team not in [c['team'] for c in candidates if 'team' in c]:
                    confidence = 85
                    if not parsed.get('designation') and not team.designation:
                        confidence = 90
                    candidates.append({
                        'team': team,
                        'match_type': 'base_identifier',
                        'confidence': confidence,
                        'reason': 'Base identifier match (designation may differ)'
                    })
    
    # Strategy 4: Fuzzy string matching
    all_teams = list(select(t for t in Team))
    if all_teams:
        from thefuzz import fuzz, process
        matches = process.extract(
            normalized,
            [t.canonical_name for t in all_teams],
            scorer=fuzz.ratio,
            limit=5
        )
        
        for matched_name, score, _ in matches:
            if score >= 75:  # Lower threshold for candidates
                matched_team = next((t for t in all_teams if t.canonical_name == matched_name), None)
                if matched_team and matched_team not in [c['team'] for c in candidates if 'team' in c]:
                    candidates.append({
                        'team': matched_team,
                        'match_type': 'fuzzy',
                        'confidence': score,
                        'reason': f'Fuzzy string match ({score}% similarity)'
                    })
    
    # Sort candidates by confidence (highest first)
    candidates.sort(key=lambda x: x['confidence'], reverse=True)
    
    # Determine recommended match (highest confidence, or first if multiple 100% matches)
    recommended = None
    if candidates:
        # Prefer exact matches or birth_year_club matches
        high_confidence = [i for i, c in enumerate(candidates) if c['confidence'] >= 90]
        if high_confidence:
            # Prefer birth_year_club or exact_name over others
            preferred = [i for i in high_confidence 
                        if candidates[i]['match_type'] in ['exact_name', 'birth_year_club']]
            if preferred:
                recommended = preferred[0]
            else:
                recommended = high_confidence[0]
        else:
            recommended = 0
    
    return {
        'original_name': team_name,
        'parsed': parsed,
        'candidates': [
            {
                'team_id': c['team'].id,
                'team_name': c['team'].canonical_name,
                'birth_year': c['team'].birth_year,
                'gender': c['team'].gender,
                'club': c['team'].club.name if c['team'].club else None,
                'designation': c['team'].designation,
                'match_type': c['match_type'],
                'confidence': c['confidence'],
                'reason': c['reason'],
                'seasons_count': len(c['team'].seasons)
            }
            for c in candidates
        ],
        'recommended_match': recommended
    }


@db_session
def get_teams_needing_review(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get teams that might need manual review for matching.
    
    Finds teams that:
    - Have parsed data but no matched team
    - Have multiple potential matches
    - Have unusual name patterns
    
    Parameters
    ----------
    limit : int
        Maximum number of teams to return
        
    Returns
    -------
    List[Dict[str, Any]]
        List of teams with candidate matches for review
    """
    # Get all TeamSeason records
    team_seasons = list(select(
        ts for ts in TeamSeason
    ).limit(limit * 10))  # Get more to filter
    
    # Group by unique team names
    unique_names = {}
    for ts in team_seasons:
        name = ts.team_name
        if name not in unique_names:
            unique_names[name] = {
                'team_name': name,
                'team_entity': ts.team,
                'appearances': []
            }
        unique_names[name]['appearances'].append({
            'season': ts.division.season.season_name,
            'division': ts.division.division_name
        })
    
    # For each unique name, get candidates
    review_list = []
    for name, data in list(unique_names.items())[:limit]:
        candidates = get_matching_candidates(name)
        if len(candidates['candidates']) > 1 or candidates['recommended_match'] is None:
            review_list.append({
                'team_name': name,
                'appearances': data['appearances'],
                'candidates': candidates['candidates'],
                'recommended_match': candidates['recommended_match'],
                'parsed': candidates['parsed']
            })
    
    return review_list

