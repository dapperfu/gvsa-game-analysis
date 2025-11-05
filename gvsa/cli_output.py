#!/usr/bin/env python3
"""
Output formatting utilities for GVSA CLI.

This module provides functions to format CLI output in various formats:
table, JSON, and CSV.
"""
from typing import List, Dict, Any, Optional
import json
import csv
import sys
from io import StringIO


def format_table(data: List[Dict[str, Any]], headers: Optional[List[str]] = None) -> str:
    """
    Format data as a table using tabulate.
    
    Parameters
    ----------
    data : List[Dict[str, Any]]
        List of dictionaries to format
    headers : Optional[List[str]]
        Column headers. If None, uses dict keys from first item.
        
    Returns
    -------
    str
        Formatted table string
    """
    try:
        from tabulate import tabulate
    except ImportError:
        # Fallback to simple formatting if tabulate not available
        return format_table_simple(data, headers)
    
    if not data:
        return "No data available."
    
    # Extract headers if not provided
    if headers is None:
        headers = list(data[0].keys())
    
    # Build rows
    rows = []
    for item in data:
        row = [str(item.get(key, '')) for key in headers]
        rows.append(row)
    
    return tabulate(rows, headers=headers, tablefmt='grid')


def format_table_simple(data: List[Dict[str, Any]], headers: Optional[List[str]] = None) -> str:
    """
    Simple table formatting without tabulate dependency.
    
    Parameters
    ----------
    data : List[Dict[str, Any]]
        List of dictionaries to format
    headers : Optional[List[str]]
        Column headers. If None, uses dict keys from first item.
        
    Returns
    -------
    str
        Formatted table string
    """
    if not data:
        return "No data available."
    
    if headers is None:
        headers = list(data[0].keys())
    
    # Calculate column widths
    col_widths = [len(str(h)) for h in headers]
    for item in data:
        for i, key in enumerate(headers):
            val_len = len(str(item.get(key, '')))
            if val_len > col_widths[i]:
                col_widths[i] = val_len
    
    # Build table
    lines = []
    
    # Header row
    header_row = ' | '.join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
    lines.append(header_row)
    lines.append('-' * len(header_row))
    
    # Data rows
    for item in data:
        row = ' | '.join(str(item.get(key, '')).ljust(col_widths[i]) for i, key in enumerate(headers))
        lines.append(row)
    
    return '\n'.join(lines)


def format_json(data: List[Dict[str, Any]], indent: int = 2) -> str:
    """
    Format data as JSON.
    
    Parameters
    ----------
    data : List[Dict[str, Any]]
        List of dictionaries to format
    indent : int
        JSON indentation level (default: 2)
        
    Returns
    -------
    str
        Formatted JSON string
    """
    # Convert any non-serializable objects to strings
    def json_serializer(obj: Any) -> Any:
        """Convert non-serializable objects to strings."""
        if hasattr(obj, '__dict__'):
            return str(obj)
        return obj
    
    # Recursively convert objects
    def clean_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively clean dictionary for JSON serialization."""
        result = {}
        for k, v in d.items():
            if hasattr(v, '__dict__'):
                result[k] = str(v)
            elif isinstance(v, dict):
                result[k] = clean_dict(v)
            elif isinstance(v, list):
                result[k] = [clean_dict(item) if isinstance(item, dict) else 
                            (str(item) if hasattr(item, '__dict__') else item) 
                            for item in v]
            elif isinstance(v, set):
                result[k] = list(v)
            else:
                result[k] = json_serializer(v)
        return result
    
    cleaned_data = [clean_dict(item) for item in data]
    return json.dumps(cleaned_data, indent=indent, default=json_serializer)


def format_csv(data: List[Dict[str, Any]], headers: Optional[List[str]] = None) -> str:
    """
    Format data as CSV.
    
    Parameters
    ----------
    data : List[Dict[str, Any]]
        List of dictionaries to format
    headers : Optional[List[str]]
        Column headers. If None, uses dict keys from first item.
        
    Returns
    -------
    str
        Formatted CSV string
    """
    if not data:
        return ""
    
    if headers is None:
        headers = list(data[0].keys())
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    
    for item in data:
        # Only write values for specified headers
        row = {key: item.get(key, '') for key in headers}
        writer.writerow(row)
    
    return output.getvalue()


def print_output(data: List[Dict[str, Any]], format_type: str, 
                 headers: Optional[List[str]] = None) -> None:
    """
    Print data in the specified format.
    
    Parameters
    ----------
    data : List[Dict[str, Any]]
        List of dictionaries to format
    format_type : str
        Output format: 'table', 'json', or 'csv'
    headers : Optional[List[str]]
        Column headers for table/CSV format
    """
    if format_type == 'json':
        print(format_json(data))
    elif format_type == 'csv':
        print(format_csv(data, headers))
    else:  # table (default)
        print(format_table(data, headers))


def extract_age_group(division_name: str) -> Optional[str]:
    """
    Extract age group from division name.
    
    Parameters
    ----------
    division_name : str
        Division name to parse
        
    Returns
    -------
    Optional[str]
        Age group label (e.g., "U11", "U15/16") or None
    """
    import re
    
    # Match patterns like U10, U11, U15/16, U17/19
    range_pattern = r'U(\d{1,2})/(\d{1,2})'
    match = re.search(range_pattern, division_name)
    if match:
        return f"U{match.group(1)}/{match.group(2)}"
    
    single_pattern = r'U(\d{1,2})\b'
    match = re.search(single_pattern, division_name)
    if match:
        return f"U{match.group(1)}"
    
    return None

