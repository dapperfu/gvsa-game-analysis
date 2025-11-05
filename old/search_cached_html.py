#!/usr/bin/env python3
"""
Search cached HTML files for a specific team.
"""
from pathlib import Path
from bs4 import BeautifulSoup
import re


def search_cached_html(search_term: str, cache_dir: Path = Path("html_cache")) -> None:
    """
    Search cached HTML files for a team.
    
    Parameters
    ----------
    search_term : str
        Search term (team name or division)
    cache_dir : Path
        Cache directory path
    """
    search_lower = search_term.lower()
    
    print(f"Searching cached HTML files for: '{search_term}'")
    print("=" * 80)
    
    if not cache_dir.exists():
        print(f"Cache directory {cache_dir} does not exist.")
        return
    
    html_files = list(cache_dir.rglob("*.html"))
    print(f"Found {len(html_files)} cached HTML files\n")
    
    matches = []
    
    for html_file in html_files:
        try:
            content = html_file.read_text(encoding='utf-8')
            soup = BeautifulSoup(content, 'html.parser')
            
            # Check division name in file path
            parts = html_file.parts
            if len(parts) >= 3:
                year_season = parts[-3]
                season_name = parts[-2]
                division_name = html_file.stem.replace('_', ' ')
                
                # Check if search term matches division
                if search_lower in division_name.lower():
                    matches.append({
                        'file': html_file,
                        'type': 'division',
                        'year_season': year_season,
                        'season_name': season_name,
                        'division_name': division_name,
                        'content': content
                    })
            
            # Search for team names in HTML
            # Look for standings table
            standings_table = soup.find('table', id='row')
            if standings_table:
                tbody = standings_table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if cells and len(cells) > 0:
                            team_name = cells[0].get_text(strip=True)
                            if search_lower in team_name.lower():
                                matches.append({
                                    'file': html_file,
                                    'type': 'team',
                                    'team_name': team_name,
                                    'year_season': year_season if len(parts) >= 3 else 'unknown',
                                    'season_name': season_name if len(parts) >= 3 else 'unknown',
                                    'division_name': division_name if len(parts) >= 3 else 'unknown',
                                    'content': content
                                })
                                break  # Only need one match per file
        except Exception as e:
            print(f"Error reading {html_file}: {e}")
    
    # Print results
    if not matches:
        print(f"No matches found for '{search_term}'")
        print("\nAvailable seasons and divisions:")
        seasons = {}
        for html_file in html_files:
            parts = html_file.parts
            if len(parts) >= 3:
                year_season = parts[-3]
                season_name = parts[-2]
                if year_season not in seasons:
                    seasons[year_season] = {}
                if season_name not in seasons[year_season]:
                    seasons[year_season][season_name] = []
                seasons[year_season][season_name].append(html_file.stem.replace('_', ' '))
        
        for year, year_data in sorted(seasons.items()):
            print(f"\n{year}:")
            for season, divisions in sorted(year_data.items()):
                print(f"  {season}:")
                for div in sorted(divisions):
                    if 'U11' in div and 'Boys' in div:
                        print(f"    - {div}")
    else:
        print(f"\nFound {len(matches)} matches:\n")
        for match in matches:
            print(f"File: {match['file']}")
            print(f"  Season: {match['season_name']} ({match['year_season']})")
            print(f"  Division: {match['division_name']}")
            if match['type'] == 'team':
                print(f"  Team: {match['team_name']}")
            print()


if __name__ == "__main__":
    import sys
    
    search_term = sys.argv[1] if len(sys.argv) > 1 else "U11 Boys Green"
    search_cached_html(search_term)

