#!/usr/bin/env python3
"""
Analyze clubs and their success across seasons.

This script analyzes the database to identify clubs, track their teams,
and compare club success annually.
"""
from typing import Dict, List, Any
from pony.orm import db_session, select, count, sum as db_sum
from .models import db, Club, Team, TeamSeason, Season, Division


class ClubAnalyzer:
    """
    Analyzes club performance and statistics.
    """
    
    @db_session
    def get_all_clubs(self) -> List[Club]:
        """
        Get all clubs in the database.
        
        Returns
        -------
        List[Club]
            List of all clubs
        """
        return list(select(c for c in Club))
    
    @db_session
    def get_club_teams(self, club: Club) -> List[Team]:
        """
        Get all teams for a club.
        
        Parameters
        ----------
        club : Club
            Club entity
            
        Returns
        -------
        List[Team]
            List of teams
        """
        return list(select(t for t in Team if t.club == club))
    
    @db_session
    def get_club_stats_by_season(self, club: Club) -> Dict[str, Dict[str, Any]]:
        """
        Get club statistics grouped by season.
        
        Parameters
        ----------
        club : Club
            Club entity
            
        Returns
        -------
        Dict[str, Dict[str, Any]]
            Dictionary mapping season names to statistics
        """
        stats = {}
        
        for team in club.teams:
            for team_season in team.seasons:
                season = team_season.division.season
                season_key = f"{season.season_name} ({season.year_season})"
                
                if season_key not in stats:
                    stats[season_key] = {
                        'season': season,
                        'teams': 0,
                        'total_wins': 0,
                        'total_losses': 0,
                        'total_ties': 0,
                        'total_points': 0,
                        'total_goals_for': 0,
                        'total_goals_against': 0,
                        'divisions': set()
                    }
                
                stats[season_key]['teams'] += 1
                stats[season_key]['total_wins'] += team_season.wins
                stats[season_key]['total_losses'] += team_season.losses
                stats[season_key]['total_ties'] += team_season.ties
                stats[season_key]['total_points'] += team_season.points
                stats[season_key]['total_goals_for'] += team_season.goals_for
                stats[season_key]['total_goals_against'] += team_season.goals_against
                stats[season_key]['divisions'].add(team_season.division.division_name)
        
        # Convert sets to lists for JSON serialization
        for season_key in stats:
            stats[season_key]['divisions'] = list(stats[season_key]['divisions'])
            stats[season_key]['win_percentage'] = (
                stats[season_key]['total_wins'] / 
                max(1, stats[season_key]['total_wins'] + stats[season_key]['total_losses'] + stats[season_key]['total_ties'])
                * 100
            )
        
        return stats
    
    @db_session
    def print_club_summary(self) -> None:
        """
        Print summary of all clubs and their statistics.
        """
        clubs = self.get_all_clubs()
        
        print(f"\n{'='*80}")
        print(f"Club Analysis Summary")
        print(f"{'='*80}")
        print(f"Total clubs found: {len(clubs)}\n")
        
        for club in sorted(clubs, key=lambda c: c.name):
            teams = self.get_club_teams(club)
            stats = self.get_club_stats_by_season(club)
            
            print(f"\n{club.name}")
            print(f"  Teams: {len(teams)}")
            print(f"  Seasons active: {len(stats)}")
            
            if stats:
                print(f"  Season-by-season performance:")
                for season_key, season_stats in sorted(stats.items()):
                    print(f"    {season_key}:")
                    print(f"      Teams: {season_stats['teams']}")
                    print(f"      Record: {season_stats['total_wins']}W-{season_stats['total_losses']}L-{season_stats['total_ties']}T")
                    print(f"      Points: {season_stats['total_points']}")
                    print(f"      Win %: {season_stats['win_percentage']:.1f}%")
                    print(f"      Goals: {season_stats['total_goals_for']} for, {season_stats['total_goals_against']} against")
                    print(f"      Divisions: {len(season_stats['divisions'])}")


def main() -> None:
    """
    Main entry point for club analysis.
    """
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "gvsa_data.db"
    
    # Initialize database
    db.bind(provider='sqlite', filename=db_path, create_db=False)
    db.generate_mapping(create_tables=False)
    
    analyzer = ClubAnalyzer()
    analyzer.print_club_summary()


if __name__ == "__main__":
    main()

