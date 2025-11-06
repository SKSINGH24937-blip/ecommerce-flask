# init_db.py
import sqlite3

con = sqlite3.connect("ecommerce.db")
cur = con.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS product (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    image TEXT,
    description TEXT
);
""")

print("✅ Product table created successfully with description column.")
con.commit()
con.close()
