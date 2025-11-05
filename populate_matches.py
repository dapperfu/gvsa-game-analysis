#!/usr/bin/env python3
"""
Populate matches database using Selenium to fetch fully rendered pages.

This script uses Selenium to fetch standings pages with JavaScript execution,
which should include the match schedule table (row2), then parses and saves
matches to the database.
"""
from scraper_selenium import GVSAScraperSelenium
from scraper import GVSAScraper
from db_pony import GVSA_Database
from parse_standings import parse_match_results
import sys


def main() -> None:
    """Main entry point."""
    db_path = sys.argv[1] if len(sys.argv) > 1 else "gvsa_data.db"
    
    print("=" * 80)
    print("Populating Matches Database with Selenium")
    print("=" * 80)
    
    # Get divisions for Fall 2025
    html_scraper = GVSAScraper(use_cache=True)
    seasons = html_scraper.get_seasons()
    
    fall_2025 = None
    for season in seasons:
        if 'Fall 2025' in season.get('season_name', ''):
            fall_2025 = season
            break
    
    if not fall_2025:
        print("Fall 2025 season not found")
        return
    
    divisions = html_scraper.get_divisions(fall_2025)
    print(f"\nFound {len(divisions)} divisions for Fall 2025")
    
    # Initialize Selenium scraper and database
    selenium_scraper = GVSAScraperSelenium(browser="firefox", headless=True, delay=2.0)
    db = GVSA_Database(db_path)
    
    total_matches = 0
    divisions_with_matches = 0
    
    try:
        for i, division in enumerate(divisions, 1):
            print(f"\n[{i}/{len(divisions)}] {division['display_name']}")
            
            standings = selenium_scraper.get_standings_with_selenium(division, force_refresh=False)
            
            if standings:
                if db:
                    db.save_standings(standings)
                
                matches = standings.get('matches', [])
                teams = standings.get('teams', [])
                
                if matches:
                    divisions_with_matches += 1
                    total_matches += len(matches)
                    print(f"  ✓ {len(teams)} teams, {len(matches)} matches")
                else:
                    print(f"  ⚠ {len(teams)} teams, 0 matches (row2 table may not be loading)")
            else:
                print(f"  ✗ Failed to fetch")
        
        print(f"\n{'='*80}")
        print("Summary:")
        print(f"  Divisions processed: {len(divisions)}")
        print(f"  Divisions with matches: {divisions_with_matches}")
        print(f"  Total matches found: {total_matches}")
        print(f"  Database: {db_path}")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        selenium_scraper.close()


if __name__ == "__main__":
    main()

