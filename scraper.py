#!/usr/bin/env python3
"""
Main scraper for GVSA soccer website.

This module scrapes the gvsoccer.org website to extract teams and match results
for all divisions. It handles the frame-based structure by making direct requests
to the JSP endpoints.
"""
from typing import List, Dict, Any, Optional, Tuple
import requests
import time
import re
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from parse_seasons import parse_divisions, parse_seasons_list
from parse_standings import parse_standings
from parse_csv import parse_csv_standings, download_csv_standings
from db_pony import GVSA_Database


class GVSAScraper:
    """
    Scraper for GVSA soccer website.
    
    This class handles all scraping operations including fetching
    division lists and standings data.
    """
    
    BASE_URL = "https://www.gvsoccer.org"
    CACHE_DIR = Path("html_cache")
    
    def __init__(self, delay: float = 1.0, use_cache: bool = True, max_workers: int = 5) -> None:
        """
        Initialize the scraper.
        
        Parameters
        ----------
        delay : float
            Delay between requests in seconds (default: 1.0)
        use_cache : bool
            Whether to use cached HTML files (default: True)
        max_workers : int
            Maximum number of parallel workers for fetching (default: 5)
        """
        self.delay = delay
        self.use_cache = use_cache
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Create cache directory if it doesn't exist
        if self.use_cache:
            self.CACHE_DIR.mkdir(exist_ok=True)
        
        # Thread lock for cache operations (though file I/O is generally safe)
        self.cache_lock = Lock()
    
    @staticmethod
    def sanitize_filename(name: str) -> str:
        """
        Sanitize a string to be used as a filename.
        
        Parameters
        ----------
        name : str
            String to sanitize
            
        Returns
        -------
        str
            Sanitized filename-safe string
        """
        # Remove or replace invalid filename characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        sanitized = re.sub(r'\s+', '_', sanitized)
        sanitized = sanitized.strip('._')
        return sanitized
    
    def get_cache_path(self, division: Dict[str, Any]) -> Tuple[Path, Path]:
        """
        Get the cache file paths for a division (HTML and metadata).
        
        Structure: html_cache/{year}_{season_type}/{division_name}.html
        Metadata: html_cache/{year}_{season_type}/{division_name}.json
        
        Examples: html_cache/2025_Fall/, html_cache/2025_Spring/
        
        Parameters
        ----------
        division : Dict[str, Any]
            Division dictionary
            
        Returns
        -------
        tuple[Path, Path]
            Tuple of (HTML file path, metadata JSON file path)
        """
        # Extract year from season_name (e.g., "Fall 2025" -> "2025")
        season_name = division.get('season_name', '')
        year = 'unknown'
        if season_name:
            # Try to extract year from season_name (e.g., "Fall 2025" -> "2025")
            year_match = re.search(r'\b(20\d{2})\b', season_name)
            if year_match:
                year = year_match.group(1)
        
        # Get season type: "F" -> "Fall", "S" -> "Spring"
        season_type_code = division.get('season_type', 'F')
        season_type = 'Fall' if season_type_code == 'F' else 'Spring'
        
        # Create cache directory: {year}_{season_type}
        cache_dir_name = f"{year}_{season_type}"
        division_name = self.sanitize_filename(division.get('division_name', division.get('display_name', 'unknown')))
        
        cache_dir = self.CACHE_DIR / cache_dir_name
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        html_path = cache_dir / f"{division_name}.html"
        json_path = cache_dir / f"{division_name}.json"
        
        return (html_path, json_path)
    
    def get_cached_html(self, division: Dict[str, Any]) -> Optional[str]:
        """
        Get cached HTML for a division if it exists.
        
        Parameters
        ----------
        division : Dict[str, Any]
            Division dictionary
            
        Returns
        -------
        Optional[str]
            Cached HTML content or None if not found
        """
        if not self.use_cache:
            return None
        
        html_path, _ = self.get_cache_path(division)
        
        with self.cache_lock:
            if html_path.exists():
                try:
                    content = html_path.read_text(encoding='utf-8')
                    return content
                except Exception as e:
                    print(f"  - Error reading cache: {e}")
                    return None
        
        return None
    
    def get_cached_metadata(self, division: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached metadata for a division if it exists.
        
        Parameters
        ----------
        division : Dict[str, Any]
            Division dictionary
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Cached metadata or None if not found
        """
        if not self.use_cache:
            return None
        
        _, json_path = self.get_cache_path(division)
        
        with self.cache_lock:
            if json_path.exists():
                try:
                    content = json_path.read_text(encoding='utf-8')
                    return json.loads(content)
                except Exception as e:
                    print(f"  - Error reading metadata: {e}")
                    return None
        
        return None
    
    def save_html_cache(self, division: Dict[str, Any], html_content: str) -> None:
        """
        Save HTML content and metadata to cache.
        
        Parameters
        ----------
        division : Dict[str, Any]
            Division dictionary
        html_content : str
            HTML content to cache
        """
        if not self.use_cache:
            return
        
        html_path, json_path = self.get_cache_path(division)
        
        with self.cache_lock:
            try:
                # Save HTML
                html_path.write_text(html_content, encoding='utf-8')
                
                # Save metadata (division info)
                # Extract year from season_name (e.g., "Spring 2019" -> "2019")
                season_name = division.get('season_name', '')
                year = 'unknown'
                if season_name:
                    year_match = re.search(r'\b(20\d{2})\b', season_name)
                    if year_match:
                        year = year_match.group(1)
                
                # Normalize season_type: "F" -> "Fall", "S" -> "Spring"
                season_type_code = division.get('season_type', 'F')
                # Also check season_name to ensure correctness
                if 'Spring' in season_name:
                    season_type = 'Spring'
                elif 'Fall' in season_name:
                    season_type = 'Fall'
                else:
                    season_type = 'Fall' if season_type_code == 'F' else 'Spring'
                
                division_name = division.get('division_name', division.get('display_name', ''))
                
                metadata = {
                    'division_id': division.get('division_id', ''),
                    'year': year,
                    'season_id1': division.get('season_id1', ''),
                    'season_id2': division.get('season_id2', ''),
                    'season_name': season_name,
                    'division_name': division_name,
                    'season_type': season_type
                }
                json_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
            except Exception as e:
                print(f"  - Error saving cache: {e}")
    
    def get_seasons(self) -> List[Dict[str, str]]:
        """
        Fetch and parse all available seasons.
        
        Returns
        -------
        List[Dict[str, str]]
            List of season dictionaries
        """
        url = f"{self.BASE_URL}/seasons.jsp"
        print(f"Fetching seasons from {url}...")
        
        try:
            response = self.session.post(url, data={'seasons.x': '64', 'seasons.y': '13'})
            response.raise_for_status()
            response.encoding = 'ISO-8859-1'
            
            seasons = parse_seasons_list(response.text)
            print(f"Found {len(seasons)} seasons")
            return seasons
        except requests.RequestException as e:
            print(f"Error fetching seasons: {e}")
            return []
    
    def get_divisions(self, season: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """
        Fetch and parse all available divisions for a specific season.
        
        Parameters
        ----------
        season : Optional[Dict[str, str]]
            Season to fetch divisions for. If None, fetches current/default season.
        
        Returns
        -------
        List[Dict[str, Any]]
            List of division dictionaries
        """
        url = f"{self.BASE_URL}/seasons.jsp"
        print(f"Fetching divisions from {url}...")
        
        try:
            # If season specified, try to select it
            post_data = {'seasons.x': '64', 'seasons.y': '13'}
            if season and season.get('season_value'):
                # Use the stored season value directly
                post_data['season'] = season['season_value']
            
            response = self.session.post(url, data=post_data)
            response.raise_for_status()
            response.encoding = 'ISO-8859-1'
            
            divisions = parse_divisions(response.text)
            if season:
                print(f"Found {len(divisions)} divisions for {season['season_name']}")
            else:
                print(f"Found {len(divisions)} divisions")
            return divisions
        except requests.RequestException as e:
            print(f"Error fetching divisions: {e}")
            return []
    
    def get_standings(self, division: Dict[str, Any], force_refresh: bool = False, use_csv: bool = True) -> Optional[Dict[str, Any]]:
        """
        Fetch standings for a specific division, using cache if available.
        
        Can optionally try to download CSV data first for more reliable parsing.
        
        Parameters
        ----------
        division : Dict[str, Any]
            Division dictionary from get_divisions()
        force_refresh : bool
            Force refresh even if cached (default: False)
        use_csv : bool
            Try to download CSV data first (default: True)
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Parsed standings data or None if request fails
        """
        url = f"{self.BASE_URL}/standings.jsp"
        
        # Build division parameter with exact spacing/padding as seen in mitm logs
        # Format: "      2843,2025/2026 ,      2775,      2846,Fall 2025                     ,U17/18/19 Girls Elite         ,F"
        # IDs: 10 chars (7 spaces + 3-4 digits), Names: 30 chars, Year: 10 chars (with trailing space)
        division_param = (
            f"{str(division['division_id']):>10},"
            f"{division['year_season']} ,"
            f"{str(division['season_id1']):>10},"
            f"{str(division['season_id2']):>10},"
            f"{division['season_name']:<30},"
            f"{division['division_name']:<30},"
            f"{division['season_type']}"
        )
        
        # Try CSV download first if requested
        if use_csv:
            session = requests.Session()
            session.headers.update(self.session.headers)
            try:
                csv_content = download_csv_standings(url, division_param, session)
                if csv_content:
                    # Successfully got CSV data
                    standings_data = parse_csv_standings(csv_content)
                    standings_data['division'] = division
                    session.close()
                    return standings_data
            except Exception as e:
                # CSV download failed, fall back to HTML
                pass
            finally:
                session.close()
        
        html_content: Optional[str] = None
        
        # Try to get from cache first
        if not force_refresh:
            html_content = self.get_cached_html(division)
            if html_content:
                # Using cache - no delay needed
                pass
        
        # Fetch from web if not cached
        if html_content is None:
            # Create a new session for thread safety
            session = requests.Session()
            session.headers.update(self.session.headers)
            
            try:
                response = session.post(url, data={'division': division_param}, timeout=30)
                response.raise_for_status()
                response.encoding = 'ISO-8859-1'
                html_content = response.text
                
                # Save to cache
                self.save_html_cache(division, html_content)
                
                # Small delay to be polite to the server (only for network requests)
                time.sleep(self.delay)
            except requests.RequestException as e:
                display_name = division.get('display_name', division.get('division_name', 'unknown'))
                print(f"Error fetching standings for {display_name}: {e}")
                return None
            finally:
                session.close()
        
        # Parse the HTML (from cache or fresh)
        standings_data = parse_standings(html_content)
        standings_data['division'] = division
        
        return standings_data
    
    def _process_division(self, division: Dict[str, Any], div_idx: int, total: int, db: Optional[GVSA_Database] = None) -> Optional[Dict[str, Any]]:
        """
        Process a single division (used by parallel processing).
        
        Parameters
        ----------
        division : Dict[str, Any]
            Division dictionary
        div_idx : int
            Division index (for display)
        total : int
            Total number of divisions (for display)
        db : Optional[GVSA_Database]
            Database instance to save data to (optional)
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Parsed standings data or None if request fails
        """
        display_name = division.get('display_name', division.get('division_name', 'unknown'))
        standings = self.get_standings(division, force_refresh=False)
        
        if standings:
            # Save to database immediately in this thread (PonyORM handles thread safety)
            if db:
                db.save_standings(standings)
            print(f"[{div_idx}/{total}] ✓ {display_name}: {len(standings['teams'])} teams, {len(standings['matches'])} matches")
        else:
            print(f"[{div_idx}/{total}] ✗ {display_name}: Failed to fetch")
        
        return standings
    
    def fetch_html_only(self) -> int:
        """
        Stage 1: Fetch and save all HTML files without parsing.
        This hits the server once to cache all HTML files.
        Skips divisions that are already cached.
        
        Returns
        -------
        int
            Number of HTML files fetched/cached (newly fetched, not already cached)
        """
        # First, get all available seasons
        seasons = self.get_seasons()
        
        if not seasons:
            # Fallback: try to get divisions without season selection
            print("No seasons found, trying to get divisions directly...")
            divisions = self.get_divisions()
            if not divisions:
                print("No divisions found, cannot continue")
                return 0
            seasons = [None]  # Use None to indicate no season filtering
        
        total_fetched = 0
        total_divisions = 0
        total_cached = 0
        
        # Fetch each season
        for season_idx, season in enumerate(seasons, 1):
            if season:
                print(f"\n{'='*80}")
                print(f"Season {season_idx}/{len(seasons)}: {season['season_name']}")
                print(f"{'='*80}")
            
            # Get divisions for this season
            divisions = self.get_divisions(season)
            if not divisions:
                print("No divisions found for this season, skipping...")
                continue
            
            total_divisions += len(divisions)
            
            # Check how many are already cached
            cached_count = sum(1 for div in divisions if self.get_cached_html(div))
            total_cached += cached_count
            
            if cached_count == len(divisions):
                print(f"\n✓ All {len(divisions)} divisions already cached, skipping...")
                continue
            
            # Fetch HTML in parallel (but don't parse)
            remaining = len(divisions) - cached_count
            print(f"\nFetching HTML for {remaining} divisions ({(len(divisions) - cached_count)} new, {cached_count} already cached) with {self.max_workers} workers...")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                futures = {
                    executor.submit(
                        self._fetch_html_only,
                        division,
                        div_idx + 1,
                        len(divisions)
                    ): (div_idx, division)
                    for div_idx, division in enumerate(divisions)
                }
                
                # Collect results as they complete
                for future in as_completed(futures):
                    div_idx, division = futures[future]
                    try:
                        fetched = future.result()
                        if fetched:
                            total_fetched += 1
                    except Exception as e:
                        display_name = division.get('display_name', division.get('division_name', 'unknown'))
                        print(f"Error fetching HTML for {display_name}: {e}")
        
        print(f"\n{'='*80}")
        print("HTML Fetching Summary:")
        print(f"  Seasons processed: {len(seasons)}")
        print(f"  Total divisions: {total_divisions}")
        print(f"  Already cached: {total_cached}")
        print(f"  HTML files newly fetched: {total_fetched}")
        
        return total_fetched
    
    def _fetch_html_only(self, division: Dict[str, Any], div_idx: int, total: int) -> bool:
        """
        Fetch and save HTML for a single division without parsing.
        
        Parameters
        ----------
        division : Dict[str, Any]
            Division dictionary
        div_idx : int
            Division index (for display)
        total : int
            Total number of divisions (for display)
            
        Returns
        -------
        bool
            True if HTML was fetched/saved, False otherwise
        """
        display_name = division.get('display_name', division.get('division_name', 'unknown'))
        
        # Check if already cached
        if self.get_cached_html(division):
            print(f"[{div_idx}/{total}] ⊘ {display_name}: Already cached")
            return False
        
        # Fetch from web
        url = f"{self.BASE_URL}/standings.jsp"
        # Build division parameter with exact spacing/padding as seen in mitm logs
        # Format: "      2843,2025/2026 ,      2775,      2846,Fall 2025                     ,U17/18/19 Girls Elite         ,F"
        # IDs: 10 chars (7 spaces + 3-4 digits), Names: 30 chars, Year: 10 chars (with trailing space)
        division_param = (
            f"{str(division['division_id']):>10},"
            f"{division['year_season']} ,"
            f"{str(division['season_id1']):>10},"
            f"{str(division['season_id2']):>10},"
            f"{division['season_name']:<30},"
            f"{division['division_name']:<30},"
            f"{division['season_type']}"
        )
        
        # Create a new session for thread safety
        session = requests.Session()
        session.headers.update(self.session.headers)
        
        try:
            response = session.post(url, data={'division': division_param}, timeout=30)
            response.raise_for_status()
            response.encoding = 'ISO-8859-1'
            html_content = response.text
            
            # Save to cache
            self.save_html_cache(division, html_content)
            
            print(f"[{div_idx}/{total}] ✓ {display_name}: Fetched and cached")
            time.sleep(self.delay)  # Be polite to the server
            return True
        except requests.RequestException as e:
            print(f"[{div_idx}/{total}] ✗ {display_name}: Failed to fetch - {e}")
            return False
        finally:
            session.close()
    
    def parse_cached_html(self, db: Optional[GVSA_Database] = None) -> List[Dict[str, Any]]:
        """
        Stage 2: Parse all cached HTML files and populate database.
        This does NOT hit the server - only reads cached files.
        
        Parameters
        ----------
        db : Optional[GVSA_Database]
            Database instance to save data to (optional)
            
        Returns
        -------
        List[Dict[str, Any]]
            List of parsed standings data
        """
        # Find all cached HTML files
        if not self.CACHE_DIR.exists():
            print(f"Cache directory {self.CACHE_DIR} does not exist. Run fetch_html_only() first.")
            return []
        
        all_standings: List[Dict[str, Any]] = []
        
        # Walk through cache directory structure: html_cache/{year}_{season_type}/*.html
        cache_files = list(self.CACHE_DIR.rglob("*.html"))
        
        if not cache_files:
            print("No cached HTML files found. Run fetch_html_only() first.")
            return []
        
        print(f"\n{'='*80}")
        print(f"Found {len(cache_files)} cached HTML files")
        print(f"{'='*80}")
        print(f"\nParsing cached HTML files with {self.max_workers} workers...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all parsing tasks
            futures = {
                executor.submit(
                    self._parse_cached_file,
                    cache_file,
                    idx + 1,
                    len(cache_files),
                    db
                ): (idx, cache_file)
                for idx, cache_file in enumerate(cache_files)
            }
            
            # Collect results as they complete
            for future in as_completed(futures):
                idx, cache_file = futures[future]
                try:
                    standings = future.result()
                    if standings:
                        all_standings.append(standings)
                except Exception as e:
                    print(f"Error parsing {cache_file}: {e}")
        
        print(f"\n{'='*80}")
        print("Parsing Summary:")
        print(f"  Cached files processed: {len(cache_files)}")
        print(f"  Successfully parsed: {len(all_standings)}")
        
        return all_standings
    
    def _parse_cached_file(self, cache_file: Path, idx: int, total: int, db: Optional[GVSA_Database] = None) -> Optional[Dict[str, Any]]:
        """
        Parse a single cached HTML file.
        
        Parameters
        ----------
        cache_file : Path
            Path to cached HTML file
        idx : int
            File index (for display)
        total : int
            Total number of files (for display)
        db : Optional[GVSA_Database]
            Database instance to save data to (optional)
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Parsed standings data or None if parsing fails
        """
        try:
            # Read cached HTML
            html_content = cache_file.read_text(encoding='utf-8')
            
            # Read metadata JSON (should exist alongside HTML)
            metadata_path = cache_file.with_suffix('.json')
            division_info: Dict[str, Any] = {}
            
            if metadata_path.exists():
                try:
                    metadata_content = metadata_path.read_text(encoding='utf-8')
                    division_info = json.loads(metadata_content)
                    # Handle old metadata format with year_season
                    if 'year_season' in division_info and 'year' not in division_info:
                        year_season = division_info.get('year_season', '')
                        if '/' in year_season:
                            division_info['year'] = year_season.split('/')[0]
                        else:
                            division_info['year'] = year_season
                    # Normalize season_type if it's "F" or "S"
                    if division_info.get('season_type') == 'F':
                        division_info['season_type'] = 'Fall'
                    elif division_info.get('season_type') == 'S':
                        division_info['season_type'] = 'Spring'
                    # Remove display_name if present (redundant with division_name)
                    if 'display_name' in division_info:
                        del division_info['display_name']
                    # Ensure division_id is present (Required field)
                    if 'division_id' not in division_info:
                        division_info['division_id'] = ''
                except Exception as e:
                    print(f"  - Warning: Could not read metadata for {cache_file.name}: {e}")
                    # Fall back to reconstructing from path
                    # New structure: html_cache/{year}_{season_type}/{division_name}.html
                    parts = cache_file.parts
                    if len(parts) >= 2:
                        cache_dir_name = parts[-2]  # e.g., "2025_Fall"
                        # Parse year and season type from directory name
                        if '_' in cache_dir_name:
                            year_str, season_type_str = cache_dir_name.rsplit('_', 1)
                            # Normalize season_type to "Fall" or "Spring"
                            season_type = season_type_str  # Already normalized in cache path
                            season_name = f"{season_type_str} {year_str}"
                            division_info = {
                                'division_id': '',  # Required field, set to empty if not available
                                'year': year_str,
                                'season_name': season_name,
                                'division_name': cache_file.stem.replace('_', ' '),
                                'season_type': season_type
                            }
                        else:
                            # Fallback for old format
                            division_info = {
                                'division_id': '',
                                'year': cache_dir_name,
                                'season_name': cache_dir_name,
                                'division_name': cache_file.stem.replace('_', ' '),
                                'season_type': 'Fall'
                            }
            else:
                # No metadata file - reconstruct from path
                # New structure: html_cache/{year}_{season_type}/{division_name}.html
                parts = cache_file.parts
                if len(parts) >= 2:
                    cache_dir_name = parts[-2]  # e.g., "2025_Fall"
                    # Parse year and season type from directory name
                    if '_' in cache_dir_name:
                        year_str, season_type_str = cache_dir_name.rsplit('_', 1)
                        # Normalize season_type to "Fall" or "Spring"
                        season_type = season_type_str  # Already normalized in cache path
                        season_name = f"{season_type_str} {year_str}"
                        division_info = {
                            'division_id': '',
                            'year': year_str,
                            'season_name': season_name,
                            'division_name': cache_file.stem.replace('_', ' '),
                            'season_type': season_type
                        }
                    else:
                        # Fallback for old format
                        division_info = {
                            'division_id': '',
                            'year': cache_dir_name,
                            'season_name': cache_dir_name,
                            'division_name': cache_file.stem.replace('_', ' '),
                            'season_type': 'Fall'
                        }
            
            # Parse HTML
            standings_data = parse_standings(html_content)
            standings_data['division'] = division_info
            
            # Save to database
            if db:
                db.save_standings(standings_data)
            
            print(f"[{idx}/{total}] ✓ {cache_file.name}: {len(standings_data['teams'])} teams, {len(standings_data['matches'])} matches")
            return standings_data
        except Exception as e:
            print(f"[{idx}/{total}] ✗ {cache_file.name}: Error - {e}")
            return None
    
    def scrape_all(self, db: Optional[GVSA_Database] = None) -> List[Dict[str, Any]]:
        """
        Scrape all seasons, all divisions, and their standings.
        
        Parameters
        ----------
        db : Optional[GVSA_Database]
            Database instance to save data to (optional)
        
        Returns
        -------
        List[Dict[str, Any]]
            List of standings data for all divisions
        """
        # First, get all available seasons
        seasons = self.get_seasons()
        
        if not seasons:
            # Fallback: try to get divisions without season selection
            print("No seasons found, trying to get divisions directly...")
            divisions = self.get_divisions()
            if not divisions:
                print("No divisions found, cannot continue")
                return []
            seasons = [None]  # Use None to indicate no season filtering
        
        all_standings: List[Dict[str, Any]] = []
        total_divisions = 0
        
        # Scrape each season
        for season_idx, season in enumerate(seasons, 1):
            if season:
                print(f"\n{'='*80}")
                print(f"Season {season_idx}/{len(seasons)}: {season['season_name']}")
                print(f"{'='*80}")
            
            # Get divisions for this season
            divisions = self.get_divisions(season)
            if not divisions:
                print("No divisions found for this season, skipping...")
                continue
            
            total_divisions += len(divisions)
            
            # Process divisions in parallel
            print(f"\nProcessing {len(divisions)} divisions with {self.max_workers} workers...")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                futures = {
                    executor.submit(
                        self._process_division,
                        division,
                        div_idx + 1,
                        len(divisions),
                        db
                    ): (div_idx, division)
                    for div_idx, division in enumerate(divisions)
                }
                
                # Collect results as they complete
                for future in as_completed(futures):
                    div_idx, division = futures[future]
                    try:
                        standings = future.result()
                        if standings:
                            all_standings.append(standings)
                    except Exception as e:
                        display_name = division.get('display_name', division.get('division_name', 'unknown'))
                        print(f"Error processing {display_name}: {e}")
        
        print(f"\n{'='*80}")
        print("Scraping Summary:")
        print(f"  Seasons processed: {len(seasons)}")
        print(f"  Total divisions: {total_divisions}")
        print(f"  Successfully scraped: {len(all_standings)}")
        
        return all_standings


def main() -> None:
    """
    Main entry point for the scraper.
    
    Two-stage process:
    1. fetch_html_only() - Fetches and saves all HTML files (hits server once)
    2. parse_cached_html() - Parses cached HTML and populates database (no server hits)
    """
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "gvsa_data.db"
    
    # Use more workers for faster processing (adjust based on your needs)
    scraper = GVSAScraper(delay=1.0, use_cache=True, max_workers=5)
    db = GVSA_Database(db_path)
    
    print("=" * 80)
    print("STAGE 1: Fetching HTML files from server")
    print("=" * 80)
    fetched_count = scraper.fetch_html_only()
    
    print(f"\n{'='*80}")
    print("STAGE 2: Parsing cached HTML files and populating database")
    print("=" * 80)
    standings = scraper.parse_cached_html(db=db)
    
    print(f"\n{'='*80}")
    print("Scraping complete!")
    print(f"HTML files fetched: {fetched_count}")
    print(f"Successfully parsed: {len(standings)} divisions")
    
    # Print summary
    total_teams = sum(len(s['teams']) for s in standings)
    total_matches = sum(len(s['matches']) for s in standings)
    print(f"Total teams: {total_teams}")
    print(f"Total matches: {total_matches}")
    print(f"Database saved to: {db_path}")


if __name__ == "__main__":
    main()

