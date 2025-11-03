#!/usr/bin/env python3
"""
Analyze mitmproxy log file to extract teams and results data.

This script uses mitmproxy's API to read flow files and extract
relevant information about teams and match results.
"""
from typing import Any
from mitmproxy import http, io, flow
from mitmproxy.exceptions import FlowReadException
import sys
from pathlib import Path


def analyze_flow(flow_obj: http.HTTPFlow) -> None:
    """
    Analyze a single HTTP flow to extract relevant data.
    
    Parameters
    ----------
    flow_obj : http.HTTPFlow
        The HTTP flow object to analyze
    """
    request = flow_obj.request
    response = flow_obj.response
    
    # Filter for relevant URLs (teams, results, schedules, etc.)
    url = request.pretty_url.lower()
    relevant_keywords = ['team', 'result', 'schedule', 'game', 'match', 'score', 'standings', 'league']
    
    # Check if URL might contain relevant data
    is_relevant = any(keyword in url for keyword in relevant_keywords)
    
    # Also check HTML pages that might contain embedded data
    if response and response.headers.get('content-type', '').startswith('text/html'):
        is_relevant = True
    
    if is_relevant:
        print(f"\n{'='*80}")
        print(f"URL: {request.pretty_url}")
        print(f"Method: {request.method}")
        print(f"Status: {response.status_code if response else 'No response'}")
        
        if response:
            content_type = response.headers.get('content-type', '')
            print(f"Content-Type: {content_type}")
            
            # Try to get response content
            try:
                if hasattr(response, 'content') and response.content:
                    content = response.content
                    if isinstance(content, bytes):
                        # Try to decode as text
                        try:
                            text_content = content.decode('utf-8', errors='ignore')
                            # Show preview of content
                            preview = text_content[:500] if len(text_content) > 500 else text_content
                            print(f"Content Preview (first 500 chars):\n{preview}")
                            
                            # Look for data patterns
                            if 'team' in text_content.lower() or 'result' in text_content.lower():
                                print("\n*** POTENTIALLY RELEVANT DATA FOUND ***")
                        except:
                            print(f"Content: {len(content)} bytes (binary)")
            except Exception as e:
                print(f"Error reading content: {e}")


def main() -> None:
    """
    Main function to read and analyze mitmproxy log file.
    """
    log_file = Path("mitm_logs/mitm_20251103_160133.log")
    
    if not log_file.exists():
        print(f"Error: Log file not found: {log_file}")
        sys.exit(1)
    
    print(f"Analyzing mitmproxy log: {log_file}")
    print(f"{'='*80}\n")
    
    flows_read = 0
    flows_analyzed = 0
    
    try:
        with open(log_file, "rb") as f:
            reader = io.FlowReader(f)
            try:
                for flow_obj in reader.stream():
                    flows_read += 1
                    if isinstance(flow_obj, http.HTTPFlow):
                        analyze_flow(flow_obj)
                        flows_analyzed += 1
            except FlowReadException as e:
                print(f"Error reading flow: {e}")
    except Exception as e:
        print(f"Error opening log file: {e}")
        sys.exit(1)
    
    print(f"\n{'='*80}")
    print(f"Analysis complete:")
    print(f"  Total flows read: {flows_read}")
    print(f"  HTTP flows analyzed: {flows_analyzed}")


if __name__ == "__main__":
    main()

