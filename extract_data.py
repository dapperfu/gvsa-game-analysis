#!/usr/bin/env python3
"""
Extract teams and results data from mitmproxy log file.

This script uses mitmproxy's API to read flow files and extract
HTML/JSON responses containing team and match result data.
"""
from typing import Any, Dict, List, Optional
from mitmproxy import http, io
from mitmproxy.exceptions import FlowReadException
from pathlib import Path
import json
import re


def extract_standings_data(html_content: str) -> Optional[Dict[str, Any]]:
    """
    Extract standings data from HTML content.
    
    Parameters
    ----------
    html_content : str
        The HTML content from standings.jsp
        
    Returns
    -------
    Optional[Dict[str, Any]]
        Extracted standings data or None if parsing fails
    """
    # This is a placeholder - will need to parse actual HTML structure
    # Look for table structures, team names, wins, losses, etc.
    return None


def extract_seasons_data(html_content: str) -> Optional[List[str]]:
    """
    Extract available seasons from HTML content.
    
    Parameters
    ----------
    html_content : str
        The HTML content from seasons.jsp
        
    Returns
    -------
    Optional[List[str]]
        List of season names or None if parsing fails
    """
    # This is a placeholder - will need to parse actual HTML structure
    return None


def save_response(flow_obj: http.HTTPFlow, output_dir: Path) -> None:
    """
    Save response content to file for analysis.
    
    Parameters
    ----------
    flow_obj : http.HTTPFlow
        The HTTP flow object containing the response
    output_dir : Path
        Directory to save extracted files
    """
    request = flow_obj.request
    response = flow_obj.response
    
    if not response:
        return
    
    # Focus on JSP files and HTML pages
    url_path = request.pretty_url.split('?')[0]  # Remove query params
    if not (url_path.endswith('.jsp') or url_path.endswith('.htm') or 
            url_path.endswith('.html')):
        return
    
    # Create filename from URL
    filename = url_path.split('/')[-1]
    if not filename:
        filename = 'index.html'
    
    # Sanitize filename
    filename = re.sub(r'[^\w\.\-]', '_', filename)
    
    output_path = output_dir / filename
    
    try:
        if hasattr(response, 'content') and response.content:
            content = response.content
            if isinstance(content, bytes):
                # Try to decode as text
                try:
                    text_content = content.decode('utf-8', errors='ignore')
                    output_path.write_text(text_content, encoding='utf-8')
                    print(f"Saved: {output_path} ({len(text_content)} chars)")
                except Exception as e:
                    print(f"Error saving {filename}: {e}")
    except Exception as e:
        print(f"Error processing {filename}: {e}")


def analyze_flow(flow_obj: http.HTTPFlow, output_dir: Path) -> None:
    """
    Analyze a single HTTP flow and extract relevant data.
    
    Parameters
    ----------
    flow_obj : http.HTTPFlow
        The HTTP flow object to analyze
    output_dir : Path
        Directory to save extracted files
    """
    request = flow_obj.request
    response = flow_obj.response
    
    url = request.pretty_url.lower()
    
    # Focus on JSP files which likely contain the data
    if url.endswith('.jsp') and response and response.status_code == 200:
        print(f"\nFound JSP: {request.pretty_url}")
        save_response(flow_obj, output_dir)


def main() -> None:
    """
    Main function to extract data from mitmproxy log file.
    """
    log_file = Path("mitm_logs/mitm_20251103_160133.log")
    output_dir = Path("extracted_responses")
    
    output_dir.mkdir(exist_ok=True)
    
    if not log_file.exists():
        print(f"Error: Log file not found: {log_file}")
        return
    
    print(f"Extracting data from: {log_file}")
    print(f"Output directory: {output_dir}\n")
    
    flows_read = 0
    flows_analyzed = 0
    
    try:
        with open(log_file, "rb") as f:
            reader = io.FlowReader(f)
            try:
                for flow_obj in reader.stream():
                    flows_read += 1
                    if isinstance(flow_obj, http.HTTPFlow):
                        analyze_flow(flow_obj, output_dir)
                        flows_analyzed += 1
            except FlowReadException as e:
                print(f"Error reading flow: {e}")
    except Exception as e:
        print(f"Error opening log file: {e}")
        return
    
    print(f"\n{'='*80}")
    print(f"Extraction complete:")
    print(f"  Total flows read: {flows_read}")
    print(f"  HTTP flows analyzed: {flows_analyzed}")
    print(f"  Files saved to: {output_dir}")


if __name__ == "__main__":
    main()

