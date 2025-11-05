#!/usr/bin/env python3
"""
Check mitmproxy logs for standings.jsp POST requests and responses.
Extract the exact request format and response HTML with row2 table.
"""
from mitmproxy import http, io
from mitmproxy.exceptions import FlowReadException
from pathlib import Path
import sys
import re


def find_standings_flows(log_file: Path) -> list:
    """
    Find all standings.jsp flows in the mitmproxy log.
    
    Parameters
    ----------
    log_file : Path
        Path to mitmproxy log file
        
    Returns
    -------
    list
        List of HTTPFlow objects for standings.jsp
    """
    standings_flows = []
    
    try:
        with open(log_file, "rb") as f:
            reader = io.FlowReader(f)
            try:
                for flow_obj in reader.stream():
                    if isinstance(flow_obj, http.HTTPFlow):
                        request = flow_obj.request
                        if 'standings.jsp' in request.pretty_url:
                            standings_flows.append(flow_obj)
            except FlowReadException as e:
                print(f"Error reading flow: {e}")
    except Exception as e:
        print(f"Error opening log file: {e}")
        return []
    
    return standings_flows


def analyze_standings_flow(flow_obj: http.HTTPFlow) -> None:
    """
    Analyze a standings.jsp flow to show request and response.
    
    Parameters
    ----------
    flow_obj : http.HTTPFlow
        The HTTP flow to analyze
    """
    request = flow_obj.request
    response = flow_obj.response
    
    print("=" * 80)
    print(f"URL: {request.pretty_url}")
    print(f"Method: {request.method}")
    
    # Show POST data
    if request.method == "POST":
        print(f"\nPOST Data:")
        if request.content:
            try:
                content = request.content.decode('utf-8', errors='ignore')
                print(f"  {content}")
                
                # Parse division parameter
                if 'division=' in content:
                    division_param = content.split('division=')[1].split('&')[0]
                    print(f"\nDivision Parameter:")
                    print(f"  {division_param}")
            except:
                print(f"  {len(request.content)} bytes (binary)")
        
        # Also check form data
        if request.urlencoded_form:
            print(f"\nForm Data:")
            for key, value in request.urlencoded_form.items():
                print(f"  {key}: {value[:200]}")
    
    # Show response
    if response:
        print(f"\nResponse Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
        
        if response.content:
            try:
                html_content = response.content.decode('ISO-8859-1', errors='ignore')
                print(f"Response Length: {len(html_content)} characters")
                
                # Check for row2 table
                has_row2 = 'id="row2"' in html_content or "id='row2'" in html_content
                print(f"Has row2 table: {has_row2}")
                
                if has_row2:
                    print("\n✓✓✓ FOUND row2 TABLE! ✓✓✓")
                    # Find the table
                    import re
                    match = re.search(r'<table[^>]*id=["\']row2["\'][^>]*>.*?</table>', html_content, re.DOTALL)
                    if match:
                        table_html = match.group(0)
                        print(f"\nrow2 Table (first 1000 chars):")
                        print(table_html[:1000])
                
                # Check for "Game No"
                if 'Game No' in html_content:
                    print("\n'Game No' text found in response")
                    idx = html_content.find('Game No')
                    context = html_content[max(0, idx-200):idx+1000]
                    print(f"\nContext around 'Game No':")
                    print(context[:800])
                
                # Count tables
                table_count = html_content.count('<table')
                print(f"\nTotal <table> tags: {table_count}")
                
                # Show table IDs
                table_ids = re.findall(r'<table[^>]*id=["\']([^"\']+)["\']', html_content)
                print(f"Table IDs found: {table_ids}")
                
            except Exception as e:
                print(f"Error decoding response: {e}")
    else:
        print("\nNo response")


def main() -> None:
    """Main function."""
    # Look for mitm log files
    log_files = []
    
    # Check common locations
    possible_logs = [
        Path("mitm_logs/mitm_20251103_160133.log"),
        Path("mitm_logs"),
        Path("."),
    ]
    
    for location in possible_logs:
        if location.is_file():
            log_files.append(location)
        elif location.is_dir():
            log_files.extend(location.glob("*.log"))
            log_files.extend(location.glob("mitm*"))
    
    # Also check command line argument
    if len(sys.argv) > 1:
        log_files = [Path(sys.argv[1])]
    
    if not log_files:
        print("No mitmproxy log files found.")
        print("\nUsage: python3 check_mitm_standings.py [path_to_log_file]")
        print("\nOr provide the path to your mitmproxy log file:")
        try:
            log_path = input("Path: ").strip()
            if log_path:
                log_files = [Path(log_path)]
        except:
            pass
    
    if not log_files:
        print("No log files specified. Exiting.")
        sys.exit(1)
    
    for log_file in log_files:
        if not log_file.exists():
            print(f"Log file not found: {log_file}")
            continue
        
        print(f"\n{'='*80}")
        print(f"Analyzing: {log_file}")
        print('='*80)
        
        standings_flows = find_standings_flows(log_file)
        
        if not standings_flows:
            print(f"No standings.jsp flows found in {log_file}")
            continue
        
        print(f"\nFound {len(standings_flows)} standings.jsp flows\n")
        
        for i, flow in enumerate(standings_flows, 1):
            print(f"\nFlow {i}/{len(standings_flows)}:")
            analyze_standings_flow(flow)
            print()


if __name__ == "__main__":
    main()

