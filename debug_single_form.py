import json
import base64
import os
import requests
import platform

def _get_machine_key():
    """Generate a simple key from machine-specific data"""
    key_base = f"{platform.node()}{os.getenv('USERNAME', 'default')}"
    return base64.b64encode(key_base.encode())[:32]

def decrypt_token(encrypted_token):
    """Decrypt token"""
    if not encrypted_token:
        return ""
    try:
        key = _get_machine_key()
        encrypted = base64.b64decode(encrypted_token.encode())
        decrypted = bytearray()
        for i, byte in enumerate(encrypted):
            decrypted.append(byte ^ key[i % len(key)])
        return bytes(decrypted).decode()
    except Exception as e:
        print(f"Decryption error: {e}")
        return encrypted_token

def main():
    if not os.path.exists("config.json"):
        print("config.json not found")
        return

    with open("config.json", 'r') as f:
        config = json.load(f)
    
    token = config.get("ona_api_token")
    if config.get("ona_api_token_encrypted"):
        token = decrypt_token(config.get("ona_api_token_encrypted"))
    
    headers = {"Authorization": f"Token {token}"}
    
    fid = 859541 # Reporte de avance
    print(f"Inspecting Form ID: {fid}")
    
    url = f"https://api.ona.io/api/v1/data/{fid}?limit=1&sort={{\"-submission_time\":1}}"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if data:
            record = data[0]
            print("\n--- COLUMNS ---")
            for k in sorted(record.keys()):
                print(f"{k}")
        else:
            print("No data found.")
    else:
        print(f"Error: {resp.status_code}")

if __name__ == "__main__":
    main()
