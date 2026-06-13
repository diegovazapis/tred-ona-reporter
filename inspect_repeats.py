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

def inspect_repeats():
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        token = decrypt_token(config.get("ona_api_token_encrypted")) or config.get("ona_api_token")
        if not token: return

        headers = {"Authorization": f"Token {token}"}
        fid = config.get("ona_form_id")
        
        url = f"https://api.ona.io/api/v1/data/{fid}?limit=1"
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 200:
            data = resp.json()
            if data:
                record = data[0]
                for k, v in record.items():
                    if isinstance(v, list) and not k.startswith('_'):
                        print(f"\nPotential Repeat Group: {k} (Length: {len(v)})")
                        if len(v) > 0:
                            print("First Item Keys:", list(v[0].keys()))
                            # Look for photos in the first item
                            photos = [pk for pk in v[0].keys() if any(x in pk.lower() for x in ['photo', 'image', 'foto', 'img'])]
                            print(f"Photos in repeat item: {photos}")
                    elif isinstance(v, dict):
                         print(f"\nGroup: {k}")
                         print("Keys:", list(v.keys()))
            else:
                print("No data")
        else:
            print(f"Error: {resp.status_code}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_repeats()
