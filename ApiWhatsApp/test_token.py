import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv(override=True)

async def test_meta():
    token = os.getenv("META_ACCESS_TOKEN")
    phone_id = os.getenv("META_PHONE_NUMBER_ID")
    target_phone = "34622430735"

    url = f"https://graph.facebook.com/v25.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp", 
        "to": target_phone, 
        "type": "template", 
        "template": { 
            "name": "hello_world", 
            "language": { "code": "en_US" } 
        } 
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        print("Status:", resp.status_code)
        print("Body:", resp.text)

if __name__ == "__main__":
    asyncio.run(test_meta())
