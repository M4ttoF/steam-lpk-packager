import os
import sys
import sqlite3
import zipfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'catalog.sqlite')

# Helper to read basic key=values from .env if present
def load_env_config():
    env_vars = {}
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env_vars[k.strip()] = v.strip()
    return env_vars

env_cfg = load_env_config()
STORAGE_DIR = env_cfg.get("STORAGE_DIR") or env_cfg.get("STORAGE_ROOT") or os.path.join(BASE_DIR, "storage")
CACHE_DIR = os.path.join(STORAGE_DIR, "workshop_cache")

# Setup packages directories under storage directory
LIVE2D_DIR = os.path.join(STORAGE_DIR, "live2d_packages")
SPINE_DIR = os.path.join(STORAGE_DIR, "spine_packages")

def package_single_item(item_id, steam_type):
    """
    Packages a decrypted directory into a ZIP archive without discrimination.
    """
    decrypted_path = os.path.join(CACHE_DIR, item_id, "decrypted")
    if not os.path.isdir(decrypted_path):
        return False, "Decrypted cache directory missing."

    target_dir = LIVE2D_DIR if steam_type == "Live2D" else SPINE_DIR
    os.makedirs(target_dir, exist_ok=True)
    
    zip_filename = f"live2d_{item_id}.zip" if steam_type == "Live2D" else f"spine_{item_id}.zip"
    zip_path = os.path.join(target_dir, zip_filename)

    try:
        # Create zip archive of the entire decrypted directory
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(decrypted_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    # Resolve relative path inside the zip file
                    rel_path = os.path.relpath(full_path, decrypted_path)
                    zf.write(full_path, rel_path)
        return True, zip_path
    except Exception as e:
        return False, f"Failed to compile zip: {e}"

def run_packaging(specific_id=None):
    print("=" * 60)
    print("LPK STUDIO — ZIP COMPRESSION PACKAGER")
    print(f"STORAGE DIR: {STORAGE_DIR}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if specific_id:
        c.execute("SELECT id, steam_type FROM models WHERE id = ?", (specific_id,))
        targets = c.fetchall()
    else:
        # Find all compatible, checked models
        c.execute("""
            SELECT id, steam_type 
            FROM models 
            WHERE compatible = 1 
              AND thumbnail_checked = 1 
              AND steam_type IN ('Live2D', 'Spine')
        """)
        all_models = c.fetchall()
        
        # Pre-scan cache directory for active folders
        active_cache_folders = set(os.listdir(CACHE_DIR)) if os.path.isdir(CACHE_DIR) else set()
        
        # Filter for targets where the decrypted cache folder exists AND the zip file is missing on disk
        targets = []
        for item_id, steam_type in all_models:
            if item_id in active_cache_folders:
                decrypted_path = os.path.join(CACHE_DIR, item_id, "decrypted")
                if os.path.isdir(decrypted_path):
                    target_dir = LIVE2D_DIR if steam_type == "Live2D" else SPINE_DIR
                    zip_filename = f"live2d_{item_id}.zip" if steam_type == "Live2D" else f"spine_{item_id}.zip"
                    zip_path = os.path.join(target_dir, zip_filename)
                    
                    # Package if the ZIP file doesn't exist on disk
                    if not os.path.exists(zip_path):
                        targets.append((item_id, steam_type))
                
    conn.close()

    if not targets:
        print("No models found that require packaging.")
        return

    print(f"Found {len(targets)} models to package.")

    success_count = 0
    updated_records = []

    for idx, (item_id, steam_type) in enumerate(targets, 1):
        print(f"[{idx}/{len(targets)}] Packaging {steam_type} item {item_id}...")
        success, result = package_single_item(item_id, steam_type)
        if success:
            print(f"  [OK] Saved package to: {result}")
            success_count += 1
            updated_records.append((item_id,))
        else:
            print(f"  [SKIPPED/FAILED] {result}")

    # Mark as packaged in SQLite database
    if updated_records:
        print("\nUpdating packaged status in catalog database...")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.executemany("UPDATE models SET packaged = 1 WHERE id = ?", updated_records)
        conn.commit()
        print(f"Successfully updated {c.rowcount} records in database.")
        conn.close()

    print("\n" + "=" * 60)
    print("PACKAGING SUMMARY")
    print(f"  Total Processed : {len(targets)}")
    print(f"  Zipped & Saved  : {success_count}")
    print("=" * 60)

if __name__ == '__main__':
    # Accept specific ID command-line argument if passed
    import sys
    arg_id = sys.argv[1] if len(sys.argv) > 1 else None
    run_packaging(arg_id)
