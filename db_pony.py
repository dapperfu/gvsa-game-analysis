#!/usr/bin/env python3
"""
PonyORM database interface for GVSA soccer data.

This module provides functionality to manage the database using PonyORM,
including team name matching, club detection, and data persistence.
"""
from typing import List, Dict, Any, Optional, Tuple
from pony.orm import db_session, select, get, commit
import re
from thefuzz import fuzz, process
from models import db, Season, Division, Club, Team, TeamSeason, Match


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
            db.bind(provider='sqlite', filename=db_path, create_db=True)
            db.generate_mapping(create_tables=True)
        except Exception:
            # Already bound, just generate mapping
            db.generate_mapping(create_tables=True)
    
    @db_session
    def get_or_create_season(self, year_season: str, season_name: str, 
                            season_type: str) -> Season:
        """
        Get or create a season.
        
        Parameters
        ----------
        year_season : str
            Year range (e.g., "2025/2026")
        season_name : str
            Season name (e.g., "Fall 2025")
        season_type : str
            Season type (e.g., "F")
            
        Returns
        -------
        Season
            Season entity
        """
        season = Season.get(
            year_season=year_season,
            season_name=season_name,
            season_type=season_type
        )
        
        if not season:
            season = Season(
                year_season=year_season,
                season_name=season_name,
                season_type=season_type
            )
            commit()
        
        return season
    
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
        division = Division.get(
            division_id=division_id,
            season=season
        )
        
        if not division:
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
        
        # Try fuzzy matching
        existing_teams = list(select(t for t in Team))
        matched_team = TeamMatcher.find_matching_team(team_name, existing_teams)
        
        if matched_team:
            return matched_team, False
        
        # Create new team
        team = Team(canonical_name=normalized)
        
        # Try to associate with a club
        club_name = TeamMatcher.extract_club_name(team_name)
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
        
        # Get or create season
        season = self.get_or_create_season(
            division_info.get('year_season', ''),
            division_info.get('season_name', ''),
            division_info.get('season_type', '')
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
            team_season = TeamSeason.get(team=team, division=division)
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
                    home_team_season = TeamSeason.get(team=home_team, division=division)
                    if not home_team_season:
                        home_team_season = TeamSeason(
                            team=home_team,
                            division=division,
                            team_name=home_team_name
                        )
                        team_seasons[home_team_name] = home_team_season
                
                if not away_team_season:
                    away_team, _ = self.get_or_create_team(away_team_name)
                    away_team_season = TeamSeason.get(team=away_team, division=division)
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

