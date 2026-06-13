import json
import requests
import base64
import platform
import os

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

def test_media_urls():
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        token = decrypt_token(config.get("ona_api_token_encrypted")) or config.get("ona_api_token")
        if not token: return

        headers = {"Authorization": f"Token {token}"}
        fid = config.get("ona_form_id")
        
        print(f"Testing with include_media_urls=true for Form: {fid}")
        url = f"https://api.ona.io/api/v1/data/{fid}?limit=1&include_media_urls=true"
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 200:
            data = resp.json()
            if data:
                record = data[0]
                # Look for columns that might contain URLs
                url_cols = [k for k in record.keys() if 'url' in k.lower() or 'link' in k.lower() or 'http' in str(record[k]).lower()]
                print(f"Columns with potential URLs: {url_cols}")
                for c in url_cols:
                    print(f"  {c}: {record[c]}")
                
                # Check if original photo columns now have URLs
                photo_cols = [k for k in record.keys() if any(x in k.lower() for x in ['photo', 'image', 'foto', 'img'])]
                print(f"Photo columns current values:")
                for pc in photo_cols:
                    print(f"  {pc}: {record[pc]}")
            else:
                print("No data")
        else:
            print(f"Error: {resp.status_code}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_media_urls()
