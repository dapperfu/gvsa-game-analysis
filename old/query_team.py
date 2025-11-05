#!/usr/bin/env python3
"""
Query the database for a specific team.
"""
from db_pony import GVSA_Database
from models import db, Team, TeamSeason, Division, Season, Match
from pony.orm import db_session, select, count
import sys


def search_team(db_path: str, search_term: str) -> None:
    """
    Search for a team in the database.
    
    Parameters
    ----------
    db_path : str
        Path to database file
    search_term : str
        Search term to look for
    """
    gvsa_db = GVSA_Database(db_path)
    
    search_lower = search_term.lower()
    
    with db_session:
        print(f"Searching for: '{search_term}'")
        print("=" * 80)
        
        # Search in TeamSeason (team_name)
        print("\nSearching in TeamSeason.team_name:")
        team_seasons = select(ts for ts in TeamSeason if search_lower in ts.team_name.lower())
        for ts in team_seasons:
            print(f"  - {ts.team_name}")
            print(f"    Division: {ts.division.division_name}")
            print(f"    Season: {ts.division.season.season_name} ({ts.division.season.year_season})")
            print(f"    Record: {ts.wins}W-{ts.losses}L-{ts.ties}T, {ts.points} pts")
            print()
        
        # Search in Division names
        print("\nSearching in Division.division_name:")
        divisions = select(d for d in Division if search_lower in d.division_name.lower())
        for div in divisions:
            print(f"  - {div.division_name}")
            print(f"    Season: {div.season.season_name} ({div.season.year_season})")
            print(f"    Teams: {count(ts for ts in TeamSeason if ts.division == div)}")
            print()
        
        # Search in Team canonical_name
        print("\nSearching in Team.canonical_name:")
        teams = select(t for t in Team if search_lower in t.canonical_name.lower())
        for team in teams:
            print(f"  - {team.canonical_name}")
            if team.club:
                print(f"    Club: {team.club.name}")
            print(f"    Seasons: {count(ts for ts in TeamSeason if ts.team == team)}")
            print()
        
        # Search specifically for "U11 Boys" and "Green" and "Fall 2025"
        print("\nSearching for U11 Boys Green in Fall 2025:")
        print("-" * 80)
        fall_2025_seasons = select(s for s in Season if 'Fall' in s.season_name and '2025' in s.year_season)
        for season in fall_2025_seasons:
            print(f"\nSeason: {season.season_name} ({season.year_season})")
            divisions = select(d for d in Division if d.season == season and 
                             'U11' in d.division_name and 'Boys' in d.division_name)
            for div in divisions:
                print(f"  Division: {div.division_name}")
                team_seasons = select(ts for ts in TeamSeason if ts.division == div and 
                                     'green' in ts.team_name.lower())
                for ts in team_seasons:
                    print(f"    Team: {ts.team_name}")
                    print(f"      Record: {ts.wins}W-{ts.losses}L-{ts.ties}T, {ts.points} pts")
                    print(f"      Goals: {ts.goals_for}GF / {ts.goals_against}GA")
                    print()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "gvsa_data.db"
    search_term = sys.argv[2] if len(sys.argv) > 2 else "U11 Boys Green"
    
    search_team(db_path, search_term)

