#!/usr/bin/env python3
"""
Capture the exact POST request format for standings.jsp and analyze the response.
"""
import requests
from bs4 import BeautifulSoup
import sys

BASE_URL = "https://www.gvsoccer.org"

def test_standings_request() -> None:
    """Make a test request to standings.jsp and show the exact format."""
    
    # Test division: U11 Boys 5th Division
    division_param = "2811,2025/2026,2775,2846,Fall 2025,U11 Boys 5th Division,F"
    
    url = f"{BASE_URL}/standings.jsp"
    
    print("=" * 80)
    print("Testing standings.jsp POST Request")
    print("=" * 80)
    print(f"\nURL: {url}")
    print(f"Method: POST")
    print(f"Data: division={division_param}")
    print(f"\nFull POST data string:")
    print(f"division={division_param}")
    
    # Make the request
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://www.gvsoccer.org/seasons.jsp',
    }
    
    print(f"\nHeaders:")
    for key, value in headers.items():
        print(f"  {key}: {value}")
    
    print("\nMaking request...")
    try:
        response = requests.post(url, data={'division': division_param}, headers=headers, timeout=30)
        response.encoding = 'ISO-8859-1'
        html = response.text
        
        print(f"\nResponse:")
        print(f"  Status: {response.status_code}")
        print(f"  Length: {len(html)} characters")
        print(f"  Content-Type: {response.headers.get('content-type', 'unknown')}")
        
        # Check for row2
        has_row2 = 'id="row2"' in html or "id='row2'" in html
        print(f"\n  Has row2 table: {has_row2}")
        
        if has_row2:
            print("  ✓✓✓ FOUND row2 TABLE! ✓✓✓")
            
            # Extract the table
            soup = BeautifulSoup(html, 'html.parser')
            row2_table = soup.find('table', id='row2')
            if row2_table:
                rows = row2_table.find_all('tr')
                print(f"  Found {len(rows)} rows in row2 table")
                
                # Show first few rows
                print(f"\n  First 3 rows of row2 table:")
                for i, row in enumerate(rows[:3]):
                    cells = [cell.get_text(strip=True) for cell in row.find_all(['th', 'td'])]
                    print(f"    Row {i+1}: {cells[:5]}...")
        else:
            print("  ✗ No row2 table found")
            
            # Check what tables we have
            soup = BeautifulSoup(html, 'html.parser')
            tables = soup.find_all('table')
            print(f"\n  Found {len(tables)} tables:")
            for table in tables:
                table_id = table.get('id', 'no id')
                rows = table.find_all('tr')
                print(f"    Table id='{table_id}': {len(rows)} rows")
                
                # Check if this table has match data
                table_text = table.get_text()
                if 'Game No' in table_text or 'Date' in table_text:
                    print(f"      ⚠ This table might contain match data!")
                    # Show first row
                    first_row = rows[0] if rows else None
                    if first_row:
                        cells = [cell.get_text(strip=True) for cell in first_row.find_all(['th', 'td'])]
                        print(f"      Headers: {cells}")
        
        # Save to file for inspection
        output_file = "/tmp/standings_response.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\n  Response saved to: {output_file}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_standings_request()


