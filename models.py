#!/usr/bin/env python3
"""
PonyORM database models for GVSA soccer data.

This module defines the database schema using PonyORM to track teams,
divisions, matches, clubs, and team progression across seasons.
"""
from pony.orm import Database, Required, Optional, Set, PrimaryKey
from datetime import datetime


# Initialize database
db = Database()


class Season(db.Entity):
    """
    Represents a soccer season (e.g., "Fall 2025", "Spring 2026").
    
    Attributes
    ----------
    year_season : str
        Year range (e.g., "2025/2026")
    season_name : str
        Season name (e.g., "Fall 2025")
    season_type : str
        Season type (e.g., "F" for Fall, "S" for Spring)
    divisions : Set[Division]
        Divisions in this season
    scraped_at : datetime
        When this season was scraped
    """
    id = PrimaryKey(int, auto=True)
    year_season = Required(str)
    season_name = Required(str)
    season_type = Required(str)
    divisions = Set('Division')
    scraped_at = Required(datetime, default=datetime.now)
    
    def __str__(self) -> str:
        return f"{self.season_name} ({self.year_season})"


class Division(db.Entity):
    """
    Represents a division within a season (e.g., "U11 Boys 5th Division").
    
    Attributes
    ----------
    division_id : str
        Original division ID from website
    division_name : str
        Division name (e.g., "U11 Boys 5th Division")
    season : Season
        The season this division belongs to
    teams : Set[TeamSeason]
        Teams in this division
    matches : Set[Match]
        Matches in this division
    scraped_at : datetime
        When this division was scraped
    """
    id = PrimaryKey(int, auto=True)
    division_id = Required(str)
    division_name = Required(str)
    season = Required(Season)
    teams = Set('TeamSeason')
    matches = Set('Match')
    scraped_at = Required(datetime, default=datetime.now)
    
    def __str__(self) -> str:
        return f"{self.division_name} - {self.season}"


class Club(db.Entity):
    """
    Represents a soccer club (e.g., "NUSC", "Rapids FC").
    
    Clubs are detected from team names and can have multiple teams across
    different ages and seasons.
    
    Attributes
    ----------
    name : str
        Club name
    canonical_name : str
        Normalized canonical name for matching
    teams : Set[Team]
        Teams associated with this club
    """
    id = PrimaryKey(int, auto=True)
    name = Required(str, unique=True)
    canonical_name = Required(str, unique=True)  # Normalized for matching
    teams = Set('Team')
    
    def __str__(self) -> str:
        return self.name


class Team(db.Entity):
    """
    Represents a team entity that persists across seasons.
    
    Teams are matched across seasons using NLP to handle name variations.
    For example, "Rapids FC 15B Black" in U11 might be the same team as
    "Rapids FC 15B Black" in U12 (age progression).
    
    Attributes
    ----------
    canonical_name : str
        Normalized canonical name for matching
    club : Optional[Club]
        The club this team belongs to
    seasons : Set[TeamSeason]
        Team appearances across different seasons
    """
    id = PrimaryKey(int, auto=True)
    canonical_name = Required(str, unique=True)
    club = Optional(Club)
    seasons = Set('TeamSeason')
    
    def __str__(self) -> str:
        return self.canonical_name


class TeamSeason(db.Entity):
    """
    Represents a team's participation in a specific division/season.
    
    This links teams to divisions and stores their season-specific statistics.
    
    Attributes
    ----------
    team : Team
        The team entity
    division : Division
        The division this team played in
    team_name : str
        The exact name as it appeared in that season
    wins : int
        Number of wins
    losses : int
        Number of losses
    ties : int
        Number of ties
    forfeits : int
        Number of forfeits
    points : int
        Total points
    goals_for : int
        Goals scored
    goals_against : int
        Goals conceded
    goal_differential : int
        Goal differential
    scraped_at : datetime
        When this record was scraped
    """
    id = PrimaryKey(int, auto=True)
    team = Required(Team)
    division = Required(Division)
    team_name = Required(str)
    wins = Required(int, default=0)
    losses = Required(int, default=0)
    ties = Required(int, default=0)
    forfeits = Required(int, default=0)
    points = Required(int, default=0)
    goals_for = Required(int, default=0)
    goals_against = Required(int, default=0)
    goal_differential = Required(int, default=0)
    scraped_at = Required(datetime, default=datetime.now)
    
    def __str__(self) -> str:
        return f"{self.team_name} in {self.division}"


class Match(db.Entity):
    """
    Represents a soccer match.
    
    Attributes
    ----------
    division : Division
        The division this match belongs to
    date : str
        Match date
    time : str
        Match time
    home_team : TeamSeason
        Home team
    away_team : TeamSeason
        Away team
    field : Optional[str]
        Field name
    home_score : Optional[int]
        Home team score
    away_score : Optional[int]
        Away team score
    status : str
        Match status (scheduled/completed)
    scraped_at : datetime
        When this match was scraped
    """
    id = PrimaryKey(int, auto=True)
    division = Required(Division)
    date = Required(str)
    time = Optional(str)
    home_team = Required(TeamSeason)
    away_team = Required(TeamSeason)
    field = Optional(str)
    home_score = Optional(int)
    away_score = Optional(int)
    status = Required(str, default='scheduled')
    scraped_at = Required(datetime, default=datetime.now)
    
    def __str__(self) -> str:
        return f"{self.home_team.team_name} vs {self.away_team.team_name} ({self.date})"

