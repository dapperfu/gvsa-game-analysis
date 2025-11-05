#!/usr/bin/env python3
"""
Test script to debug match parsing from HTML files.

This script helps identify why matches aren't being parsed by:
1. Checking for the "Game No" table in HTML files
2. Testing the parser on specific files
3. Showing what the parser finds
"""
from pathlib import Path
from bs4 import BeautifulSoup
from parse_standings import parse_match_results
import sys


def analyze_html_file(html_file: Path) -> None:
    """
    Analyze an HTML file to find match data.
    
    Parameters
    ----------
    html_file : Path
        Path to HTML file to analyze
    """
    print(f"\n{'='*80}")
    print(f"Analyzing: {html_file.name}")
    print(f"{'='*80}")
    
    html_content = html_file.read_text(encoding='utf-8')
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all tables
    all_tables = soup.find_all('table')
    print(f"\nFound {len(all_tables)} table(s)")
    
    for i, table in enumerate(all_tables):
        table_id = table.get('id', 'no id')
        print(f"\nTable {i+1}: id='{table_id}'")
        
        # Check headers
        thead = table.find('thead')
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all(['th', 'td'])]
            print(f"  Headers: {headers}")
        
        # Check first row
        first_row = table.find('tr')
        if first_row:
            first_cells = [cell.get_text(strip=True) for cell in first_row.find_all(['th', 'td'])]
            print(f"  First row: {first_cells}")
        
        # Check for "Game No" text
        table_text = table.get_text()
        if 'Game No' in table_text or 'game no' in table_text.lower():
            print(f"  ✓ Contains 'Game No' text!")
            # Find where it appears
            rows = table.find_all('tr')
            for j, row in enumerate(rows):
                row_text = row.get_text()
                if 'Game No' in row_text or 'game no' in row_text.lower():
                    cells = row.find_all(['th', 'td'])
                    cell_texts = [cell.get_text(strip=True) for cell in cells]
                    print(f"    Row {j} contains 'Game No': {cell_texts}")
                    # Show next few rows
                    for k in range(j+1, min(j+4, len(rows))):
                        next_cells = rows[k].find_all(['th', 'td'])
                        next_texts = [cell.get_text(strip=True) for cell in next_cells]
                        print(f"      Row {k}: {next_texts}")
        
        # Check row count
        rows = table.find_all('tr')
        print(f"  Total rows: {len(rows)}")
    
    # Try parsing
    print(f"\n{'='*80}")
    print("Testing parser...")
    matches = parse_match_results(html_content)
    print(f"Parser found {len(matches)} matches")
    
    if matches:
        print("\nFirst few matches:")
        for match in matches[:3]:
            print(f"  {match}")
    else:
        print("\nNo matches found. Possible reasons:")
        print("  - Table with 'Game No' not found")
        print("  - Table structure doesn't match expected format")
        print("  - Match data not present in this HTML file")


def main() -> None:
    """Main entry point."""
    cache_dir = Path("html_cache")
    
    if len(sys.argv) > 1:
        # Test specific file
        html_file = Path(sys.argv[1])
        if not html_file.exists():
            print(f"Error: File not found: {html_file}")
            return
        analyze_html_file(html_file)
    else:
        # Test a sample file
        if cache_dir.exists():
            # Find a recent HTML file
            html_files = list(cache_dir.rglob("*.html"))
            if html_files:
                # Use the most recent file
                html_file = max(html_files, key=lambda p: p.stat().st_mtime)
                print(f"Testing with: {html_file}")
                analyze_html_file(html_file)
            else:
                print("No HTML files found in cache directory")
        else:
            print("Cache directory not found. Usage:")
            print(f"  {sys.argv[0]} <path_to_html_file>")


if __name__ == "__main__":
    main()

