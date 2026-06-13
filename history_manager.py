import json
import os
import time
import uuid
import glob
from datetime import datetime

class HistoryManager:
    def __init__(self, base_dir="data/historial"):
        self.base_dir = base_dir
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def save_generation_record(self, project_id, report_type, site_name, ona_record_id, data_snapshot, user="admin", record_id=None):
        """
        Saves a snapshot of the generation parameters.
        If record_id is passed, it OVERWRITES the existing record (Update Mode).
        """
        timestamp = int(time.time())
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Determine ID and Filename
        if record_id:
            # Update Mode
            gen_id = record_id
            # We need to find the filename associated with this ID
            existing_file = None
            files = glob.glob(os.path.join(self.base_dir, "*.json"))
            for f in files:
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        d = json.load(file)
                        if d.get('id') == gen_id:
                            existing_file = f
                            break
                except: pass
            
            if existing_file:
                filepath = existing_file
            else:
                # Fallback if file missing
                safe_site = "".join([c for c in site_name if c.isalnum() or c in (' ', '-', '_')]).strip()
                safe_proj = "".join([c for c in project_id if c.isalnum() or c in (' ', '-', '_')]).strip() or "General"
                filename = f"{safe_proj}_{report_type}_{safe_site}_{timestamp}.json"
                filepath = os.path.join(self.base_dir, filename)
        else:
            # Create Mode
            gen_id = str(uuid.uuid4())
            safe_site = "".join([c for c in site_name if c.isalnum() or c in (' ', '-', '_')]).strip()
            safe_proj = "".join([c for c in project_id if c.isalnum() or c in (' ', '-', '_')]).strip() or "General"
            filename = f"{safe_proj}_{report_type}_{safe_site}_{timestamp}.json"
            filepath = os.path.join(self.base_dir, filename)
        
        record = {
            "id": gen_id,
            "project_id": project_id,
            "report_type": report_type,
            "site_name": site_name,
            "ona_record_id": ona_record_id,
            "created_at": timestamp,
            "created_at_fmt": date_str,
            "updated_at": timestamp,
            "user": user,
            "data": data_snapshot
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=4, ensure_ascii=False)
            return True, filepath
        except Exception as e:
            print(f"Error saving history: {e}")
            return False, str(e)

    def list_history(self):
        """
        Returns a list of all historical records, sorted by date DESC.
        """
        files = glob.glob(os.path.join(self.base_dir, "*.json"))
        records = []
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    records.append(json.load(file))
            except: pass
        
        # Sort by timestamp desc
        records.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        return records

    def get_record(self, gen_id):
        """
        Finds a record by ID (inefficient but simple for files)
        """
        # In a real DB this would be a query. Here we scan.
        all_recs = self.list_history()
        for r in all_recs:
            if r.get('id') == gen_id:
                return r
        return None
