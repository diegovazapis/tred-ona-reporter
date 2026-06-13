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
    headers = {"Authorization": f"Token {token}"}
    
    # URL provided by user
    user_url = "https://api.ona.io/api/v1/files/47374838?filename=tred/attachments/852559_a8aHSTM7VdcrmEgygtz6GS/image-12_13_22.jpg"
    
    print(f"Testing User-Provided URL: {user_url}")
    try:
        r = requests.get(user_url, headers=headers, timeout=10)
        print(f"  Status: {r.status_code}")
        print(f"  Content-Type: {r.headers.get('Content-Type')}")
        if r.status_code == 200:
            print(f"  SUCCESS! Received {len(r.content)} bytes")
        else:
            print(f"  FAILED. Response: {r.text[:500]}")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    test_ona_images()
