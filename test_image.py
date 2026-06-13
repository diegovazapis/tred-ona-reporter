import requests

api_token = "Token e325fbb8582f3a616212ea66e1d5208f754704b2"
headers = {'Authorization': api_token}

filename = "1000045660-17_17_19.jpg"
urls = [
    f"https://api.ona.io/api/v1/files/42078876"
]

for url in urls:
    print(f"\nTrying {url}")
    print("Status:", resp1.status_code)
    
    if resp1.status_code in [301, 302, 303, 307] and 'Location' in resp1.headers:
        final_url = resp1.headers['Location']
        print("Redirecting to:", final_url[:100] + "...")
        response = requests.get(final_url, timeout=15)
        print("Final Status:", response.status_code)
        if response.status_code != 200:
            print(response.text[:200])
    else:
        print("Response text:", resp1.text[:200])
