#!/usr/bin/env python3
"""
Verify that all table data is being parsed correctly from HTML files.

This script checks:
- All tables are found and parsed
- Edge cases in table structure (missing cells, different formats)
- Whether all data columns are being extracted
"""
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Set
from collections import defaultdict
import json


def analyze_table_structure(html_content: str, file_path: str) -> Dict[str, Any]:
    """
    Analyze the structure of the standings table in detail.
    
    Parameters
    ----------
    html_content : str
        HTML content to analyze
    file_path : str
        Path to the file
        
    Returns
    -------
    Dict[str, Any]
        Detailed analysis of table structure
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    analysis: Dict[str, Any] = {
        'file': str(file_path),
        'table_found': False,
        'thead_columns': [],
        'tbody_rows': [],
        'row_variations': defaultdict(int),
        'parsing_issues': [],
        'sample_data': []
    }
    
    # Find the standings table
    standings_table = soup.find('table', id='row')
    if not standings_table:
        analysis['parsing_issues'].append("Table with id='row' not found")
        return analysis
    
    analysis['table_found'] = True
    
    # Analyze header
    thead = standings_table.find('thead')
    if thead:
        header_row = thead.find('tr')
        if header_row:
            headers = header_row.find_all(['th', 'td'])
            analysis['thead_columns'] = [h.get_text(strip=True) for h in headers]
    
    # Analyze body rows
    tbody = standings_table.find('tbody')
    if not tbody:
        analysis['parsing_issues'].append("Table tbody not found")
        return analysis
    
    rows = tbody.find_all('tr')
    for row_idx, row in enumerate(rows):
        cells = row.find_all('td')
        cell_count = len(cells)
        cell_texts = [cell.get_text(strip=True) for cell in cells]
        
        # Track row variations
        analysis['row_variations'][cell_count] += 1
        analysis['tbody_rows'].append({
            'row_index': row_idx,
            'cell_count': cell_count,
            'cells': cell_texts
        })
        
        # Check for parsing issues
        if cell_count < 9:
            analysis['parsing_issues'].append(
                f"Row {row_idx} has only {cell_count} cells (expected 9)"
            )
        
        # Sample first few rows
        if row_idx < 3:
            analysis['sample_data'].append(cell_texts)
    
    return analysis


def verify_all_tables() -> Dict[str, Any]:
    """
    Verify parsing for all cached HTML files.
    
    Returns
    -------
    Dict[str, Any]
        Summary of verification results
    """
    cache_dir = Path("html_cache")
    html_files = list(cache_dir.rglob("*.html"))
    
    print(f"Verifying table parsing for {len(html_files)} HTML files...")
    
    results = []
    issues_summary = defaultdict(int)
    row_variations = defaultdict(int)
    missing_tables = []
    parsing_errors = []
    
    for html_file in html_files:
        try:
            content = html_file.read_text(encoding='utf-8')
            analysis = analyze_table_structure(content, str(html_file))
            results.append(analysis)
            
            # Collect statistics
            if not analysis['table_found']:
                missing_tables.append(str(html_file))
            
            for issue in analysis['parsing_issues']:
                issues_summary[issue] += 1
            
            for cell_count, count in analysis['row_variations'].items():
                row_variations[cell_count] += count
        
        except Exception as e:
            parsing_errors.append({
                'file': str(html_file),
                'error': str(e)
            })
    
    # Summary
    summary = {
        'total_files': len(html_files),
        'files_analyzed': len(results),
        'missing_tables': len(missing_tables),
        'parsing_errors': len(parsing_errors),
        'issues_summary': dict(issues_summary),
        'row_variations': dict(sorted(row_variations.items())),
        'missing_table_files': missing_tables[:10],  # First 10
        'parsing_error_files': parsing_errors[:10],  # First 10
        'sample_analyses': results[:5]  # First 5 for inspection
    }
    
    return summary


def print_verification_summary(summary: Dict[str, Any]) -> None:
    """
    Print verification summary.
    
    Parameters
    ----------
    summary : Dict[str, Any]
        Verification summary
    """
    print("\n" + "=" * 80)
    print("TABLE PARSING VERIFICATION SUMMARY")
    print("=" * 80)
    
    print(f"\nTotal files: {summary['total_files']}")
    print(f"Files analyzed: {summary['files_analyzed']}")
    print(f"Missing tables: {summary['missing_tables']}")
    print(f"Parsing errors: {summary['parsing_errors']}")
    
    if summary['row_variations']:
        print(f"\nRow cell count variations:")
        for cell_count, count in summary['row_variations'].items():
            print(f"  {cell_count} cells: {count} rows")
    
    if summary['issues_summary']:
        print(f"\n⚠️  Parsing issues found:")
        for issue, count in sorted(summary['issues_summary'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {count:4d}x: {issue}")
    else:
        print(f"\n✅ No parsing issues found!")
    
    if summary['missing_tables']:
        print(f"\n⚠️  Files missing table with id='row':")
        for file in summary['missing_table_files']:
            print(f"  - {file}")
    
    if summary['parsing_errors']:
        print(f"\n⚠️  Files with parsing errors:")
        for error in summary['parsing_error_files']:
            print(f"  - {error['file']}: {error['error']}")
    
    # Show sample analyses
    print(f"\n📊 Sample table structures:")
    for analysis in summary['sample_analyses']:
        print(f"\n  File: {Path(analysis['file']).name}")
        if analysis['thead_columns']:
            print(f"    Headers ({len(analysis['thead_columns'])}): {analysis['thead_columns']}")
        if analysis['sample_data']:
            print(f"    Sample row 0: {analysis['sample_data'][0]}")


def main() -> None:
    """Main entry point."""
    cache_dir = Path("html_cache")
    
    if not cache_dir.exists():
        print(f"Cache directory {cache_dir} does not exist.")
        return
    
    summary = verify_all_tables()
    print_verification_summary(summary)
    
    # Save detailed results
    output_file = Path("table_verification.json")
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✅ Detailed verification saved to: {output_file}")


if __name__ == "__main__":
    main()

