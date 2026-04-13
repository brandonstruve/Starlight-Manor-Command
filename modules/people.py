import os
import math
import sqlite3
import requests
from flask import Blueprint, render_template, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv
from pathlib import Path

# Initialize the Blueprint
bp = Blueprint('people', __name__, url_prefix='/people')

# --- Configuration & Paths ---
BASE_DIR = Path(__file__).parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"
DB_PATH = BASE_DIR / "data" / "starlight_manor.db"
DATA_DIR = BASE_DIR / "data"

def get_immich_config():
    load_dotenv(dotenv_path=ENV_PATH)
    return {
        "url": os.getenv("IMMICH_API_URL", "").rstrip('/'),
        "key": os.getenv("IMMICH_API_KEY", "")
    }

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn

@bp.route('/')
def index():
    return render_template('people.html')

@bp.route('/api/people_list')
def people_list():
    if not DB_PATH.exists():
        return jsonify({"error": "Database not found"}), 404
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Build Category Map
    cursor.execute("SELECT DISTINCT category, sub_category FROM People WHERE category != ''")
    rows = cursor.fetchall()
    categories = {}
    for row in rows:
        cat = row['category']
        sub = row['sub_category']
        if cat not in categories:
            categories[cat] = set()
        if sub:
            categories[cat].add(sub)
    cat_dict = {k: sorted(list(v)) for k, v in categories.items()}
    
    # 2. Filtering & Search
    query = "SELECT * FROM People"
    conditions = []
    params = []
    
    cat_filter = request.args.get('category')
    sub_filter = request.args.get('subcategory')
    search_query = request.args.get('search', '').strip()
    
    if cat_filter:
        conditions.append("category = ?")
        params.append(cat_filter)
    if sub_filter:
        conditions.append("sub_category = ?")
        params.append(sub_filter)
    if search_query:
        conditions.append("(first_name LIKE ? OR middle_name LIKE ? OR last_name LIKE ? OR nickname LIKE ?)")
        search_param = f"%{search_query}%"
        params.extend([search_param, search_param, search_param, search_param])
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY asset_count DESC"
    cursor.execute(query, params)
    all_results = cursor.fetchall()
    
    total_records = len(all_results)
    page = int(request.args.get('page', 1))
    per_page = 12
    total_pages = math.ceil(total_records / per_page) if total_records > 0 else 1
    
    start = (page - 1) * per_page
    page_rows = all_results[start:start+per_page]
    
    records = []
    for row in page_rows:
        d = dict(row)
        records.append({
            "Name": f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
            "I_Immich_ID": d.get('immich_id'),
            "ImmichAssetCount": d.get('asset_count', 0),
            "D_Category": d.get('category'),
            "D_Sub Category": d.get('sub_category'),
            "ProfilePhotoPath": d.get('profile_photo_path')
        })
        
    conn.close()
    return jsonify({
        'records': records, 'total': total_records, 'page': page,
        'total_pages': total_pages, 'categories': cat_dict
    })

@bp.route('/api/person/<immich_id>')
def get_person(immich_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Base Fetch
    cursor.execute("SELECT * FROM People WHERE immich_id = ?", (immich_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return jsonify({"error": "Person not found"}), 404
        
    d = dict(row)
    internal_id = d.get('id')
    
    # 2. Schema-Accurate Household Fetch
    household_name = "Standalone"
    try:
        if d.get('household_id'):
            cursor.execute("SELECT household_name FROM Households WHERE id = ?", (d.get('household_id'),))
            hh_row = cursor.fetchone()
            if hh_row: household_name = hh_row['household_name']
    except Exception as e:
        print(f"Household Join Error: {e}")
        
    # 3. Schema-Accurate Relationship Fetch
    spouse_name = None
    anniversary_date = None
    try:
        cursor.execute("""
            SELECT r.anniversary_date, 
                   CASE WHEN r.person_a_id = ? THEN p2.first_name || ' ' || p2.last_name 
                        ELSE p1.first_name || ' ' || p1.last_name END as spouse_name
            FROM Relationships r
            LEFT JOIN People p1 ON r.person_a_id = p1.id
            LEFT JOIN People p2 ON r.person_b_id = p2.id
            WHERE (r.person_a_id = ? OR r.person_b_id = ?) AND r.relationship_type = 'Married'
            LIMIT 1
        """, (internal_id, internal_id, internal_id))
        rel_row = cursor.fetchone()
        if rel_row:
            spouse_name = rel_row['spouse_name']
            anniversary_date = rel_row['anniversary_date']
    except Exception as e:
        print(f"Relationship Join Error: {e}")

    conn.close()
    
    full_addr = f"{d.get('street_address', '')}, {d.get('city', '')}, {d.get('state', '')} {d.get('zip_code', '')}".strip(", ")
    
    person_data = {
        "Name": f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
        "first_name": d.get('first_name'),
        "last_name": d.get('last_name'),
        "I_Immich_ID": d.get('immich_id'),
        "ImmichAssetCount": d.get('asset_count', 0),
        "D_Category": d.get('category'),
        "D_Sub Category": d.get('sub_category'),
        "Household_Name": household_name,
        "Household_ID": d.get('household_id'),
        "Spouse_Name": spouse_name,
        "Anniversary_Date": anniversary_date,
        "ProfilePhotoPath": d.get('profile_photo_path'),
        "I_Birthdate": d.get('birthdate'),
        "I_DeathDate": d.get('deathdate'),
        "Email": d.get('email'),
        "Phone": d.get('phone'),
        "Address": full_addr if full_addr != ",  " else "",
        "street_address": d.get('street_address'),
        "city": d.get('city'),
        "state": d.get('state'),
        "zip_code": d.get('zip_code'),
        "D_digiKam_ID": d.get('digikam_id'),
        "G_Google_ID": d.get('google_id')
    }
    
    # 4. Fetch Random Image from Immich
    config = get_immich_config()
    random_asset_id = None
    try:
        headers = {"x-api-key": config['key'], "Accept": "application/json"}
        res = requests.post(f"{config['url']}/api/search/random", json={"personIds": [immich_id], "size": 1}, headers=headers, timeout=5)
        if res.status_code == 200:
            assets = res.json()
            if assets: random_asset_id = assets[0].get('id')
    except: pass
        
    person_data['random_asset_id'] = random_asset_id
    return jsonify(person_data)

@bp.route('/api/update_person', methods=['POST'])
def update_person():
    data = request.json
    immich_id = data.get('immich_id')
    if not immich_id:
        return jsonify({"error": "Missing ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE People SET 
                birthdate = ?, deathdate = ?, email = ?, phone = ?, 
                street_address = ?, city = ?, state = ?, zip_code = ?,
                category = ?, sub_category = ?,
                google_id = ?, digikam_id = ?
            WHERE immich_id = ?
        """, (
            data.get('birthdate'), data.get('deathdate'), data.get('email'),
            data.get('phone'), data.get('street_address'), data.get('city'),
            data.get('state'), data.get('zip_code'), data.get('category'),
            data.get('sub_category'), data.get('google_id'), data.get('digikam_id'),
            immich_id
        ))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# --- CRM Dashboard Endpoints ---

@bp.route('/api/households', methods=['GET'])
def get_households():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Aggregated Join to support sketch requirements
    cursor.execute("""
        SELECT h.id, h.household_name, 
               GROUP_CONCAT(p.first_name, ', ') as residents,
               MAX(p.street_address) as street_address,
               MAX(p.city) as city,
               MAX(p.state) as state
        FROM Households h
        LEFT JOIN People p ON h.id = p.household_id
        GROUP BY h.id, h.household_name
        ORDER BY h.household_name
    """)
    households = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(households)

@bp.route('/api/relationships_list', methods=['GET'])
def get_relationships():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.anniversary_date, 
               p1.first_name || ' ' || p1.last_name as person_a_name,
               p2.first_name || ' ' || p2.last_name as person_b_name
        FROM Relationships r
        JOIN People p1 ON r.person_a_id = p1.id
        JOIN People p2 ON r.person_b_id = p2.id
        WHERE r.relationship_type = 'Married'
        ORDER BY r.anniversary_date ASC
    """)
    relationships = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(relationships)

@bp.route('/api/households/assign', methods=['POST'])
def assign_household():
    data = request.json
    person_id = data.get('immich_id')
    household_id = data.get('household_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE People SET household_id = ? WHERE immich_id = ?", (household_id, person_id))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@bp.route('/api/households/create_and_batch', methods=['POST'])
def create_household_batch():
    data = request.json
    name = data.get('name')
    person_ids = data.get('person_ids', [])
    
    if not name or not person_ids:
        return jsonify({"error": "Missing name or individuals"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Households (household_name) VALUES (?)", (name,))
        new_household_id = cursor.lastrowid
        
        for pid in person_ids:
            cursor.execute("UPDATE People SET household_id = ? WHERE immich_id = ?", (new_household_id, pid))
            
        conn.commit()
        return jsonify({"success": True, "household_id": new_household_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@bp.route('/api/relationships/link', methods=['POST'])
def link_relationship():
    data = request.json
    person1_immich = data.get('person1_id')
    person2_immich = data.get('person2_id')
    anniversary = data.get('anniversary_date')
    
    if not person1_immich or not person2_immich:
        return jsonify({"error": "Requires two people to link"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Step 1: Translate Immich IDs to internal integer IDs
        cursor.execute("SELECT id FROM People WHERE immich_id = ?", (person1_immich,))
        p1 = cursor.fetchone()
        cursor.execute("SELECT id FROM People WHERE immich_id = ?", (person2_immich,))
        p2 = cursor.fetchone()
        
        if not p1 or not p2:
            return jsonify({"error": "Could not locate internal IDs for relationship mapping."}), 404
            
        p1_id, p2_id = p1['id'], p2['id']

        # Step 2: Insert or Update the schema-accurate relationship
        cursor.execute("""
            SELECT id FROM Relationships 
            WHERE (person_a_id = ? AND person_b_id = ?) OR (person_a_id = ? AND person_b_id = ?)
        """, (p1_id, p2_id, p2_id, p1_id))
        
        if cursor.fetchone():
            cursor.execute("""
                UPDATE Relationships SET relationship_type = 'Married', anniversary_date = ?
                WHERE (person_a_id = ? AND person_b_id = ?) OR (person_a_id = ? AND person_b_id = ?)
            """, (anniversary, p1_id, p2_id, p2_id, p1_id))
        else:
            cursor.execute("""
                INSERT INTO Relationships (person_a_id, person_b_id, relationship_type, anniversary_date)
                VALUES (?, ?, 'Married', ?)
            """, (p1_id, p2_id, anniversary))
            
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# --- Media Proxies ---

@bp.route('/api/image/<asset_id>')
def proxy_immich_image(asset_id):
    config = get_immich_config()
    try:
        headers = {"x-api-key": config['key']}
        url = f"{config['url']}/api/assets/{asset_id}/thumbnail?size=preview"
        res = requests.get(url, headers=headers, stream=True)
        return Response(stream_with_context(res.iter_content(chunk_size=1024)), content_type=res.headers.get('Content-Type', 'image/jpeg'))
    except: return "Error", 500

@bp.route('/api/profile_photo')
def proxy_local_photo():
    photo_path = request.args.get('path', '')
    full_path = DATA_DIR / photo_path
    if full_path.exists():
        with open(full_path, 'rb') as f: return Response(f.read(), mimetype='image/jpeg')
    return "Not found", 404