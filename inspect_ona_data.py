import json
import requests
from api_handler import OnaAPIHandler

def inspect_columns():
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        token = config.get("ona_api_token")
        if not token:
            print("No token found in config.json")
            return

        handler = OnaAPIHandler(token)
        forms = handler.get_user_forms()
        print(f"Found {len(forms)} forms.")

        for form in forms:
            fid = form['formid']
            title = form['title']
            print(f"\n--- FORM: {title} (ID: {fid}) ---")
            
            # Fetch 1 record
            headers = {"Authorization": f"Token {token}"}
            url = f"https://api.ona.io/api/v1/data/{fid}?limit=1"
            resp = requests.get(url, headers=headers)
            
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list) and len(data) > 0:
                    record = data[0]
                    # Print keys that look like 'client' or 'site'
                    print("  [Potential CLIENT columns]:")
                    for k in record.keys():
                        if 'client' in k.lower() or 'cliente' in k.lower():
                            print(f"    - {k} : {record[k]}")
                            
                    print("  [Potential SITE columns]:")
                    for k in record.keys():
                        if 'site' in k.lower() or 'sitio' in k.lower() or 'nombre' in k.lower():
                            print(f"    - {k} : {record[k]}")
                    
                    print("  (ALL COLUMNS):")
                    print(list(record.keys()))
                else:
                    print("  (Form is empty)")
            else:
                print(f"  Error fetching data: {resp.status_code}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_columns()
