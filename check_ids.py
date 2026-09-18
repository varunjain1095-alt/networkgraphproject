import sqlite3
conn = sqlite3.connect('data/dev_verify.db')
result = conn.execute("SELECT user_id FROM users WHERE user_id LIKE '%347' OR user_id LIKE '%158' LIMIT 10").fetchall()
print(result)