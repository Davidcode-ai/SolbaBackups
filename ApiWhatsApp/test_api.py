import asyncio
import httpx

async def test():
    async with httpx.AsyncClient() as client:
        # Test health
        r = await client.get("http://localhost:8000/health")
        print("HEALTH:", r.status_code, r.text)

        # Test POST notification
        r2 = await client.post(
            "http://localhost:8000/api/v1/notifications",
            json={
                "to": "34622430735",
                "template_name": "solba_backup_status",
                "language_code": "es_ES",
                "template_vars": ["Base de Datos Principal", "Incremental", "✅ ÉXITO"]
            }
        )
        print("POST /api/v1/notifications:", r2.status_code, r2.text)

if __name__ == "__main__":
    asyncio.run(test())
