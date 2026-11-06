import os
import requests

key = os.getenv("GEMINI_API_KEY")

url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

response = requests.post(
    url,
    headers={
        "x-goog-api-key": key,
        "Content-Type": "application/json"
    },
    json={
        "contents": [{
            "parts": [{"text": "Reply only: TRACKBACK connected"}]
        }]
    },
    timeout=30
)

print("STATUS:", response.status_code)
print("RESPONSE:", response.text[:1000])