#!/usr/bin/env python3
"""
PonyORM database interface for GVSA soccer data.

This module provides functionality to manage the database using PonyORM,
including team name matching, club detection, and data persistence.
"""
from typing import List, Dict, Any, Optional, Tuple
from pony.orm import db_session, select, commit
import re
from thefuzz import fuzz, process
from models import db, Season, Division, Club, Team, TeamSeason, Match, SeasonType
from team_name_parser import parse_team_name, normalize_team_identifier, extract_base_identifier


class TeamMatcher:
    """
    Matches team names across seasons using fuzzy string matching.
    
    Handles variations in team names and identifies the same team
    across different seasons and age groups.
    """
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Normalize team name for matching.
        
        Parameters
        ----------
        name : str
            Original team name
            
        Returns
        -------
        str
            Normalized name
        """
        # Remove extra whitespace
        name = ' '.join(name.split())
        
        # Convert to lowercase for matching
        normalized = name.lower()
        
        # Remove common suffixes that might vary
        normalized = re.sub(r'\s+fc\s*$', '', normalized)
        normalized = re.sub(r'\s+sc\s*$', '', normalized)
        
        return normalized.strip()
    
    @staticmethod
    def extract_club_name(team_name: str) -> Optional[str]:
        """
        Extract club name from team name.
        
        Examples:
        - "Rapids FC 15B Black" -> "Rapids FC"
        - "NUSC 15B Green" -> "NUSC"
        - "Alliance FC 15 Lobos" -> "Alliance FC"
        
        Parameters
        ----------
        team_name : str
            Team name
            
        Returns
        -------
        Optional[str]
            Extracted club name or None
        """
        # Common patterns: "Club Name [Age] [Color/Name]"
        # Try to extract the club part before age indicators
        
        # Remove common age patterns (U10, U11, 15B, etc.)
        name = re.sub(r'\bU\d{1,2}\b', '', team_name)
        name = re.sub(r'\b\d{1,2}[BG]\b', '', name)  # 15B, 14G, etc.
        name = re.sub(r'\b\d{4}[BG]\b', '', name)  # 2015B, etc.
        name = re.sub(r'\b\d{2}\b', '', name)  # Standalone 2-digit numbers (like "15" in "Alliance FC 15")
        
        # Extract first significant words (likely club name)
        # Look for patterns like "FC", "SC", or common club endings
        words = name.split()
        club_words = []
        
        for word in words:
            # Stop at common color/descriptor words
            if word.lower() in ['black', 'white', 'green', 'blue', 'red', 'yellow',
                               'gold', 'silver', 'elite', 'premier', 'lobos',
                               'rovers', 'wolves', 'eagles', 'hawks']:
                break
            club_words.append(word)
        
        club_name = ' '.join(club_words).strip()
        
        # Clean up
        club_name = re.sub(r'\s+', ' ', club_name)
        club_name = club_name.strip()
        
        if len(club_name) < 2:
            return None
        
        return club_name
    
    @staticmethod
    def parse_team_name(team_name: str) -> Dict[str, Any]:
        """
        Parse team name using NLP parser.
        
        Parameters
        ----------
        team_name : str
            Team name to parse
            
        Returns
        -------
        Dict[str, Any]
            Parsed team data from team_name_parser.parse_team_name()
        """
        return parse_team_name(team_name)
    
    @staticmethod
    def find_matching_team(team_name: str, existing_teams: List[Team]) -> Optional[Team]:
        """
        Find matching team from existing teams using fuzzy matching.
        
        Parameters
        ----------
        team_name : str
            Team name to match
        existing_teams : List[Team]
            List of existing Team entities
            
        Returns
        -------
        Optional[Team]
            Matching team or None if no good match found
        """
        normalized_name = TeamMatcher.normalize_name(team_name)
        
        if not existing_teams:
            return None
        
        # Create list of normalized names for matching
        team_names = [(t.canonical_name, t) for t in existing_teams]
        
        # Use fuzzy matching
        best_match = process.extractOne(
            normalized_name,
            [name for name, _ in team_names],
            scorer=fuzz.ratio
        )
        
        if best_match and best_match[1] >= 85:  # 85% similarity threshold
            matched_name = best_match[0]
            # Find the team object
            for name, team in team_names:
                if name == matched_name:
                    return team
        
        return None
    
    @staticmethod
    def find_team_by_birth_year(birth_year: int, gender: str, club_name: str, 
                                designation: Optional[str] = None) -> Optional[Team]:
        """
        Find team by birth year, gender, club, and optionally designation.
        
        Uses the designation matching rule: if a team exists without designation
        in a previous year, and a team with designation appears in a later year,
        match them as the same team.
        
        NOTE: This method must be called within a db_session context.
        
        Parameters
        ----------
        birth_year : int
            Birth year of the players
        gender : str
            "Boys" or "Girls"
        club_name : str
            Club name
        designation : Optional[str]
            Color/descriptor designation (optional)
            
        Returns
        -------
        Optional[Team]
            Matching team or None if not found
        """
        # Normalize club name
        normalized_club = TeamMatcher.normalize_name(club_name)
        
        # Search for teams with matching birth year, gender, and club
        # NOTE: This requires db_session context (typically called from within @db_session method)
        try:
            candidates = list(select(
                t for t in Team
                if t.birth_year == birth_year
                and t.gender == gender
                and t.base_club_name == normalized_club
            ))
        except Exception:
            # If not in db_session, return None
            return None
        
        if not candidates:
            return None
        
        # If designation provided, prefer exact match
        if designation:
            designation_upper = designation.upper()
            for team in candidates:
                if team.designation and team.designation.upper() == designation_upper:
                    return team
            # If no exact match, return first candidate (designation may have been added)
            # This implements the rule: if team without designation existed before,
            # later team with designation is the same team
            if candidates:
                return candidates[0]
        else:
            # No designation specified - return first match (any designation is fine)
            if candidates:
                return candidates[0]
        
        return None


class GVSA_Database:
    """
    Database interface using PonyORM.
    
    Handles saving standings data with team matching and club detection.
    """
    
    def __init__(self, db_path: str = "gvsa_data.db") -> None:
        """
        Initialize database connection.
        
        Parameters
        ----------
        db_path : str
            Path to SQLite database file
        """
        self.db_path = db_path
        # Check if already bound (in case of multiple instances)
        try:
            # Try to access schema to see if already bound
            _ = db.schema
            # Already bound, just generate mapping if not already done
            if not db.schema:
                db.generate_mapping(create_tables=True)
        except Exception:
            # Not bound, bind and generate mapping
            db.bind(provider='sqlite', filename=db_path, create_db=True)
            db.generate_mapping(create_tables=True)
    
    @db_session
    def get_or_create_season(self, year: int, season_name: str, 
                            season_type: str) -> Season:
        """
        Get or create a season.
        
        Parameters
        ----------
        year : int
            Year (e.g., 2025)
        season_name : str
            Season name (e.g., "Fall 2025")
        season_type : str
            Season type: "Fall" or "Spring" (or "F"/"S" for short)
            
        Returns
        -------
        Season
            Season entity
        """
        # Normalize season_type
        if season_type == 'F' or season_type == 'Fall':
            season_type_str = 'Fall'
        elif season_type == 'S' or season_type == 'Spring':
            season_type_str = 'Spring'
        else:
            raise ValueError(f"Invalid season_type: {season_type}. Must be 'Fall' or 'Spring'")
        
        # Try to get existing season (composite_key ensures uniqueness)
        season = Season.get(year=year, season_type=season_type_str)
        
        if season:
            # Update season_name if it's different (shouldn't happen, but handle it)
            if season.season_name != season_name:
                season.season_name = season_name
                commit()
        else:
            # Create new season
            season = Season(
                year=year,
                season_type=season_type_str,
                season_name=season_name
            )
            commit()
        
        return season
    
    @db_session
    def get_season(self, year: int, season_type: str) -> Optional[Season]:
        """
        Get a season by year and season type.
        
        Simple query: year=2025, season_type="Fall"
        
        Parameters
        ----------
        year : int
            Year (e.g., 2025)
        season_type : str
            Season type: "Fall" or "Spring" (or "F"/"S" for short)
            
        Returns
        -------
        Optional[Season]
            Season entity or None if not found
        """
        # Normalize season_type
        if season_type == 'F' or season_type == 'Fall':
            season_type_str = 'Fall'
        elif season_type == 'S' or season_type == 'Spring':
            season_type_str = 'Spring'
        else:
            raise ValueError(f"Invalid season_type: {season_type}. Must be 'Fall' or 'Spring'")
        
        # Use composite_key to get season directly
        return Season.get(year=year, season_type=season_type_str)
    
    @db_session
    def get_or_create_division(self, division_id: str, division_name: str,
                              season: Season) -> Division:
        """
        Get or create a division.
        
        Parameters
        ----------
        division_id : str
            Division ID
        division_name : str
            Division name
        season : Season
            Season entity
            
        Returns
        -------
        Division
            Division entity
        """
        # Use select() instead of get() to handle multiple matches
        divisions = list(select(
            d for d in Division
            if d.division_id == division_id
            and d.season == season
        ))
        
        if divisions:
            # If multiple divisions exist, return the first one
            division = divisions[0]
        else:
            division = Division(
                division_id=division_id,
                division_name=division_name,
                season=season
            )
            commit()
        
        return division
    
    @db_session
    def get_or_create_club(self, club_name: str) -> Club:
        """
        Get or create a club.
        
        Parameters
        ----------
        club_name : str
            Club name
            
        Returns
        -------
        Club
            Club entity
        """
        normalized = TeamMatcher.normalize_name(club_name)
        
        club = Club.get(canonical_name=normalized)
        
        if not club:
            club = Club(name=club_name, canonical_name=normalized)
            commit()
        
        return club
    
    @db_session
    def get_or_create_team(self, team_name: str) -> Tuple[Team, bool]:
        """
        Get or create a team, matching across seasons if possible.
        
        Uses enhanced parsing to extract birth year, gender, and club information.
        Matches teams by birth year + gender + club when possible.
        
        Parameters
        ----------
        team_name : str
            Team name
            
        Returns
        -------
        Tuple[Team, bool]
            (Team entity, is_new) - True if newly created
        """
        normalized = TeamMatcher.normalize_name(team_name)
        
        # Check for exact match
        team = Team.get(canonical_name=normalized)
        
        if team:
            return team, False
        
        # Parse team name to extract structured information
        parsed = TeamMatcher.parse_team_name(team_name)
        
        # Try matching by birth year + gender + club if we have that data
        if parsed.get('parsed') and parsed.get('birth_year') and parsed.get('gender'):
            birth_year = parsed['birth_year']
            gender = parsed['gender']
            club_name = parsed.get('club_name')
            designation = parsed.get('designation')
            
            if club_name:
                matched_team = TeamMatcher.find_team_by_birth_year(
                    birth_year, gender, club_name, designation
                )
                if matched_team:
                    return matched_team, False
        
        # Try fuzzy matching as fallback
        existing_teams = list(select(t for t in Team))
        matched_team = TeamMatcher.find_matching_team(team_name, existing_teams)
        
        if matched_team:
            return matched_team, False
        
        # Create new team
        team = Team(canonical_name=normalized)
        
        # Store parsed information
        if parsed.get('parsed'):
            if parsed.get('birth_year'):
                team.birth_year = parsed['birth_year']
            if parsed.get('gender'):
                team.gender = parsed['gender']
            if parsed.get('designation'):
                team.designation = parsed['designation']
            if parsed.get('club_name'):
                normalized_club = TeamMatcher.normalize_name(parsed['club_name'])
                team.base_club_name = normalized_club
        
        # Try to associate with a club
        club_name = parsed.get('club_name') or TeamMatcher.extract_club_name(team_name)
        if club_name:
            club = self.get_or_create_club(club_name)
            team.club = club
        
        commit()
        return team, True
    
    @db_session
    def save_standings(self, standings_data: Dict[str, Any]) -> None:
        """
        Save complete standings data.
        
        Parameters
        ----------
        standings_data : Dict[str, Any]
            Standings data including division, teams, and matches
        """
        division_info = standings_data.get('division', {})
        
        # Extract year from season_name (e.g., "Spring 2019" -> 2019)
        season_name = division_info.get('season_name', '')
        year = None
        if season_name:
            import re
            year_match = re.search(r'\b(20\d{2})\b', season_name)
            if year_match:
                try:
                    year = int(year_match.group(1))
                except ValueError:
                    pass
        
        if year is None:
            # Fallback: try to extract from year_season if still present
            year_season = division_info.get('year_season', '')
            if year_season:
                year_str = year_season.split('/')[0] if '/' in year_season else year_season
                try:
                    year = int(year_str)
                except ValueError:
                    pass
        
        if year is None:
            raise ValueError(f"Could not extract year from division info: {division_info}")
        
        # Get normalized season_type
        season_type_str = division_info.get('season_type', 'Fall')
        # Normalize if it's "F" or "S"
        if season_type_str == 'F':
            season_type_str = 'Fall'
        elif season_type_str == 'S':
            season_type_str = 'Spring'
        # Also check season_name to ensure correctness
        elif 'Spring' in season_name or 'spring' in season_name.lower():
            season_type_str = 'Spring'
        elif 'Fall' in season_name or 'fall' in season_name.lower():
            season_type_str = 'Fall'
        
        # Get or create season (will convert to enum internally)
        season = self.get_or_create_season(
            year,
            season_name,
            season_type_str
        )
        
        # Get or create division
        division = self.get_or_create_division(
            division_info.get('division_id', ''),
            division_info.get('division_name', ''),
            season
        )
        
        # Process teams
        teams_data = standings_data.get('teams', [])
        team_seasons = {}
        
        for team_data in teams_data:
            team_name = team_data['team_name']
            team, _ = self.get_or_create_team(team_name)
            
            # Create or update TeamSeason
            # Use select() instead of get() to handle multiple matches
            team_seasons_list = list(select(
                ts for ts in TeamSeason
                if ts.team == team and ts.division == division
            ))
            team_season = team_seasons_list[0] if team_seasons_list else None
            if not team_season:
                team_season = TeamSeason(
                    team=team,
                    division=division,
                    team_name=team_name,
                    wins=team_data.get('wins', 0),
                    losses=team_data.get('losses', 0),
                    ties=team_data.get('ties', 0),
                    forfeits=team_data.get('forfeits', 0),
                    points=team_data.get('points', 0),
                    goals_for=team_data.get('goals_for', 0),
                    goals_against=team_data.get('goals_against', 0),
                    goal_differential=team_data.get('goal_differential', 0)
                )
            else:
                # Update existing
                team_season.wins = team_data.get('wins', 0)
                team_season.losses = team_data.get('losses', 0)
                team_season.ties = team_data.get('ties', 0)
                team_season.forfeits = team_data.get('forfeits', 0)
                team_season.points = team_data.get('points', 0)
                team_season.goals_for = team_data.get('goals_for', 0)
                team_season.goals_against = team_data.get('goals_against', 0)
                team_season.goal_differential = team_data.get('goal_differential', 0)
            
            team_seasons[team_name] = team_season
        
        commit()
        
        # Process matches
        matches_data = standings_data.get('matches', [])
        for match_data in matches_data:
            home_team_name = match_data['home_team']
            away_team_name = match_data['away_team']
            
            home_team_season = team_seasons.get(home_team_name)
            away_team_season = team_seasons.get(away_team_name)
            
            if not home_team_season or not away_team_season:
                # Teams might not be in standings, try to find them
                if not home_team_season:
                    home_team, _ = self.get_or_create_team(home_team_name)
                    home_team_seasons_list = list(select(
                        ts for ts in TeamSeason
                        if ts.team == home_team and ts.division == division
                    ))
                    home_team_season = home_team_seasons_list[0] if home_team_seasons_list else None
                    if not home_team_season:
                        home_team_season = TeamSeason(
                            team=home_team,
                            division=division,
                            team_name=home_team_name
                        )
                        team_seasons[home_team_name] = home_team_season
                
                if not away_team_season:
                    away_team, _ = self.get_or_create_team(away_team_name)
                    away_team_seasons_list = list(select(
                        ts for ts in TeamSeason
                        if ts.team == away_team and ts.division == division
                    ))
                    away_team_season = away_team_seasons_list[0] if away_team_seasons_list else None
                    if not away_team_season:
                        away_team_season = TeamSeason(
                            team=away_team,
                            division=division,
                            team_name=away_team_name
                        )
                        team_seasons[away_team_name] = away_team_season
            
            # Create match
            match = Match(
                division=division,
                date=match_data.get('date', ''),
                time=match_data.get('time'),
                home_team=home_team_season,
                away_team=away_team_season,
                field=match_data.get('field'),
                home_score=match_data.get('home_score'),
                away_score=match_data.get('away_score'),
                status=match_data.get('status', 'scheduled')
            )
        
        commit()
        print(f"  - Saved to database (division_id: {division.id})")

