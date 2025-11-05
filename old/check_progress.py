#!/usr/bin/env python3
"""
Check scraping progress and database statistics.
"""
from pony.orm import db_session, select, count
from models import db, Season, Division, Team, TeamSeason, Match, Club
import sys


def main() -> None:
    """
    Print database statistics.
    """
    db_path = sys.argv[1] if len(sys.argv) > 1 else "gvsa_data.db"
    
    try:
        db.bind(provider='sqlite', filename=db_path, create_db=False)
        db.generate_mapping(create_tables=False)
        
        with db_session:
            seasons = count(s for s in Season)
            divisions = count(d for d in Division)
            teams = count(t for t in Team)
            team_seasons = count(ts for ts in TeamSeason)
            matches = count(m for m in Match)
            clubs = count(c for c in Club)
            
            print(f"\n{'='*80}")
            print(f"Database Statistics")
            print(f"{'='*80}")
            print(f"Seasons: {seasons}")
            print(f"Divisions: {divisions}")
            print(f"Teams: {teams}")
            print(f"Team Seasons: {team_seasons}")
            print(f"Matches: {matches}")
            print(f"Clubs: {clubs}")
            
            if seasons > 0:
                print(f"\nSeasons in database:")
                for season in select(s for s in Season).order_by(Season.season_name):
                    div_count = count(d for d in Division if d.season == season)
                    print(f"  {season.season_name} ({season.year_season}): {div_count} divisions")
            
            if clubs > 0:
                print(f"\nTop 10 Clubs (by number of teams):")
                club_teams = {}
                for club in Club.select():
                    team_count = count(t for t in Team if t.club == club)
                    club_teams[club.name] = team_count
                for club_name, team_count in sorted(club_teams.items(), key=lambda x: x[1], reverse=True)[:10]:
                    print(f"  {club_name}: {team_count} teams")
    
    except Exception as e:
        print(f"Error: {e}")
        print("Database may not exist yet or may be empty.")


if __name__ == "__main__":
    main()

