import json
import requests
import base64
import platform
import os
import pandas as pd
from io import StringIO

def _get_machine_key():
    key_base = f"{platform.node()}{os.getenv('USERNAME', 'default')}"
    return base64.b64encode(key_base.encode())[:32]

def decrypt_token(encrypted_token):
    if not encrypted_token: return ""
    try:
        key = _get_machine_key()
        encrypted = base64.b64decode(encrypted_token.encode())
        decrypted = bytearray()
        for i, byte in enumerate(encrypted):
            decrypted.append(byte ^ key[i % len(key)])
        return bytes(decrypted).decode()
    except: return encrypted_token

def test_csv_links():
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        token = decrypt_token(config.get("ona_api_token_encrypted")) or config.get("ona_api_token")
        if not token: return

        headers = {"Authorization": f"Token {token}"}
        fid = config.get("ona_form_id")
        
        # ONA supports .csv extension in data endpoint
        print(f"Requesting CSV for Form: {fid}")
        url = f"https://api.ona.io/api/v1/data/{fid}.csv?limit=1"
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 200:
            csv_data = resp.text
            df = pd.read_csv(StringIO(csv_data))
            
            print("\nColumns in CSV:")
            print(df.columns.tolist())
            
            # Check for photo columns and their content
            photo_cols = [c for c in df.columns if any(x in c.lower() for x in ['photo', 'image', 'foto', 'img'])]
            print("\nPhoto Columns Values in CSV:")
            for pc in photo_cols:
                val = df.iloc[0][pc]
                print(f"  {pc}: {val}")
                if str(val).startswith("http"):
                    print("  [Link Detected!]")
        else:
            print(f"Error: {resp.status_code}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_csv_links()
