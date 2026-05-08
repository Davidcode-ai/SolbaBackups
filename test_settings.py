import requests

url = "http://localhost:8765/api/v1/settings"
payload = {
    "language": "es",
    "admin_email": "test@test.com",
    "log_retention_days": 15
}

r = requests.put(url, json=payload)
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")

r2 = requests.get(url)
print(f"GET Response: {r2.text}")
