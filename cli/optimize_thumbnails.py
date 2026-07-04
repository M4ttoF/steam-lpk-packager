import os
import sqlite3
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THUMBNAILS_DIR = os.path.join(PROJECT_ROOT, "public", "thumbnails")
DB_PATH = os.path.join(PROJECT_ROOT, "db", "catalog.sqlite")

def optimize():
    print("=" * 60)
    print("LPK STUDIO — THUMBNAIL OPTIMIZER (PNG -> JPG 512x512)")
    print(f"THUMBNAILS DIR: {THUMBNAILS_DIR}")
    print("=" * 60)

    if not os.path.isdir(THUMBNAILS_DIR):
        print("[Error] public/thumbnails/ directory not found!")
        return

    # Find all PNG files directly inside public/thumbnails
    png_files = [f for f in os.listdir(THUMBNAILS_DIR) if f.endswith(".png")]
    print(f"Found {len(png_files)} PNG files to optimize.")

    optimized_count = 0
    skipped_count = 0
    MAX_SIZE = 512

    for idx, fname in enumerate(png_files, 1):
        png_path = os.path.join(THUMBNAILS_DIR, fname)
        jpg_name = os.path.splitext(fname)[0] + ".jpg"
        jpg_path = os.path.join(THUMBNAILS_DIR, jpg_name)

        try:
            # Open and convert to RGB (removes alpha channel transparency cleanly for JPEG)
            img = Image.open(png_path)
            
            # Resize if dimensions exceed 512px
            if img.width > MAX_SIZE or img.height > MAX_SIZE:
                img.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)

            # Convert to RGB mode
            rgb_img = img.convert("RGB")
            
            # Save as JPEG with 75% quality compression
            rgb_img.save(jpg_path, "JPEG", quality=75)
            
            # Close images
            img.close()
            rgb_img.close()

            # Remove original PNG
            os.remove(png_path)
            optimized_count += 1
        except Exception as e:
            print(f"  Failed to optimize {fname}: {e}")

        if idx % 1000 == 0:
            print(f"  Processed {idx}/{len(png_files)} images...")

    # Update database references to point to .jpg instead of .png
    print("\nUpdating SQLite database references...")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Select all models where thumbnail_local is set to .png
        c.execute("SELECT id, thumbnail_local FROM models WHERE thumbnail_local LIKE '%.png'")
        rows = c.fetchall()
        
        updates = []
        for row in rows:
            model_id, local_path = row
            new_path = local_path.replace(".png", ".jpg")
            updates.append((new_path, model_id))
            
        if updates:
            c.executemany("UPDATE models SET thumbnail_local = ? WHERE id = ?", updates)
            conn.commit()
            print(f"Successfully updated {len(updates)} database paths in SQLite.")
        else:
            print("No database paths needed updating.")
            
        conn.close()
    except Exception as db_err:
        print(f"[Error] Database update failed: {db_err}")

    print("\n" + "=" * 60)
    print("OPTIMIZATION COMPLETE")
    print(f"  Images Converted & Resized : {optimized_count}")
    print("=" * 60)

if __name__ == '__main__':
    optimize()
