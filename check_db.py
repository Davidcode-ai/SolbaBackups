import psycopg2
import json

conn_str = 'postgresql://postgres.yjkhdvzbyrjsauytzvnh:Ef5YTpTlsd3yft9Q@aws-0-eu-west-1.pooler.supabase.com:6543/postgres'
try:
    with psycopg2.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status, retry_count, error_log FROM whatsapp_notifications WHERE id IN ('cd8f63f3-e32f-4d65-963e-a6bbd47a0a96', '759ca280-41f5-4756-b2c1-e359d4905351');")
            rows = cur.fetchall()
            for r in rows:
                print(r)
except Exception as e:
    print('DB Error:', e)
