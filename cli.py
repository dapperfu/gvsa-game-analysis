#!/usr/bin/env python3
"""
GVSA CLI Application.

Command-line interface for scraping and analyzing GVSA soccer data.
Provides commands for scraping, querying teams, seasons, divisions, and analysis.
"""
from typing import Optional, List, Dict, Any
import click
from pathlib import Path
import sys

from scraper import GVSAScraper
from db_pony import GVSA_Database, TeamMatcher
from models import db, Season, Division, Team, TeamSeason, Club, Match, SeasonType
from pony.orm import db_session, select, count
from team_progression import track_team_progression, find_team_progression_path, build_team_record_across_seasons
from age_progression import extract_season_year
from cli_output import print_output, extract_age_group
from analyze_clubs import ClubAnalyzer


# Global context for database path
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version='1.0.0', prog_name='gvsa')
@click.option('--db-path', default='gvsa_data2.db', 
              help='Path to SQLite database file',
              type=click.Path(exists=False, dir_okay=False))
@click.option('--verbose', '-v', is_flag=True, 
              help='Enable verbose output')
@click.pass_context
def cli(ctx: click.Context, db_path: str, verbose: bool) -> None:
    """
    GVSA CLI - Scrape and analyze GVSA soccer data.
    
    This CLI provides commands for scraping data from gvsoccer.org,
    querying teams, seasons, and divisions, and performing analysis.
    
    Examples:
    
        gvsa scrape --db-path gvsa_data2.db
    
        gvsa seasons --format table
    
        gvsa divisions --year 2025 --season Fall
    
        gvsa teams --search "Rapids FC" --format table
    """
    ctx.ensure_object(dict)
    ctx.obj['db_path'] = db_path
    ctx.obj['verbose'] = verbose


def get_db(ctx: click.Context) -> GVSA_Database:
    """
    Get or initialize database connection.
    
    Parameters
    ----------
    ctx : click.Context
        Click context
        
    Returns
    -------
    GVSA_Database
        Database instance
    """
    db_path = ctx.obj['db_path']
    if not Path(db_path).exists():
        click.echo(f"Error: Database file '{db_path}' does not exist.", err=True)
        click.echo("Run 'gvsa scrape' first to create the database.", err=True)
        sys.exit(1)
    return GVSA_Database(db_path)


@cli.command()
@click.option('--force-refresh', is_flag=True,
              help='Force refresh even if cached')
@click.option('--no-cache', is_flag=True,
              help='Disable HTML caching')
@click.option('--workers', default=5, type=int,
              help='Number of parallel workers (default: 5)')
@click.option('--delay', default=1.0, type=float,
              help='Delay between requests in seconds (default: 1.0)')
@click.pass_context
def scrape(ctx: click.Context, force_refresh: bool, no_cache: bool, 
          workers: int, delay: float) -> None:
    """
    Scrape data from gvsoccer.org.
    
    This command performs a two-stage scrape:
    1. Fetches and caches HTML files from the server
    2. Parses cached HTML and populates the database
    
    Examples:
    
        gvsa scrape --db-path gvsa_data2.db
    
        gvsa scrape --force-refresh --workers 10
    """
    db_path = ctx.obj['db_path']
    verbose = ctx.obj['verbose']
    
    if verbose:
        click.echo(f"Using database: {db_path}")
        click.echo(f"Workers: {workers}, Delay: {delay}s")
        click.echo(f"Force refresh: {force_refresh}, No cache: {no_cache}")
    
    # Initialize scraper
    scraper = GVSAScraper(
        delay=delay,
        use_cache=not no_cache,
        max_workers=workers
    )
    
    # Initialize database
    db_instance = GVSA_Database(db_path)
    
    # Stage 1: Fetch HTML
    click.echo("=" * 80)
    click.echo("STAGE 1: Fetching HTML files from server")
    click.echo("=" * 80)
    fetched_count = scraper.fetch_html_only()
    
    # Stage 2: Parse cached HTML
    click.echo(f"\n{'='*80}")
    click.echo("STAGE 2: Parsing cached HTML files and populating database")
    click.echo("=" * 80)
    standings = scraper.parse_cached_html(db=db_instance)
    
    # Summary
    click.echo(f"\n{'='*80}")
    click.echo("Scraping complete!")
    click.echo(f"HTML files fetched: {fetched_count}")
    click.echo(f"Successfully parsed: {len(standings)} divisions")
    
    total_teams = sum(len(s['teams']) for s in standings)
    total_matches = sum(len(s['matches']) for s in standings)
    click.echo(f"Total teams: {total_teams}")
    click.echo(f"Total matches: {total_matches}")
    click.echo(f"Database saved to: {db_path}")


@cli.command()
@click.option('--format', 'output_format', default='table',
              type=click.Choice(['table', 'json', 'csv'], case_sensitive=False),
              help='Output format (default: table)')
@click.option('--year', type=int,
              help='Filter by year (e.g., 2025)')
@click.option('--season-type', type=click.Choice(['Fall', 'Spring'], case_sensitive=False),
              help='Filter by season type (Fall or Spring)')
@click.pass_context
def seasons(ctx: click.Context, output_format: str, year: Optional[int], 
           season_type: Optional[str]) -> None:
    """
    List all available seasons from the database.
    
    Examples:
    
        gvsa seasons
    
        gvsa seasons --year 2025 --format json
    
        gvsa seasons --season-type Fall --format csv
    """
    db_instance = get_db(ctx)
    
    @db_session
    def get_seasons_data() -> List[Dict[str, Any]]:
        """Get seasons data from database."""
        query = select(s for s in Season)
        
        if year:
            query = select(s for s in Season if s.year == year)
        
        if season_type:
            season_type_norm = season_type.capitalize()
            season_type_str = 'Fall' if season_type_norm == 'Fall' else 'Spring'
            if year:
                query = select(s for s in Season if s.year == year and s.season_type == season_type_str)
            else:
                query = select(s for s in Season if s.season_type == season_type_str)
        
        seasons_list = list(query)
        result = []
        
        for season in seasons_list:
            # Count divisions
            div_count = count(d for d in Division if d.season == season)
            
            result.append({
                'season_name': season.season_name,
                'year': season.year,
                'season_type': season.season_type,
                'division_count': div_count,
                'scraped_at': str(season.scraped_at)
            })
        
        return sorted(result, key=lambda x: (x['year'], x['season_type']))
    
    try:
        data = get_seasons_data()
        headers = ['season_name', 'year', 'season_type', 'division_count', 'scraped_at']
        print_output(data, output_format, headers)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--year', type=int,
              help='Filter by year (e.g., 2025)')
@click.option('--season', type=click.Choice(['Fall', 'Spring'], case_sensitive=False),
              help='Filter by season type (Fall or Spring)')
@click.option('--age-group', type=str,
              help='Filter by age group (e.g., U11, U15/16)')
@click.option('--gender', type=click.Choice(['Boys', 'Girls'], case_sensitive=False),
              help='Filter by gender (Boys or Girls)')
@click.option('--format', 'output_format', default='table',
              type=click.Choice(['table', 'json', 'csv'], case_sensitive=False),
              help='Output format (default: table)')
@click.pass_context
def divisions(ctx: click.Context, year: Optional[int], season: Optional[str],
             age_group: Optional[str], gender: Optional[str], 
             output_format: str) -> None:
    """
    List divisions with optional filtering.
    
    Examples:
    
        gvsa divisions --year 2025 --season Fall
    
        gvsa divisions --age-group U11 --gender Boys
    
        gvsa divisions --year 2025 --season Fall --format json
    """
    db_instance = get_db(ctx)
    
    @db_session
    def get_divisions_data() -> List[Dict[str, Any]]:
        """Get divisions data from database."""
        query = select(d for d in Division)
        
        # Filter by year and season
        if year and season:
            season_type_norm = season.capitalize()
            season_type_str = 'Fall' if season_type_norm == 'Fall' else 'Spring'
            season_obj = db_instance.get_season(year, season_type_str)
            if season_obj:
                query = select(d for d in Division if d.season == season_obj)
            else:
                return []
        elif year:
            seasons_list = list(select(s for s in Season if s.year == year))
            if seasons_list:
                query = select(d for d in Division if d.season in seasons_list)
            else:
                return []
        elif season:
            season_type_norm = season.capitalize()
            season_type_str = 'Fall' if season_type_norm == 'Fall' else 'Spring'
            query = select(d for d in Division if d.season.season_type == season_type_str)
        
        # Filter by age group
        if age_group:
            age_group_upper = age_group.upper()
            query = select(d for d in query if age_group_upper in d.division_name.upper())
        
        # Filter by gender
        if gender:
            gender_lower = gender.lower()
            query = select(d for d in query if gender_lower in d.division_name.lower())
        
        divisions_list = list(query)
        result = []
        
        for division in divisions_list:
            # Count teams and matches
            team_count = count(ts for ts in TeamSeason if ts.division == division)
            match_count = count(m for m in Match if m.division == division)
            
            age_group_extracted = extract_age_group(division.division_name)
            
            result.append({
                'division_name': division.division_name,
                'season': division.season.season_name,
                'year': division.season.year,
                'season_type': division.season.season_type,
                'age_group': age_group_extracted or 'Unknown',
                'team_count': team_count,
                'matches_count': match_count,
                'scraped_at': str(division.scraped_at)
            })
        
        return sorted(result, key=lambda x: (x['year'], x['season_type'], x['division_name']))
    
    try:
        data = get_divisions_data()
        headers = ['division_name', 'season', 'year', 'season_type', 'age_group', 'team_count', 'matches_count']
        print_output(data, output_format, headers)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--search', type=str,
              help='Search team name (fuzzy matching)')
@click.option('--club', type=str,
              help='Filter by club name')
@click.option('--age-group', type=str,
              help='Filter by age group (e.g., U11, U15/16)')
@click.option('--gender', type=click.Choice(['Boys', 'Girls'], case_sensitive=False),
              help='Filter by gender (Boys or Girls)')
@click.option('--season', type=str,
              help='Filter by season name (e.g., "Fall 2025")')
@click.option('--year', type=int,
              help='Filter by year (e.g., 2025)')
@click.option('--stats', is_flag=True,
              help='Include detailed statistics')
@click.option('--progression', is_flag=True,
              help='Show team progression across seasons')
@click.option('--format', 'output_format', default='table',
              type=click.Choice(['table', 'json', 'csv'], case_sensitive=False),
              help='Output format (default: table)')
@click.pass_context
def teams(ctx: click.Context, search: Optional[str], club: Optional[str],
         age_group: Optional[str], gender: Optional[str], season: Optional[str],
         year: Optional[int], stats: bool, progression: bool, 
         output_format: str) -> None:
    """
    Query teams with various filters and options.
    
    Examples:
    
        gvsa teams --search "Rapids FC"
    
        gvsa teams --club "NUSC" --age-group U11 --format json
    
        gvsa teams --search "Green" --progression --format table
    
        gvsa teams --year 2025 --season "Fall 2025" --stats
    """
    db_instance = get_db(ctx)
    
    def format_progression_data(progression: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format progression data for output."""
        result = []
        for age_prog in progression.get('progression', []):
            for appearance in age_prog.get('appearances', []):
                result.append({
                    'team_name': progression['team_name'],
                    'club': progression.get('club_name', 'N/A'),
                    'age_group': age_prog['age_group'],
                    'season': appearance['season'],
                    'division': appearance['division_name'],
                    'record': f"{appearance['wins']}W-{appearance['losses']}L-{appearance['ties']}T",
                    'points': appearance['points'],
                })
        return result
    
    @db_session
    def get_teams_data() -> List[Dict[str, Any]]:
        """Get teams data from database."""
        # Handle progression mode with search
        if progression and search:
            progression_data = find_team_progression_path(search)
            if progression_data:
                return format_progression_data(progression_data)
        
        # Start with all team seasons
        query = select(ts for ts in TeamSeason)
        
        # Filter by season name
        if season:
            season_list = list(select(s for s in Season if season in s.season_name))
            if season_list:
                divisions_list = list(select(d for d in Division if d.season in season_list))
                if divisions_list:
                    query = select(ts for ts in TeamSeason if ts.division in divisions_list)
                else:
                    return []
            else:
                return []
        
        # Filter by year
        if year:
            seasons_list = list(select(s for s in Season if s.year == year))
            if seasons_list:
                divisions_list = list(select(d for d in Division if d.season in seasons_list))
                if divisions_list:
                    if season:
                        # Already filtered, intersect
                        query = select(ts for ts in query if ts.division in divisions_list)
                    else:
                        query = select(ts for ts in TeamSeason if ts.division in divisions_list)
                else:
                    return []
        
        # Filter by age group
        if age_group:
            age_group_upper = age_group.upper()
            divisions_list = list(select(d for d in Division if age_group_upper in d.division_name.upper()))
            if divisions_list:
                query = select(ts for ts in query if ts.division in divisions_list)
            else:
                return []
        
        # Filter by gender
        if gender:
            gender_lower = gender.lower()
            divisions_list = list(select(d for d in Division if gender_lower in d.division_name.lower()))
            if divisions_list:
                query = select(ts for ts in query if ts.division in divisions_list)
            else:
                return []
        
        # Filter by club
        if club:
            normalized_club = TeamMatcher.normalize_name(club)
            clubs_list = list(select(c for c in Club if normalized_club in c.canonical_name.lower()))
            if clubs_list:
                teams_list = list(select(t for t in Team if t.club in clubs_list))
                if teams_list:
                    query = select(ts for ts in query if ts.team in teams_list)
                else:
                    return []
            else:
                return []
        
        # Filter by search term
        if search:
            search_lower = search.lower()
            query = select(ts for ts in query if search_lower in ts.team_name.lower())
        
        team_seasons = list(query)
        
        result = []
        
        for ts in team_seasons:
            team_data = {
                'team_name': ts.team_name,
                'canonical_name': ts.team.canonical_name,
                'club': ts.team.club.name if ts.team.club else 'N/A',
                'division': ts.division.division_name,
                'season': ts.division.season.season_name,
                'year': ts.division.season.year,
                'season_type': ts.division.season.season_type,
            }
            
            if stats:
                team_data.update({
                    'wins': ts.wins,
                    'losses': ts.losses,
                    'ties': ts.ties,
                    'points': ts.points,
                    'goals_for': ts.goals_for,
                    'goals_against': ts.goals_against,
                    'goal_differential': ts.goal_differential,
                })
            else:
                team_data.update({
                    'record': f"{ts.wins}W-{ts.losses}L-{ts.ties}T",
                    'points': ts.points,
                })
            
            result.append(team_data)
        
        return result
    
    try:
        data = get_teams_data()
        if stats:
            headers = ['team_name', 'canonical_name', 'club', 'division', 'season', 'wins', 'losses', 'ties', 'points', 'goals_for', 'goals_against', 'goal_differential']
        elif progression:
            headers = ['team_name', 'club', 'age_group', 'season', 'division', 'record', 'points']
        else:
            headers = ['team_name', 'club', 'division', 'season', 'record', 'points']
        print_output(data, output_format, headers)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        import traceback
        if ctx.obj['verbose']:
            traceback.print_exc()
        sys.exit(1)


@cli.group()
def analyze() -> None:
    """
    Analysis commands for GVSA data.
    
    Provides various analysis tools for clubs, team progression, and statistics.
    """
    pass


@analyze.command()
@click.option('--format', 'output_format', default='table',
              type=click.Choice(['table', 'json', 'csv'], case_sensitive=False),
              help='Output format (default: table)')
@click.pass_context
def clubs(ctx: click.Context, output_format: str) -> None:
    """
    Analyze clubs and their performance across seasons.
    
    Examples:
    
        gvsa analyze clubs
    
        gvsa analyze clubs --format json
    """
    db_instance = get_db(ctx)
    
    @db_session
    def get_clubs_data() -> List[Dict[str, Any]]:
        """Get clubs analysis data."""
        analyzer = ClubAnalyzer()
        clubs_list = analyzer.get_all_clubs()
        
        result = []
        for club in clubs_list:
            teams = analyzer.get_club_teams(club)
            stats = analyzer.get_club_stats_by_season(club)
            
            # Aggregate total stats
            total_wins = sum(s['total_wins'] for s in stats.values())
            total_losses = sum(s['total_losses'] for s in stats.values())
            total_ties = sum(s['total_ties'] for s in stats.values())
            total_points = sum(s['total_points'] for s in stats.values())
            total_goals_for = sum(s['total_goals_for'] for s in stats.values())
            total_goals_against = sum(s['total_goals_against'] for s in stats.values())
            
            result.append({
                'club_name': club.name,
                'team_count': len(teams),
                'seasons_active': len(stats),
                'total_wins': total_wins,
                'total_losses': total_losses,
                'total_ties': total_ties,
                'total_points': total_points,
                'total_goals_for': total_goals_for,
                'total_goals_against': total_goals_against,
            })
        
        return sorted(result, key=lambda x: x['club_name'])
    
    try:
        data = get_clubs_data()
        headers = ['club_name', 'team_count', 'seasons_active', 'total_wins', 'total_losses', 'total_ties', 'total_points', 'total_goals_for', 'total_goals_against']
        print_output(data, output_format, headers)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@analyze.command()
@click.option('--club', type=str,
              help='Filter by club name')
@click.option('--min-age', default=10, type=int,
              help='Minimum age group (default: 10)')
@click.option('--max-age', default=14, type=int,
              help='Maximum age group (default: 14)')
@click.option('--format', 'output_format', default='table',
              type=click.Choice(['table', 'json', 'csv'], case_sensitive=False),
              help='Output format (default: table)')
@click.pass_context
def progression(ctx: click.Context, club: Optional[str], min_age: int, 
               max_age: int, output_format: str) -> None:
    """
    Analyze team progression across age groups.
    
    Examples:
    
        gvsa analyze progression
    
        gvsa analyze progression --club "Rapids FC" --format json
    """
    db_instance = get_db(ctx)
    
    @db_session
    def get_progression_data() -> List[Dict[str, Any]]:
        """Get team progression data."""
        progressions = track_team_progression(
            team=None,
            club_name=club,
            min_age=min_age,
            max_age=max_age
        )
        
        result = []
        for prog in progressions:
            for age_prog in prog['progression']:
                for appearance in age_prog['appearances']:
                    result.append({
                        'team_name': prog['team_name'],
                        'club': prog.get('club_name', 'N/A'),
                        'age_group': age_prog['age_group'],
                        'season': appearance['season'],
                        'division': appearance['division_name'],
                        'record': f"{appearance['wins']}W-{appearance['losses']}L-{appearance['ties']}T",
                        'points': appearance['points'],
                        'age_groups_played': prog['age_groups_played'],
                        'total_seasons': prog['total_seasons'],
                    })
        
        return result
    
    try:
        data = get_progression_data()
        headers = ['team_name', 'club', 'age_group', 'season', 'division', 'record', 'points', 'age_groups_played', 'total_seasons']
        print_output(data, output_format, headers)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@analyze.command()
@click.option('--format', 'output_format', default='table',
              type=click.Choice(['table', 'json', 'csv'], case_sensitive=False),
              help='Output format (default: table)')
@click.pass_context
def stats(ctx: click.Context, output_format: str) -> None:
    """
    Show general database statistics.
    
    Examples:
    
        gvsa analyze stats
    
        gvsa analyze stats --format json
    """
    db_instance = get_db(ctx)
    
    @db_session
    def get_stats_data() -> List[Dict[str, Any]]:
        """Get general statistics."""
        stats_data = {
            'seasons': count(s for s in Season),
            'divisions': count(d for d in Division),
            'clubs': count(c for c in Club),
            'teams': count(t for t in Team),
            'team_seasons': count(ts for ts in TeamSeason),
            'matches': count(m for m in Match),
        }
        
        return [stats_data]
    
    try:
        data = get_stats_data()
        headers = ['seasons', 'divisions', 'clubs', 'teams', 'team_seasons', 'matches']
        print_output(data, output_format, headers)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main() -> None:
    """
    Main entry point for CLI application.
    """
    cli()


if __name__ == '__main__':
    main()

