import requests
import json
import os
import base64
import platform

def _get_machine_key():
    key_base = f"{platform.node()}{os.getenv('USERNAME', 'default')}"
    return base64.b64encode(key_base.encode())[:32]

def decrypt_token(encrypted_token):
    if not encrypted_token:
        return ""
    try:
        key = _get_machine_key()
        encrypted = base64.b64decode(encrypted_token.encode())
        decrypted = bytearray()
        for i, byte in enumerate(encrypted):
            decrypted.append(byte ^ key[i % len(key)])
        return bytes(decrypted).decode()
    except:
        return encrypted_token

def test_ona_images():
    config_path = "config.json"
    with open(config_path, "r") as f: config = json.load(f)
    token = decrypt_token(config['ona_api_token_encrypted']) if 'ona_api_token_encrypted' in config else config.get('ona_api_token')
    form_id = config.get("ona_form_id")
    headers = {"Authorization": f"Token {token}"}
    
    data_url = f"https://api.ona.io/api/v1/data/{form_id}?limit=1"
    try:
        print(f"Fetching sample record...")
        resp = requests.get(data_url, headers=headers)
        record = resp.json()[0]
        
        # 1. Print full record to see the ACTUAL structure of atttachments
        print("\nFULL RECORD JSON:")
        print(json.dumps(record, indent=2))
        
        if '_attachments' in record:
            print("\nATTACHMENTS DETAIL:")
            for a in record['_attachments']:
                print(f" - JSON: {a}")
                url = a.get('download_url') or a.get('url')
                if url:
                    if not url.startswith('http'):
                        url = f"https://api.ona.io{url}"
                    print(f"   Trying URL: {url}")
                    r = requests.get(url, headers=headers)
                    print(f"   Status: {r.status_code}, Content-Type: {r.headers.get('Content-Type')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ona_images()
