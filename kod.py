import sqlite3
import pandas as pd

conn = sqlite3.connect("marketler.db")
df = pd.read_sql_query("SELECT * FROM urunler LIMIT 5", conn)
conn.close()

print(df.columns)
print(df.head())
