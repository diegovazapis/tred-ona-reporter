import json
import yaml

from app import get_csv_media_links

with open("../config.yaml", "r") as f:
    config = yaml.safe_load(f)
    api_token = config.get("ona_api_token")

links = get_csv_media_links(api_token, 832863, 114095454)
print(list(links.values())[:3])
