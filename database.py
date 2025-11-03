#!/usr/bin/env python3
"""
Database module for storing teams and match results.

This module provides functionality to create and manage a SQLite database
for storing scraped team and match result data.
"""
from typing import List, Dict, Any, Optional
import sqlite3
from pathlib import Path
from datetime import datetime


class GVSADatabase:
    """
    Database interface for GVSA soccer data.
    
    This class handles all database operations including creating
    tables, inserting teams, matches, and divisions.
    """
    
    def __init__(self, db_path: str = "gvsa_data.db") -> None:
        """
        Initialize the database connection.
        
        Parameters
        ----------
        db_path : str
            Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._create_tables()
    
    def _connect(self) -> None:
        """Create database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        if not self.conn:
            return
        
        cursor = self.conn.cursor()
        
        # Divisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS divisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                division_id TEXT NOT NULL,
                year_season TEXT,
                season_id1 TEXT,
                season_id2 TEXT,
                season_name TEXT,
                division_name TEXT NOT NULL,
                season_type TEXT,
                display_name TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(division_id, year_season, division_name)
            )
        """)
        
        # Teams table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                division_id INTEGER,
                team_name TEXT NOT NULL,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                ties INTEGER DEFAULT 0,
                forfeits INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                goals_for INTEGER DEFAULT 0,
                goals_against INTEGER DEFAULT 0,
                goal_differential INTEGER DEFAULT 0,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (division_id) REFERENCES divisions(id),
                UNIQUE(division_id, team_name)
            )
        """)
        
        # Matches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                division_id INTEGER,
                date TEXT,
                time TEXT,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                field TEXT,
                home_score INTEGER,
                away_score INTEGER,
                status TEXT DEFAULT 'scheduled',
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (division_id) REFERENCES divisions(id)
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_teams_division ON teams(division_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_division ON matches(division_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team, away_team)")
        
        self.conn.commit()
    
    def insert_division(self, division: Dict[str, Any]) -> int:
        """
        Insert or update a division.
        
        Parameters
        ----------
        division : Dict[str, Any]
            Division dictionary
            
        Returns
        -------
        int
            The division database ID
        """
        if not self.conn:
            return 0
        
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO divisions 
            (division_id, year_season, season_id1, season_id2, season_name, 
             division_name, season_type, display_name, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            division.get('division_id'),
            division.get('year_season'),
            division.get('season_id1'),
            division.get('season_id2'),
            division.get('season_name'),
            division.get('division_name'),
            division.get('season_type'),
            division.get('display_name'),
            datetime.now()
        ))
        
        # Get the division ID
        cursor.execute("""
            SELECT id FROM divisions 
            WHERE division_id = ? AND year_season = ? AND division_name = ?
        """, (
            division.get('division_id'),
            division.get('year_season'),
            division.get('division_name')
        ))
        
        result = cursor.fetchone()
        division_db_id = result[0] if result else cursor.lastrowid
        
        self.conn.commit()
        return division_db_id
    
    def insert_teams(self, division_db_id: int, teams: List[Dict[str, Any]]) -> None:
        """
        Insert or update teams for a division.
        
        Parameters
        ----------
        division_db_id : int
            Database ID of the division
        teams : List[Dict[str, Any]]
            List of team dictionaries
        """
        if not self.conn:
            return
        
        cursor = self.conn.cursor()
        
        for team in teams:
            cursor.execute("""
                INSERT OR REPLACE INTO teams 
                (division_id, team_name, wins, losses, ties, forfeits, 
                 points, goals_for, goals_against, goal_differential, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                division_db_id,
                team['team_name'],
                team.get('wins', 0),
                team.get('losses', 0),
                team.get('ties', 0),
                team.get('forfeits', 0),
                team.get('points', 0),
                team.get('goals_for', 0),
                team.get('goals_against', 0),
                team.get('goal_differential', 0),
                datetime.now()
            ))
        
        self.conn.commit()
    
    def insert_matches(self, division_db_id: int, matches: List[Dict[str, Any]]) -> None:
        """
        Insert or update matches for a division.
        
        Parameters
        ----------
        division_db_id : int
            Database ID of the division
        matches : List[Dict[str, Any]]
            List of match dictionaries
        """
        if not self.conn:
            return
        
        cursor = self.conn.cursor()
        
        for match in matches:
            cursor.execute("""
                INSERT OR REPLACE INTO matches 
                (division_id, date, time, home_team, away_team, field, 
                 home_score, away_score, status, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                division_db_id,
                match.get('date'),
                match.get('time'),
                match['home_team'],
                match['away_team'],
                match.get('field'),
                match.get('home_score'),
                match.get('away_score'),
                match.get('status', 'scheduled'),
                datetime.now()
            ))
        
        self.conn.commit()
    
    def save_standings(self, standings_data: Dict[str, Any]) -> None:
        """
        Save complete standings data for a division.
        
        Parameters
        ----------
        standings_data : Dict[str, Any]
            Complete standings data including division, teams, and matches
        """
        division = standings_data.get('division', {})
        division_db_id = self.insert_division(division)
        
        teams = standings_data.get('teams', [])
        if teams:
            self.insert_teams(division_db_id, teams)
        
        matches = standings_data.get('matches', [])
        if matches:
            self.insert_matches(division_db_id, matches)
        
        print(f"  - Saved to database (division_id: {division_db_id})")
    
    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self) -> 'GVSADatabase':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

