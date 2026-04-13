import sqlite3
import csv
from datetime import datetime, timedelta
from pathlib import Path

# --- Configuration ---
DB_PATH = r"C:\Starlight Manor Command\data\starlight_manor.db"
OUTPUT_PATH = r"\\homeassistant.local\config\data\ha_events.csv"

def get_ordinal(n):
    """Converts an integer into its ordinal string representation (e.g., 2 -> 2nd)."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'th', 'th'][n % 10]}"

def get_next_occurrence(original_date_str):
    """Calculates the next occurrence of a date within a 365-day rolling window."""
    try:
        orig_date = datetime.strptime(original_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None, None
        
    today = datetime.today().date()
    
    try:
        next_date = orig_date.replace(year=today.year)
    except ValueError:
        # Handle Leap Years gracefully
        next_date = orig_date.replace(year=today.year, month=3, day=1)
        
    if next_date < today:
        try:
            next_date = orig_date.replace(year=today.year + 1)
        except ValueError:
            next_date = orig_date.replace(year=today.year + 1, month=3, day=1)
            
    if next_date <= today + timedelta(days=30):
        years_diff = next_date.year - orig_date.year
        return next_date, years_diff
        
    return None, None

def main():
    events = []
    
    # Ensure the target directory exists before writing
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # --- Pass 1: Birthdays ---
    cursor.execute("SELECT first_name, last_name, birthdate, deathdate FROM People WHERE birthdate IS NOT NULL AND birthdate != ''")
    for row in cursor.fetchall():
        next_date, age = get_next_occurrence(row['birthdate'])
        if next_date and age is not None:
            prefix = "Remembering " if row['deathdate'] else ""
            name = f"{row['first_name']} {row['last_name']}".strip()
            events.append((next_date, f"{prefix}{name}'s {get_ordinal(age)} Birthday"))
            
    # --- Pass 2: Anniversaries ---
    cursor.execute("""
        SELECT r.anniversary_date, 
               p1.first_name as p1_first, p1.last_name as p1_last, p1.deathdate as p1_death,
               p2.first_name as p2_first, p2.last_name as p2_last, p2.deathdate as p2_death
        FROM Relationships r
        JOIN People p1 ON r.person_a_id = p1.id
        JOIN People p2 ON r.person_b_id = p2.id
        WHERE r.relationship_type = 'Married' AND r.anniversary_date IS NOT NULL AND r.anniversary_date != ''
    """)
    for row in cursor.fetchall():
        next_date, years = get_next_occurrence(row['anniversary_date'])
        if next_date and years is not None:
            prefix = "Remembering " if (row['p1_death'] or row['p2_death']) else ""
            name1 = f"{row['p1_first']} {row['p1_last']}".strip()
            name2 = f"{row['p2_first']} {row['p2_last']}".strip()
            events.append((next_date, f"{prefix}{name1} + {name2}'s {get_ordinal(years)} Wedding Anniversary"))
            
    conn.close()
    
    # Sort everything chronologically before writing
    events.sort(key=lambda x: x[0])
    
    # --- Output to CSV ---
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for event_date, event_text in events:
            # Enforce the requested "M/D/YYYY" formatting without leading zeros
            formatted_date = f"{event_date.month}/{event_date.day}/{event_date.year}"
            writer.writerow([formatted_date, event_text])
            
    print(f"Successfully exported {len(events)} events for the next 365 days to {OUTPUT_PATH}")

if __name__ == '__main__':
    main()