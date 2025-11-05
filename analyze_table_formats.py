#!/usr/bin/env python3
"""
Analyze all table formats in cached HTML files to ensure complete parsing.

This script scans all cached HTML files and identifies:
- All table elements (by id, class, structure)
- Table headers and data structures
- Any tables that might not be currently parsed
"""
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Dict, List, Set, Any
from collections import defaultdict
import json


def analyze_tables_in_html(html_content: str, file_path: str) -> Dict[str, Any]:
    """
    Analyze all tables in an HTML file.
    
    Parameters
    ----------
    html_content : str
        The HTML content to analyze
    file_path : str
        Path to the HTML file (for reporting)
        
    Returns
    -------
    Dict[str, Any]
        Analysis results with table structures found
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    analysis: Dict[str, Any] = {
        'file': str(file_path),
        'tables': [],
        'all_table_ids': [],
        'all_table_classes': [],
        'table_count': 0
    }
    
    # Find ALL tables
    all_tables = soup.find_all('table')
    analysis['table_count'] = len(all_tables)
    
    for idx, table in enumerate(all_tables):
        table_info: Dict[str, Any] = {
            'index': idx,
            'id': table.get('id', ''),
            'class': table.get('class', []),
            'has_thead': table.find('thead') is not None,
            'has_tbody': table.find('tbody') is not None,
            'has_tfoot': table.find('tfoot') is not None,
            'row_count': 0,
            'column_count': 0,
            'header_rows': [],
            'data_rows': [],
            'sample_data': []
        }
        
        # Get table ID
        if table_info['id']:
            analysis['all_table_ids'].append(table_info['id'])
        
        # Get table classes
        if table_info['class']:
            analysis['all_table_classes'].extend(table_info['class'])
        
        # Analyze structure
        thead = table.find('thead')
        tbody = table.find('tbody')
        tfoot = table.find('tfoot')
        
        # Analyze header rows
        if thead:
            header_rows = thead.find_all('tr')
            for row in header_rows:
                cells = row.find_all(['th', 'td'])
                headers = [cell.get_text(strip=True) for cell in cells]
                table_info['header_rows'].append(headers)
                if headers:
                    table_info['column_count'] = max(table_info['column_count'], len(headers))
        else:
            # Check if first row is a header row
            first_row = table.find('tr')
            if first_row:
                first_cells = first_row.find_all(['th', 'td'])
                if first_cells:
                    # Check if all cells are th or contain header-like content
                    all_th = all(cell.name == 'th' for cell in first_cells)
                    if all_th:
                        headers = [cell.get_text(strip=True) for cell in first_cells]
                        table_info['header_rows'].append(headers)
                        table_info['column_count'] = len(headers)
        
        # Analyze data rows
        rows_to_analyze = []
        if tbody:
            rows_to_analyze = tbody.find_all('tr')
        elif thead:
            # If no tbody, get all tr after thead
            rows_to_analyze = table.find_all('tr')[len(header_rows):]
        else:
            rows_to_analyze = table.find_all('tr')[len(table_info['header_rows']):]
        
        table_info['row_count'] = len(rows_to_analyze)
        
        # Sample first few data rows
        for row in rows_to_analyze[:3]:
            cells = row.find_all(['td', 'th'])
            cell_data = [cell.get_text(strip=True) for cell in cells]
            if cell_data:
                table_info['data_rows'].append(cell_data)
                table_info['column_count'] = max(table_info['column_count'], len(cell_data))
        
        # Get sample data structure
        if table_info['data_rows']:
            table_info['sample_data'] = table_info['data_rows'][0]
        
        analysis['tables'].append(table_info)
    
    return analysis


def analyze_all_cached_html(cache_dir: Path = Path("html_cache")) -> Dict[str, Any]:
    """
    Analyze all cached HTML files for table structures.
    
    Parameters
    ----------
    cache_dir : Path
        Directory containing cached HTML files
        
    Returns
    -------
    Dict[str, Any]
        Summary of all table formats found
    """
    html_files = list(cache_dir.rglob("*.html"))
    
    print(f"Analyzing {len(html_files)} HTML files...")
    
    all_table_ids: Set[str] = set()
    all_table_classes: Set[str] = set()
    table_structures: Dict[str, int] = defaultdict(int)
    files_by_table_count: Dict[int, int] = defaultdict(int)
    missing_tables: List[Dict[str, Any]] = []
    
    results = []
    
    for html_file in html_files:
        try:
            content = html_file.read_text(encoding='utf-8')
            analysis = analyze_tables_in_html(content, str(html_file))
            results.append(analysis)
            
            # Collect statistics
            files_by_table_count[analysis['table_count']] += 1
            
            for table_info in analysis['tables']:
                if table_info['id']:
                    all_table_ids.add(table_info['id'])
                
                if table_info['class']:
                    all_table_classes.update(table_info['class'])
                
                # Create structure signature
                structure = f"id={table_info['id']},thead={table_info['has_thead']},tbody={table_info['has_tbody']},rows={table_info['row_count']},cols={table_info['column_count']}"
                table_structures[structure] += 1
            
            # Check if expected tables are missing
            has_row_table = any(t['id'] == 'row' for t in analysis['tables'])
            has_row2_table = any(t['id'] == 'row2' for t in analysis['tables'])
            
            if not has_row_table or not has_row2_table:
                missing_tables.append({
                    'file': str(html_file),
                    'has_row': has_row_table,
                    'has_row2': has_row2_table,
                    'table_count': analysis['table_count'],
                    'table_ids': [t['id'] for t in analysis['tables'] if t['id']]
                })
        
        except Exception as e:
            print(f"Error analyzing {html_file}: {e}")
    
    # Create summary
    summary = {
        'total_files': len(html_files),
        'files_analyzed': len(results),
        'unique_table_ids': sorted(list(all_table_ids)),
        'unique_table_classes': sorted(list(all_table_classes)),
        'table_structures': dict(sorted(table_structures.items(), key=lambda x: x[1], reverse=True)),
        'files_by_table_count': dict(sorted(files_by_table_count.items())),
        'missing_expected_tables': missing_tables,
        'detailed_results': results
    }
    
    return summary


def print_summary(summary: Dict[str, Any]) -> None:
    """
    Print analysis summary in readable format.
    
    Parameters
    ----------
    summary : Dict[str, Any]
        Analysis summary from analyze_all_cached_html
    """
    print("\n" + "=" * 80)
    print("TABLE FORMAT ANALYSIS SUMMARY")
    print("=" * 80)
    
    print(f"\nTotal files analyzed: {summary['files_analyzed']}")
    
    print(f"\nFiles by table count:")
    for count, file_count in sorted(summary['files_by_table_count'].items()):
        print(f"  {count} table(s): {file_count} files")
    
    print(f"\nUnique table IDs found:")
    for table_id in summary['unique_table_ids']:
        print(f"  - '{table_id}'")
    
    print(f"\nUnique table classes found:")
    for table_class in summary['unique_table_classes']:
        print(f"  - '{table_class}'")
    
    print(f"\nTop table structures (by frequency):")
    for structure, count in list(summary['table_structures'].items())[:20]:
        print(f"  {count:4d}x: {structure}")
    
    if summary['missing_expected_tables']:
        print(f"\n⚠️  Files missing expected tables (id='row' or id='row2'): {len(summary['missing_expected_tables'])}")
        for missing in summary['missing_expected_tables'][:10]:
            print(f"  - {missing['file']}")
            print(f"    Tables found: {missing['table_ids']}")
            print(f"    Has 'row': {missing['has_row']}, Has 'row2': {missing['has_row2']}")
    
    # Check for tables that aren't being parsed
    print(f"\n🔍 Tables that might not be parsed:")
    parsed_ids = {'row', 'row2'}
    unparsed_ids = set(summary['unique_table_ids']) - parsed_ids
    if unparsed_ids:
        print(f"  Found {len(unparsed_ids)} table ID(s) that aren't currently parsed:")
        for table_id in unparsed_ids:
            count = sum(1 for r in summary['detailed_results'] 
                       for t in r['tables'] if t['id'] == table_id)
            print(f"    - '{table_id}': found in {count} files")
    else:
        print("  All table IDs are being parsed!")
    
    # Find tables with data that might be missed
    print(f"\n📊 Tables with data that might contain useful information:")
    for result in summary['detailed_results']:
        for table_info in result['tables']:
            if table_info['row_count'] > 0 and table_info['id'] not in parsed_ids:
                print(f"  - File: {result['file']}")
                print(f"    Table ID: '{table_info['id']}'")
                print(f"    Rows: {table_info['row_count']}, Cols: {table_info['column_count']}")
                if table_info['header_rows']:
                    print(f"    Headers: {table_info['header_rows'][0]}")
                if table_info['sample_data']:
                    print(f"    Sample row: {table_info['sample_data']}")
                print()


def main() -> None:
    """Main entry point."""
    cache_dir = Path("html_cache")
    
    if not cache_dir.exists():
        print(f"Cache directory {cache_dir} does not exist.")
        return
    
    summary = analyze_all_cached_html(cache_dir)
    
    print_summary(summary)
    
    # Save detailed results to JSON
    output_file = Path("table_analysis.json")
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✅ Detailed analysis saved to: {output_file}")


if __name__ == "__main__":
    main()

