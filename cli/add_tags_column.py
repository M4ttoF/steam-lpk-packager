import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'catalog.sqlite')

def migrate():
    print("=" * 60)
    print("LPK STUDIO — DATABASE MIGRATION (ADD TAGS COLUMN)")
    print(f"DATABASE: {DB_PATH}")
    print("=" * 60)

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if tags column already exists
        c.execute("PRAGMA table_info(models)")
        columns = [col[1] for col in c.fetchall()]
        
        if "tags" in columns:
            print("[INFO] 'tags' column already exists in models table. No action needed.")
        else:
            c.execute("ALTER TABLE models ADD COLUMN tags TEXT")
            conn.commit()
            print("[SUCCESS] Successfully added 'tags' column to models table.")
            
        conn.close()
    except Exception as e:
        print(f"[Error] Migration failed: {e}")

if __name__ == '__main__':
    migrate()
