#!/usr/bin/env python3
"""
Main scraper for GVSA soccer website.

This module scrapes the gvsoccer.org website to extract teams and match results
for all divisions. It handles the frame-based structure by making direct requests
to the JSP endpoints.
"""
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
import time
import sys
from pathlib import Path

from parse_seasons import parse_divisions
from parse_standings import parse_standings
from database import GVSADatabase


class GVSAScraper:
    """
    Scraper for GVSA soccer website.
    
    This class handles all scraping operations including fetching
    division lists and standings data.
    """
    
    BASE_URL = "https://www.gvsoccer.org"
    
    def __init__(self, delay: float = 1.0) -> None:
        """
        Initialize the scraper.
        
        Parameters
        ----------
        delay : float
            Delay between requests in seconds (default: 1.0)
        """
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def get_divisions(self) -> List[Dict[str, Any]]:
        """
        Fetch and parse all available divisions.
        
        Returns
        -------
        List[Dict[str, Any]]
            List of division dictionaries
        """
        url = f"{self.BASE_URL}/seasons.jsp"
        print(f"Fetching divisions from {url}...")
        
        try:
            response = self.session.post(url, data={'seasons.x': '64', 'seasons.y': '13'})
            response.raise_for_status()
            response.encoding = 'ISO-8859-1'  # Website uses ISO-8859-1
            
            divisions = parse_divisions(response.text)
            print(f"Found {len(divisions)} divisions")
            return divisions
        except requests.RequestException as e:
            print(f"Error fetching divisions: {e}")
            return []
    
    def get_standings(self, division: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch standings for a specific division.
        
        Parameters
        ----------
        division : Dict[str, Any]
            Division dictionary from get_divisions()
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Parsed standings data or None if request fails
        """
        url = f"{self.BASE_URL}/standings.jsp"
        
        # Build division parameter
        division_param = (
            f"{division['division_id']},"
            f"{division['year_season']},"
            f"{division['season_id1']},"
            f"{division['season_id2']},"
            f"{division['season_name']},"
            f"{division['division_name']},"
            f"{division['season_type']}"
        )
        
        print(f"Fetching standings for: {division['display_name']}")
        
        try:
            response = self.session.post(url, data={'division': division_param})
            response.raise_for_status()
            response.encoding = 'ISO-8859-1'
            
            time.sleep(self.delay)  # Be polite to the server
            
            standings_data = parse_standings(response.text)
            standings_data['division'] = division
            
            print(f"  - Found {len(standings_data['teams'])} teams")
            print(f"  - Found {len(standings_data['matches'])} matches")
            
            return standings_data
        except requests.RequestException as e:
            print(f"Error fetching standings for {division['display_name']}: {e}")
            return None
    
    def scrape_all(self, db: Optional[GVSADatabase] = None) -> List[Dict[str, Any]]:
        """
        Scrape all divisions and their standings.
        
        Parameters
        ----------
        db : Optional[GVSADatabase]
            Database instance to save data to (optional)
        
        Returns
        -------
        List[Dict[str, Any]]
            List of standings data for all divisions
        """
        divisions = self.get_divisions()
        if not divisions:
            print("No divisions found, cannot continue")
            return []
        
        all_standings: List[Dict[str, Any]] = []
        
        for i, division in enumerate(divisions, 1):
            print(f"\n[{i}/{len(divisions)}] Processing: {division['display_name']}")
            standings = self.get_standings(division)
            if standings:
                all_standings.append(standings)
                if db:
                    db.save_standings(standings)
        
        return all_standings


def main() -> None:
    """
    Main entry point for the scraper.
    """
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "gvsa_data.db"
    
    scraper = GVSAScraper(delay=1.0)
    
    with GVSADatabase(db_path) as db:
        standings = scraper.scrape_all(db=db)
        
        print(f"\n{'='*80}")
        print(f"Scraping complete!")
        print(f"Successfully scraped {len(standings)} divisions")
        
        # Print summary
        total_teams = sum(len(s['teams']) for s in standings)
        total_matches = sum(len(s['matches']) for s in standings)
        print(f"Total teams: {total_teams}")
        print(f"Total matches: {total_matches}")
        print(f"Database saved to: {db_path}")


if __name__ == "__main__":
    main()

