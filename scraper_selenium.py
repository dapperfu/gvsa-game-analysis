#!/usr/bin/env python3
"""
Selenium-based scraper for GVSA soccer website.

This scraper uses Selenium to fetch fully rendered HTML pages with JavaScript
execution, which is necessary to get the complete standings page including
the match schedule table (row2).
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.service import Service as ChromeService

from parse_seasons import parse_divisions, parse_seasons_list
from parse_standings import parse_standings
from db_pony import GVSA_Database


class GVSAScraperSelenium:
    """
    Selenium-based scraper for GVSA soccer website.
    
    Uses browser automation to fetch fully rendered pages with JavaScript.
    """
    
    BASE_URL = "https://www.gvsoccer.org"
    CACHE_DIR = Path("html_cache")
    
    def __init__(self, browser: str = "firefox", headless: bool = True, delay: float = 2.0) -> None:
        """
        Initialize the Selenium scraper.
        
        Parameters
        ----------
        browser : str
            Browser to use ("firefox" or "chrome", default: "firefox")
        headless : bool
            Run browser in headless mode (default: True)
        delay : float
            Delay between requests in seconds (default: 2.0)
        """
        self.browser_type = browser
        self.headless = headless
        self.delay = delay
        self.driver: Optional[webdriver.Remote] = None
        
        # Create cache directory
        self.CACHE_DIR.mkdir(exist_ok=True)
        
        self._init_driver()
    
    def _init_driver(self) -> None:
        """Initialize the Selenium WebDriver."""
        try:
            if self.browser_type.lower() == "firefox":
                options = FirefoxOptions()
                if self.headless:
                    options.add_argument("--headless")
                options.set_preference("general.useragent.override", 
                                     "Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0")
                service = FirefoxService(GeckoDriverManager().install())
                self.driver = webdriver.Firefox(service=service, options=options)
            else:  # chrome
                options = ChromeOptions()
                if self.headless:
                    options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
            
            self.driver.set_page_load_timeout(30)
            print(f"✓ Initialized {self.browser_type} WebDriver")
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            raise
    
    def close(self) -> None:
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def get_standings_with_selenium(self, division: Dict[str, Any], force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Fetch standings using Selenium to get fully rendered page with matches.
        
        Parameters
        ----------
        division : Dict[str, Any]
            Division dictionary
        force_refresh : bool
            Force refresh even if cached (default: False)
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Parsed standings data or None if request fails
        """
        if not self.driver:
            self._init_driver()
        
        # Check cache first
        if not force_refresh:
            from scraper import GVSAScraper
            html_scraper = GVSAScraper(use_cache=True)
            cached_html = html_scraper.get_cached_html(division)
            if cached_html and 'id="row2"' in cached_html:
                # Already have cached HTML with row2 table
                print(f"  Using cached HTML with row2 table")
                standings_data = parse_standings(cached_html)
                standings_data['division'] = division
                return standings_data
        
        try:
            # Step 1: Go to seasons.jsp first and select Fall 2025
            seasons_url = f"{self.BASE_URL}/seasons.jsp"
            print(f"  Step 1: Loading {seasons_url}...")
            self.driver.get(seasons_url)
            time.sleep(2)
            
            # Select Fall 2025 season
            try:
                season_select = Select(WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "season"))
                ))
                
                # Find Fall 2025
                season_value = None
                for option in season_select.options:
                    if 'Fall 2025' in option.text:
                        season_value = option.get_attribute('value')
                        break
                
                if season_value:
                    season_select.select_by_value(season_value)
                    # Wait for form to auto-submit (if it has onchange)
                    time.sleep(3)
                    print(f"  ✓ Selected Fall 2025 season")
            except (NoSuchElementException, TimeoutException) as e:
                print(f"  ⚠ Could not select season: {e}")
            
            # Step 2: Navigate to standings page
            url = f"{self.BASE_URL}/standings.jsp"
            print(f"  Step 2: Loading {url}...")
            self.driver.get(url)
            time.sleep(2)  # Wait for page to load
            
            # Select division from dropdown
            division_param = (
                f"{division['division_id']},"
                f"{division['year_season']},"
                f"{division['season_id1']},"
                f"{division['season_id2']},"
                f"{division['season_name']},"
                f"{division['division_name']},"
                f"{division['season_type']}"
            )
            
            try:
                division_select = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "division"))
                )
                select = Select(division_select)
                
                # Try to select by value first
                try:
                    select.select_by_value(division_param)
                    print(f"  ✓ Selected division by value")
                except:
                    # Try to find by text
                    found = False
                    for option in select.options:
                        option_text = option.text.strip()
                        if (division['display_name'] in option_text or 
                            division['division_name'] in option_text or
                            division['division_id'] in option.get_attribute('value', '')):
                            option.click()
                            print(f"  ✓ Selected division by text: {option_text}")
                            found = True
                            break
                    
                    if not found:
                        raise ValueError("Division not found in dropdown")
                
                # Wait for page to update (check if form auto-submits)
                time.sleep(2)
                
                # Check if page URL changed or form was submitted
                current_url = self.driver.current_url
                if 'division' not in current_url:
                    # Form might have auto-submitted, wait for it
                    time.sleep(3)
                
                # Wait for both tables to load
                try:
                    WebDriverWait(self.driver, 15).until(
                        lambda d: len(d.find_elements(By.CSS_SELECTOR, "table")) >= 2 or
                                  d.find_elements(By.CSS_SELECTOR, "table#row2")
                    )
                    print(f"  ✓ Tables loaded")
                except TimeoutException:
                    pass
                
            except (NoSuchElementException, TimeoutException, ValueError) as e:
                # Fallback: use direct GET request with division parameter
                print(f"  Dropdown method failed ({e}), using direct URL...")
                self.driver.get(f"{url}?division={division_param}")
                time.sleep(3)
            
            # Wait for tables to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "table"))
                )
            except TimeoutException:
                pass
            
            # Scroll down to trigger lazy loading of match table
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Wait specifically for row2 table
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table#row2"))
                )
                print(f"  ✓ Found row2 table after waiting")
            except TimeoutException:
                # Try waiting for any table with "Game No" header
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//th[contains(text(), 'Game No')]"))
                    )
                    print(f"  ✓ Found 'Game No' header")
                except TimeoutException:
                    pass
            
            # Additional wait for JavaScript to fully render
            time.sleep(3)
            
            # Scroll back up and down again to ensure everything is loaded
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Get the fully rendered HTML
            html_content = self.driver.page_source
            
            # Check if we got the row2 table
            has_row2 = 'id="row2"' in html_content or "id='row2'" in html_content
            if has_row2:
                print(f"  ✓ Found row2 table in rendered HTML!")
            else:
                print(f"  ⚠ No row2 table found (may need more wait time)")
            
            # Save to cache
            from scraper import GVSAScraper
            html_scraper = GVSAScraper(use_cache=True)
            html_scraper.save_html_cache(division, html_content)
            
            # Parse the HTML
            standings_data = parse_standings(html_content)
            standings_data['division'] = division
            
            # Small delay
            time.sleep(self.delay)
            
            return standings_data
            
        except Exception as e:
            print(f"  Error fetching with Selenium: {e}")
            return None
    
    def scrape_divisions_with_matches(self, season_name: str = "Fall 2025", db: Optional[GVSA_Database] = None) -> List[Dict[str, Any]]:
        """
        Scrape divisions for a specific season using Selenium to get matches.
        
        Parameters
        ----------
        season_name : str
            Season name (default: "Fall 2025")
        db : Optional[GVSA_Database]
            Database instance to save data to
            
        Returns
        -------
        List[Dict[str, Any]]
            List of parsed standings data
        """
        if not self.driver:
            self._init_driver()
        
        try:
            # Get seasons and divisions using regular scraper
            from scraper import GVSAScraper
            html_scraper = GVSAScraper(use_cache=True)
            seasons = html_scraper.get_seasons()
            
            # Find the target season
            target_season = None
            for season in seasons:
                if season_name in season.get('season_name', ''):
                    target_season = season
                    break
            
            if not target_season:
                print(f"Season '{season_name}' not found")
                return []
            
            # Get divisions
            divisions = html_scraper.get_divisions(target_season)
            print(f"\nFound {len(divisions)} divisions for {season_name}")
            
            all_standings: List[Dict[str, Any]] = []
            
            # Fetch each division with Selenium
            for i, division in enumerate(divisions, 1):
                print(f"\n[{i}/{len(divisions)}] {division['display_name']}")
                standings = self.get_standings_with_selenium(division, force_refresh=False)
                
                if standings:
                    if db:
                        db.save_standings(standings)
                    
                    teams_count = len(standings.get('teams', []))
                    matches_count = len(standings.get('matches', []))
                    print(f"  ✓ {teams_count} teams, {matches_count} matches")
                    all_standings.append(standings)
                else:
                    print(f"  ✗ Failed to fetch")
            
            return all_standings
            
        finally:
            self.close()


def main() -> None:
    """Main entry point for Selenium scraper."""
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "gvsa_data.db"
    
    print("=" * 80)
    print("Selenium Scraper - Fetching fully rendered pages with matches")
    print("=" * 80)
    
    scraper = GVSAScraperSelenium(browser="firefox", headless=True, delay=2.0)
    db = GVSA_Database(db_path)
    
    try:
        standings = scraper.scrape_divisions_with_matches(season_name="Fall 2025", db=db)
        
        print(f"\n{'='*80}")
        print("Scraping Summary:")
        print(f"  Divisions processed: {len(standings)}")
        total_teams = sum(len(s.get('teams', [])) for s in standings)
        total_matches = sum(len(s.get('matches', [])) for s in standings)
        print(f"  Total teams: {total_teams}")
        print(f"  Total matches: {total_matches}")
        print(f"  Database saved to: {db_path}")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()

