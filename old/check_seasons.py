#!/usr/bin/env python3
"""Check seasons in database to understand duplicates."""
from models import db, Season
from db_pony import GVSA_Database
from pony.orm import db_session, select
from collections import Counter
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "gvsa_data2.db"
db_instance = GVSA_Database(db_path)

with db_session:
    seasons = list(select(s for s in Season))
    print(f"Total seasons in database: {len(seasons)}")
    print(f"Unique season names: {len(set(s.season_name for s in seasons))}")
    print(f"Unique (year, season_type) combinations: {len(set((s.year, s._season_type) for s in seasons))}")
    
    print("\nSeason counts by year:")
    year_counts = Counter(s.year for s in seasons)
    for year, count in sorted(year_counts.items()):
        print(f"  {year}: {count} seasons")
    
    print("\nDuplicate (year, type) combinations:")
    combo_counts = Counter((s.year, s._season_type) for s in seasons)
    duplicates = {combo: count for combo, count in combo_counts.items() if count > 1}
    if duplicates:
        for (year, stype), count in sorted(duplicates.items()):
            print(f"  {year} {stype}: {count} entries")
            matching = [s for s in seasons if s.year == year and s._season_type == stype]
            for s in matching:
                print(f"    - ID {s.id}: '{s.season_name}' (scraped: {s.scraped_at})")
    else:
        print("  No duplicates found")
    
    print("\nFirst 20 seasons (sorted by year, type):")
    for s in sorted(seasons, key=lambda x: (x.year, x._season_type))[:20]:
        print(f"  {s.year} {s.season_type.value}: '{s.season_name}' (ID: {s.id})")

