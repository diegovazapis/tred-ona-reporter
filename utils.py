import requests
from PIL import Image
from io import BytesIO

def download_and_resize_image(url, target_width=400, auth_token=None):
    """
    Downloads an image from a URL and resizes it maintaining aspect ratio.
    Returns: BytesIO object or None if failed.
    """
    try:
        # Step 1: Request with Auth to get the redirect URL
        headers = {}
        if auth_token:
            headers['Authorization'] = f"Token {auth_token}"
            
        # ONA usually returns a 302 Redirect to S3. 
        # Requests follows redirects automatically, BUT it forwards headers by default which breaks S3 signature.
        # We must disable auto-redirect and handle it manually.
        
        # Determine if it's an ONA URL that needs auth
        if "ona.io" in url:
            resp1 = requests.get(url, headers=headers, allow_redirects=False, timeout=10)
            if resp1.status_code in [301, 302, 303, 307] and 'Location' in resp1.headers:
                # Redirect to S3 - DO NOT send Auth header there
                final_url = resp1.headers['Location']
                response = requests.get(final_url, timeout=15)
            else:
                # No redirect, maybe direct content
                response = resp1
        else:
            # External or already public URL
            response = requests.get(url, timeout=10)
            
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content))
        
        # Calculate new height to maintain aspect ratio
        width_percent = (target_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(width_percent)))
        
        img_resized = img.resize((target_width, h_size), Image.Resampling.LANCZOS)
        
        img_byte_arr = BytesIO()
        img_resized.save(img_byte_arr, format=img.format or 'JPEG') # Fallback format
        img_byte_arr.seek(0)
        
        return img_byte_arr
    except Exception as e:
        print(f"Error processing image {url}: {e}")
        return None

def get_address_from_coords(lat, lon):
    """
    Reverse geocoding using Nominatim (OSM) as a free fallback.
    Alternatively, could use Mapbox if token is provided.
    """
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
        headers = {"User-Agent": "TRED-DocGenerator/1.0"}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("display_name", f"{lat}, {lon}")
    except Exception as e:
        print(f"Reverse geocode error: {e}")
    return f"{lat}, {lon}"

def get_static_map_image(lat, lon, zoom=15, width=600, height=400):
    """
    Fetches a static map image from OpenStreetMap (StaticMap service).
    Returns BytesIO.
    """
    try:
        # Using a public static map generator or similar
        # For professional usage, Mapbox Static Images API is recommended
        # Placeholder logic:
        url = f"https://static-maps.yandex.ru/1.x/?ll={lon},{lat}&z={zoom}&size={width},{height}&l=map&pt={lon},{lat},pm2rdm"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return BytesIO(resp.content)
    except Exception as e:
        print(f"Static map error: {e}")
    return None
