import sqlite3
import csv
import os

# --- CONFIGURATION ---
DIGIKAM_DB_PATH = r"C:\Users\brand\Pictures\digikam4.db" 
OUTPUT_CSV = "digikam_people_categorized.csv"
# ---------------------

def extract_people_categorized():
    if not os.path.exists(DIGIKAM_DB_PATH):
        print(f"❌ Error: Could not find database at {DIGIKAM_DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DIGIKAM_DB_PATH)
        cursor = conn.cursor()

        # This query builds the full hierarchy path for every person
        query = """
        WITH RECURSIVE Hierarchy(id, name, parent_id, path) AS (
            -- Start with the root tags (where pid is 0 or -1)
            SELECT id, name, pid, name
            FROM Tags
            WHERE pid <= 0
            
            UNION ALL
            
            -- Join children with their parents to build the path string
            SELECT T.id, T.name, T.pid, H.path || '/' || T.name
            FROM Tags T
            JOIN Hierarchy H ON T.pid = H.id
        )
        -- We only want tags that are under 'People' or marked as face tags
        SELECT 
            H.id AS digiKam_ID, 
            H.name AS Name, 
            P.name AS Parent_Category,
            H.path AS Full_Path
        FROM Hierarchy H
        LEFT JOIN Tags P ON H.parent_id = P.id
        WHERE H.path LIKE 'People/%' 
           OR H.id IN (SELECT tagid FROM TagProperties WHERE property = 'face')
        ORDER BY H.path;
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        with open(OUTPUT_CSV, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['digiKam_ID', 'Name', 'Category', 'Full_Path'])
            writer.writerows(rows)

        print(f"✅ Success! Extracted {len(rows)} categorized people to {OUTPUT_CSV}")
    
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    extract_people_categorized()