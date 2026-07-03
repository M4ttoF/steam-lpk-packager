import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'catalog.sqlite')

def calculate_rollups():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=" * 60)
    print("📊 STEAM WORKSHOP TOTAL METADATA SIZE ROLLUP")
    print("=" * 60)

    # 1. Total across all items
    cursor.execute("SELECT COUNT(*), SUM(file_size) FROM models")
    total_count, total_bytes = cursor.fetchone()
    total_bytes = total_bytes or 0
    total_gb = total_bytes / (1024 * 1024 * 1024)
    print(f"Total Workshop Items : {total_count:,}")
    print(f"Total Collection Size: {total_gb:.2f} GB ({total_bytes:,} bytes)")
    print("-" * 60)

    # 2. Live2D Size
    cursor.execute("SELECT COUNT(*), SUM(file_size) FROM models WHERE steam_type = 'Live2D'")
    l2d_count, l2d_bytes = cursor.fetchone()
    l2d_bytes = l2d_bytes or 0
    l2d_gb = l2d_bytes / (1024 * 1024 * 1024)
    l2d_avg = (l2d_bytes / l2d_count / (1024 * 1024)) if l2d_count > 0 else 0
    print(f"🎭 Live2D Models      : {l2d_count:,} items")
    print(f"   Size Subtotal     : {l2d_gb:.2f} GB")
    print(f"   Avg File Size     : {l2d_avg:.2f} MB")
    print("-" * 60)

    # 3. Spine Size
    cursor.execute("SELECT COUNT(*), SUM(file_size) FROM models WHERE steam_type = 'Spine'")
    spine_count, spine_bytes = cursor.fetchone()
    spine_bytes = spine_bytes or 0
    spine_gb = spine_bytes / (1024 * 1024 * 1024)
    spine_avg = (spine_bytes / spine_count / (1024 * 1024)) if spine_count > 0 else 0
    print(f"💀 Spine Models       : {spine_count:,} items")
    print(f"   Size Subtotal     : {spine_gb:.2f} GB")
    print(f"   Avg File Size     : {spine_avg:.2f} MB")
    print("-" * 60)

    # 4. Other/Unclassified Size
    cursor.execute("SELECT COUNT(*), SUM(file_size) FROM models WHERE steam_type = 'Other'")
    other_count, other_bytes = cursor.fetchone()
    other_bytes = other_bytes or 0
    other_gb = other_bytes / (1024 * 1024 * 1024)
    other_avg = (other_bytes / other_count / (1024 * 1024)) if other_count > 0 else 0
    print(f"❓ Other/Unclassified : {other_count:,} items")
    print(f"   Size Subtotal     : {other_gb:.2f} GB")
    print(f"   Avg File Size     : {other_avg:.2f} MB")
    print("-" * 60)

    # 5. Outliers (> 100 MB)
    cursor.execute("SELECT COUNT(*) FROM models WHERE file_size > 100 * 1024 * 1024")
    outliers_100 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM models WHERE file_size > 500 * 1024 * 1024")
    outliers_500 = cursor.fetchone()[0]
    print(f"🐘 Outliers (> 100MB) : {outliers_100:,} items")
    print(f"   Gigantic (> 500MB) : {outliers_500:,} items")
    print("=" * 60)

    conn.close()

if __name__ == '__main__':
    calculate_rollups()
