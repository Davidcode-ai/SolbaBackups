import httpx
import asyncio

async def run():
    url = 'https://graph.facebook.com/v25.0/1020834011123459/messages'
    token = 'EAADkIif4We8BRbgVCqJJZAyvCsVa5j5gG6kyZBNFuzcgXhZAVg7bNgfN5ZB1xfBHUtL1jMe3ZAm6TclGwhLvLfB5DXeDzHwZBjpz325Y8wsV3LNCZCLItfMFrJAaHoJZBFY3GPsd3g5u0ZAbE9hKMjJWfAiCF9ZBemfpnQStObtx31DI4w1yF7treQTZC4ZATlsyvyYuTIZA5Xgh0wXBCIXlf9tZC2ZBypVYiSteY4BXJE5GMcQM1ZCfS8hoSZBtbY3H8OMCAn5gCbUxmuWy00EvcL4pwbWnl'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': '34622430735',
        'type': 'template',
        'template': {
            'name': 'hello_world',
            'language': {'code': 'en_US'}
        }
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=payload)
        print(r.status_code)
        print(r.text)

if __name__ == '__main__':
    asyncio.run(run())
