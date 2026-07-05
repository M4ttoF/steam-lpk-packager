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
        # Create zip archive of the entire decrypted directory and include top‑level model files
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(decrypted_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    # Resolve relative path inside the zip file
                    rel_path = os.path.relpath(full_path, decrypted_path)
                    zf.write(full_path, rel_path)
            # Add model JSON and .moc files located alongside the decrypted folder
            model_json = os.path.join(CACHE_DIR, item_id, f"{item_id}.model.json")
            moc_file = os.path.join(CACHE_DIR, item_id, "model_0.moc")
            for extra_path in (model_json, moc_file):
                if os.path.isfile(extra_path):
                    zf.write(extra_path, os.path.basename(extra_path))
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

    import concurrent.futures
    success_count = 0
    updated_records = []

    # Helper function for worker threads
    def process_worker(item_info):
        item_id, steam_type = item_info
        # Print status in a thread-safe manner
        sys.stdout.write(f"Packaging {steam_type} item {item_id}...\n")
        sys.stdout.flush()
        
        success, result = package_single_item(item_id, steam_type)
        if success:
            sys.stdout.write(f"  [OK] Saved package to: {result}\n")
            sys.stdout.flush()
            
            # If clean flag is set, delete only the decrypted workshop cache directory
            if globals().get('CLEAN_AFTER_PACKAGING', False):
                import shutil
                decrypted_path = os.path.join(CACHE_DIR, item_id, "decrypted")
                if os.path.isdir(decrypted_path):
                    try:
                        shutil.rmtree(decrypted_path)
                        sys.stdout.write(f"  [CLEAN] Deleted decrypted folder: {decrypted_path}\n")
                        sys.stdout.flush()
                    except Exception as clean_err:
                        sys.stdout.write(f"  [WARNING] Failed to delete decrypted folder {decrypted_path}: {clean_err}\n")
                        sys.stdout.flush()
            return True, item_id
        else:
            sys.stdout.write(f"  [SKIPPED/FAILED] {result}\n")
            sys.stdout.flush()
            return False, item_id

    # Use ThreadPoolExecutor to run tasks in parallel (I/O bound)
    # Using 12 worker threads as standard sweet spot for CPU/Disk balance
    max_workers = 16
    print(f"Starting parallel packaging with {max_workers} worker threads...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_worker, target): target for target in targets}
        for future in concurrent.futures.as_completed(futures):
            success, item_id = future.result()
            if success:
                success_count += 1
                updated_records.append((item_id,))

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
    import argparse
    parser = argparse.ArgumentParser(description="LPK Studio Zip Packager")
    parser.add_argument("item_id", nargs="?", default=None, help="Specific item ID to package")
    parser.add_argument("--clean", action="store_true", help="Delete the decrypted cache directory after successful zipping")
    args = parser.parse_args()
    
    CLEAN_AFTER_PACKAGING = args.clean
    run_packaging(args.item_id)
