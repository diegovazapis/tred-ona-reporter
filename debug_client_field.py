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
    
    if not token:
        print("No token retrieved.")
        return

    print(f"Token retrieved (len={len(token)})")
    
    headers = {"Authorization": f"Token {token}"}
    
    # 1. Get List of Forms
    print("Fetching list of forms...")
    resp = requests.get("https://api.ona.io/api/v1/forms", headers=headers)
    if resp.status_code != 200:
        print(f"Error fetching forms: {resp.status_code}")
        return
        
    forms = resp.json()
    print(f"Found {len(forms)} forms.")
    
    for form in forms:
        fid = form['formid']
        title = form['title']
        print(f"\n==========================================")
        print(f"FORM: {title} (ID: {fid})")
        print(f"==========================================")
        
        # 2. Fetch data (limit 1) to check columns
        url = f"https://api.ona.io/api/v1/data/{fid}?limit=1&sort={{\"-submission_time\":1}}"
        try:
            d_resp = requests.get(url, headers=headers)
            if d_resp.status_code == 200:
                data = d_resp.json()
                if data:
                    record = data[0]
                    # Search for client/cliente
                    found_client = False
                    for k in record.keys():
                        if 'client' in k.lower() or 'cust' in k.lower():
                            print(f"[MATCH] {k}: {record[k]}")
                            found_client = True
                    
                    if not found_client:
                        print("No 'client'/'cliente' field found in top keys.")
                        # Check typical suspects
                        if 'cliente' in record: print(f"[EXACT MATCH] cliente: {record['cliente']}")
                        
                else:
                    print("No data in this form.")
            else:
                print(f"Error fetching data: {d_resp.status_code}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
