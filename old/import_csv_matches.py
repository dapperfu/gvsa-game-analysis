#!/usr/bin/env python3
"""
Import match data from CSV files into the database.

This script scans CSV files in html_cache directories and imports matches
directly into the database with 1:1 team name matching (exact names from CSV).
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import re
import sys
from parse_csv import parse_csv_standings
from db_pony import GVSA_Database
from models import db, Season, Division, TeamSeason, Match
from pony.orm import db_session, select, commit


def extract_season_info_from_path(csv_path: Path) -> Optional[Dict[str, Any]]:
    """
    Extract season and division info from CSV file path.
    
    Path format: html_cache/{year}_{season_type}/{division_name}.csv
    Example: html_cache/2014_Fall/U13_Girls_3rd_Division.csv
    
    Parameters
    ----------
    csv_path : Path
        Path to CSV file
        
    Returns
    -------
    Optional[Dict[str, Any]]
        Dictionary with year, season_type, and division_name, or None if parsing fails
    """
    parts = csv_path.parts
    if len(parts) < 3:
        return None
    
    # Extract year_season from path (e.g., "2014_Fall")
    year_season = parts[-2]
    division_name = csv_path.stem  # filename without .csv extension
    
    # Parse year_season (e.g., "2014_Fall" -> year=2014, season_type="Fall")
    match = re.match(r'^(\d{4})_(Fall|Spring)$', year_season)
    if not match:
        return None
    
    year = int(match.group(1))
    season_type = match.group(2)
    
    return {
        'year': year,
        'season_type': season_type,
        'division_name': division_name,
        'season_name': f"{season_type} {year}"
    }


@db_session
def import_csv_matches(csv_path: Path, db_instance: GVSA_Database, verbose: bool = True) -> Dict[str, Any]:
    """
    Import matches from a single CSV file into the database.
    
    Parameters
    ----------
    csv_path : Path
        Path to CSV file
    db_instance : GVSA_Database
        Database instance
    verbose : bool
        Print progress messages
        
    Returns
    -------
    Dict[str, Any]
        Statistics about the import:
        - matches_found: int
        - matches_imported: int
        - teams_created: int
        - errors: List[str]
    """
    stats = {
        'matches_found': 0,
        'matches_imported': 0,
        'teams_created': 0,
        'errors': []
    }
    
    if not csv_path.exists():
        stats['errors'].append(f"CSV file not found: {csv_path}")
        return stats
    
    # Extract season/division info from path
    path_info = extract_season_info_from_path(csv_path)
    if not path_info:
        stats['errors'].append(f"Could not parse season/division from path: {csv_path}")
        return stats
    
    # Get or create season
    season = db_instance.get_or_create_season(
        path_info['year'],
        path_info['season_name'],
        path_info['season_type']
    )
    
    # Get or create division (need division_id - we'll use division_name as fallback)
    division_id = path_info['division_name']  # Use division name as ID if not in DB
    division = db_instance.get_or_create_division(
        division_id,
        path_info['division_name'],
        season
    )
    
    # Parse CSV
    try:
        csv_content = csv_path.read_text(encoding='utf-8')
        parsed_data = parse_csv_standings(csv_content)
        matches_data = parsed_data.get('matches', [])
        stats['matches_found'] = len(matches_data)
    except Exception as e:
        stats['errors'].append(f"Error parsing CSV: {e}")
        return stats
    
    if not matches_data:
        if verbose:
            print(f"  No matches found in {csv_path.name}")
        return stats
    
    # Import matches - use team names 1:1 as they appear in CSV
    team_seasons = {}
    
    for match_data in matches_data:
        home_team_name = match_data['home_team']
        away_team_name = match_data['away_team']
        
        # Get or create TeamSeason for home team (using exact name from CSV)
        if home_team_name not in team_seasons:
            home_team, _ = db_instance.get_or_create_team(home_team_name)
            home_team_seasons_list = list(select(
                ts for ts in TeamSeason
                if ts.team == home_team and ts.division == division and ts.team_name == home_team_name
            ))
            if home_team_seasons_list:
                home_team_season = home_team_seasons_list[0]
            else:
                # Create new TeamSeason with exact name from CSV
                home_team_season = TeamSeason(
                    team=home_team,
                    division=division,
                    team_name=home_team_name
                )
                stats['teams_created'] += 1
            team_seasons[home_team_name] = home_team_season
        
        # Get or create TeamSeason for away team (using exact name from CSV)
        if away_team_name not in team_seasons:
            away_team, _ = db_instance.get_or_create_team(away_team_name)
            away_team_seasons_list = list(select(
                ts for ts in TeamSeason
                if ts.team == away_team and ts.division == division and ts.team_name == away_team_name
            ))
            if away_team_seasons_list:
                away_team_season = away_team_seasons_list[0]
            else:
                # Create new TeamSeason with exact name from CSV
                away_team_season = TeamSeason(
                    team=away_team,
                    division=division,
                    team_name=away_team_name
                )
                stats['teams_created'] += 1
            team_seasons[away_team_name] = away_team_season
        
        home_team_season = team_seasons[home_team_name]
        away_team_season = team_seasons[away_team_name]
        
        # Check if match already exists (avoid duplicates)
        existing_matches = list(select(
            m for m in Match
            if m.division == division
            and m.home_team == home_team_season
            and m.away_team == away_team_season
            and m.date == match_data.get('date', '')
        ))
        
        if existing_matches:
            # Match already exists, skip
            continue
        
        # Create match
        try:
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
            stats['matches_imported'] += 1
        except Exception as e:
            stats['errors'].append(f"Error creating match {home_team_name} vs {away_team_name}: {e}")
    
    commit()
    
    if verbose:
        print(f"  {csv_path.name}: {stats['matches_imported']}/{stats['matches_found']} matches imported, "
              f"{stats['teams_created']} teams created")
    
    return stats


def find_csv_files(cache_dir: Path = Path("html_cache")) -> List[Path]:
    """
    Find all CSV files in the cache directory.
    
    Parameters
    ----------
    cache_dir : Path
        Cache directory root
        
    Returns
    -------
    List[Path]
        List of CSV file paths
    """
    csv_files = []
    if cache_dir.exists():
        csv_files = list(cache_dir.rglob("*.csv"))
    return sorted(csv_files)


def main() -> None:
    """Main entry point."""
    db_path = sys.argv[1] if len(sys.argv) > 1 else "gvsa_data2.db"
    
    print("=" * 80)
    print("Importing CSV Matches into Database")
    print("=" * 80)
    print(f"Database: {db_path}\n")
    
    # Initialize database
    db_instance = GVSA_Database(db_path)
    
    # Find all CSV files
    cache_dir = Path("html_cache")
    csv_files = find_csv_files(cache_dir)
    
    if not csv_files:
        print("No CSV files found in html_cache directory")
        return
    
    print(f"Found {len(csv_files)} CSV files\n")
    
    total_stats = {
        'matches_found': 0,
        'matches_imported': 0,
        'teams_created': 0,
        'errors': []
    }
    
    try:
        for i, csv_file in enumerate(csv_files, 1):
            print(f"[{i}/{len(csv_files)}] Processing {csv_file.relative_to(cache_dir)}...")
            
            stats = import_csv_matches(csv_file, db_instance, verbose=False)
            
            total_stats['matches_found'] += stats['matches_found']
            total_stats['matches_imported'] += stats['matches_imported']
            total_stats['teams_created'] += stats['teams_created']
            total_stats['errors'].extend(stats['errors'])
            
            if stats['matches_imported'] > 0:
                print(f"  ✓ {stats['matches_imported']}/{stats['matches_found']} matches imported")
            elif stats['errors']:
                print(f"  ✗ Error: {stats['errors'][-1]}")
            else:
                print(f"  ⊘ No matches to import")
        
        print(f"\n{'='*80}")
        print("Summary:")
        print(f"  CSV files processed: {len(csv_files)}")
        print(f"  Matches found: {total_stats['matches_found']}")
        print(f"  Matches imported: {total_stats['matches_imported']}")
        print(f"  Teams created: {total_stats['teams_created']}")
        if total_stats['errors']:
            print(f"  Errors: {len(total_stats['errors'])}")
            for error in total_stats['errors'][:10]:  # Show first 10 errors
                print(f"    - {error}")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

