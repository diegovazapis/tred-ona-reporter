import json
import requests
import sys

def inspect_columns():
    print("Starting inspection...", flush=True)
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        token = config.get("ona_api_token")
        if not token:
            print("No token found.", flush=True)
            return

        headers = {"Authorization": f"Token {token}"}
        
        # 1. Get Forms
        print("Fetching forms list...", flush=True)
        resp = requests.get("https://api.ona.io/api/v1/forms", headers=headers, timeout=10)
        forms = resp.json()
        print(f"Found {len(forms)} forms.", flush=True)

        for form in forms:
            fid = form['formid']
            title = form['title']
            print(f"\nFORM: {title} ({fid})", flush=True)
            
            # 2. Get Data (limit 1)
            url = f"https://api.ona.io/api/v1/data/{fid}?limit=1"
            try:
                r_data = requests.get(url, headers=headers, timeout=15)
                data = r_data.json()
                if data and len(data) > 0:
                    rec = data[0]
                    keys = list(rec.keys())
                    
                    # Filter for likely candidates
                    clients = [k for k in keys if "client" in k.lower() or "cliente" in k.lower()]
                    sites = [k for k in keys if "site" in k.lower() or "sitio" in k.lower() or "nombre" in k.lower()]
                    
                    print(f"  > CLIENT Keys found: {clients}", flush=True)
                    print(f"  > SITE Keys found: {sites}", flush=True)
                    # print(f"  > All Keys: {keys}", flush=True)
                else:
                    print("  > Empty data.", flush=True)
            except Exception as e:
                print(f"  > Error fetching data: {e}", flush=True)

    except Exception as e:
        print(f"Fatal Error: {e}", flush=True)

if __name__ == "__main__":
    inspect_columns()
