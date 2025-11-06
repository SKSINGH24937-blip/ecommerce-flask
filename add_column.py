# add_column.py
import sqlite3

con = sqlite3.connect('ecommerce.db')
cur = con.cursor()
try:
    cur.execute("ALTER TABLE product ADD COLUMN description TEXT;")
    print("✅ Column 'description' added successfully!")
except Exception as e:
    print("⚠️ Error:", e)
con.commit()
con.close()
