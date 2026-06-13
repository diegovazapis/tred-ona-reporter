import sqlite3
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class LocalDB:
    def __init__(self, db_path="data/tred_local.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Sites Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    partner TEXT,
                    latitude REAL,
                    longitude REAL,
                    address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Submissions Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ona_id INTEGER UNIQUE,
                    uuid TEXT,
                    site_id INTEGER,
                    raw_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (site_id) REFERENCES sites (id)
                )
            ''')
            conn.commit()

    def process_submission(self, json_data):
        """Processes a new submission, links it to a site, and saves it."""
        ona_id = json_data.get('_id')
        uuid = json_data.get('_uuid')
        
        if not ona_id:
            return None
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if submission already exists
            cursor.execute("SELECT id, site_id FROM submissions WHERE ona_id = ?", (ona_id,))
            row = cursor.fetchone()
            if row:
                # Update json just in case
                cursor.execute("UPDATE submissions SET raw_json = ? WHERE ona_id = ?", (json.dumps(json_data), ona_id))
                conn.commit()
                return row[1] # Return site_id
                
            # Find or create site
            site_id = self._ensure_site_exists(cursor, json_data)
            
            # Insert submission
            cursor.execute('''
                INSERT INTO submissions (ona_id, uuid, site_id, raw_json)
                VALUES (?, ?, ?, ?)
            ''', (ona_id, uuid, site_id, json.dumps(json_data)))
            
            conn.commit()
            return site_id

    def _ensure_site_exists(self, cursor, json_data):
        partner = json_data.get('cliente', '') # Usually mapped or present in JSON
        lat, lon = None, None
        
        if json_data.get('_geolocation'):
            try:
                lat, lon = json_data['_geolocation']
            except:
                pass
                
        # 1. Search by Coordinates (Delta 50m)
        if lat is not None and lon is not None:
            delta = 50 / 111000.0
            cursor.execute('''
                SELECT id FROM sites 
                WHERE latitude >= ? AND latitude <= ? 
                AND longitude >= ? AND longitude <= ?
            ''', (lat - delta, lat + delta, lon - delta, lon + delta))
            row = cursor.fetchone()
            if row:
                return row[0]
                
        # 2. Search by Name
        site_name = (
            json_data.get('group_sitio/nombre_sitio') or 
            json_data.get('nombre_sitio') or
            json_data.get('site_name') or
            f"Sitio {json_data.get('_id')}"
        )
        
        if partner:
            cursor.execute('''
                SELECT id FROM sites WHERE name = ? AND partner = ?
            ''', (site_name, partner))
            row = cursor.fetchone()
            if row:
                return row[0]
                
        # 3. Create new site
        address = json_data.get('group_sitio/direccion') or json_data.get('direccion', '')
        cursor.execute('''
            INSERT INTO sites (name, partner, latitude, longitude, address)
            VALUES (?, ?, ?, ?, ?)
        ''', (site_name, partner, lat, lon, address))
        
        return cursor.lastrowid
        
    def get_sites(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sites ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    def get_submissions_by_site(self, site_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM submissions WHERE site_id = ? ORDER BY created_at DESC", (site_id,))
            return [dict(row) for row in cursor.fetchall()]
