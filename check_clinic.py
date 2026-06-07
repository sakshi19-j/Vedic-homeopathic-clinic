import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name = 'clinics' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(row)
conn.close()
