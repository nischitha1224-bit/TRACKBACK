import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote

query = quote("lemon water diabetes cure")

url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

try:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20
    )

    print("HTTP STATUS:", response.status_code)

    root = ET.fromstring(response.content)

    items = root.findall(".//item")

    print("NEWS RESULTS FOUND:", len(items))

    for item in items[:5]:
        title = item.findtext("title")
        link = item.findtext("link")

        print("\nTITLE:", title)
        print("URL:", link)

except Exception as error:
    print("SEARCH ERROR:", repr(error))