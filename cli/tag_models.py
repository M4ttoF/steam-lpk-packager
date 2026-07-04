import os
import sys

# Dynamic NVIDIA CUDA & cuDNN DLL injection for Python packages under Windows
import site
paths_to_add = []
for base_path in site.getsitepackages():
    nvidia_root = os.path.join(base_path, 'nvidia')
    if os.path.isdir(nvidia_root):
        for folder in os.listdir(nvidia_root):
            bin_dir = os.path.join(nvidia_root, folder, 'bin')
            if os.path.isdir(bin_dir):
                paths_to_add.append(bin_dir)

# Add CUDA toolkit bin folder fallback
cuda_x64_bin = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.1\bin\x64"
if os.path.isdir(cuda_x64_bin):
    paths_to_add.append(cuda_x64_bin)

# Append to PATH
if paths_to_add:
    os.environ["PATH"] = ";".join(paths_to_add) + ";" + os.environ.get("PATH", "")

import json
import sqlite3
import numpy as np
import pandas as pd
import onnxruntime as rt
import huggingface_hub
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'catalog.sqlite')
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')

# Repo target as requested
MODEL_REPO = "SmilingWolf/wd-vit-large-tagger-v3"
MODEL_FILENAME = "model.onnx"
LABEL_FILENAME = "selected_tags.csv"

# Thresholds as requested
SCORE_GENERAL_THRESH = 0.35
SCORE_CHARACTER_THRESH = 0.85

kaomojis = [
    "0_0", "(o)_(o)", "+_+", "+_-", "._.", "<o>_<o>", "<|>_<|>", "=_=",
    ">_<", "3_3", "6_9", ">_o", "@_@", "^_^", "o_o", "u_u", "x_x", "|_|", "||_||",
]

def load_labels(dataframe) -> tuple:
    name_series = dataframe["name"]
    name_series = name_series.map(
        lambda x: x.replace("_", " ") if x not in kaomojis else x
    )
    tag_names = name_series.tolist()
    rating_indexes = list(np.where(dataframe["category"] == 9)[0])
    general_indexes = list(np.where(dataframe["category"] == 0)[0])
    character_indexes = list(np.where(dataframe["category"] == 4)[0])
    return tag_names, rating_indexes, general_indexes, character_indexes

class WDImageTagger:
    def __init__(self):
        print(f"Downloading/Loading WD-Tagger model from {MODEL_REPO}...")
        csv_path = huggingface_hub.hf_hub_download(MODEL_REPO, LABEL_FILENAME)
        model_path = huggingface_hub.hf_hub_download(MODEL_REPO, MODEL_FILENAME)
        
        tags_df = pd.read_csv(csv_path)
        self.tag_names, self.rating_indexes, self.general_indexes, self.character_indexes = load_labels(tags_df)
        
        # Load ONNX session (ONNXRuntime optimizes this automatically for CPU/GPU)
        self.session = rt.InferenceSession(model_path, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
        _, height, width, _ = self.session.get_inputs()[0].shape
        self.target_size = height
        print(f"Model loaded successfully. Target resolution: {self.target_size}x{self.target_size}")

    def prepare_image(self, image):
        # Convert RGBA to RGB using a clean white background canvas
        if image.mode == 'RGBA':
            canvas = Image.new("RGBA", image.size, (255, 255, 255))
            canvas.alpha_composite(image)
            image = canvas.convert("RGB")
        else:
            image = image.convert("RGB")

        # Pad image to square
        w, h = image.size
        max_dim = max(w, h)
        pad_left = (max_dim - w) // 2
        pad_top = (max_dim - h) // 2

        padded_image = Image.new("RGB", (max_dim, max_dim), (255, 255, 255))
        padded_image.paste(image, (pad_left, pad_top))

        # Resize to model input target size
        if max_dim != self.target_size:
            padded_image = padded_image.resize((self.target_size, self.target_size), Image.Resampling.BICUBIC)

        image_array = np.asarray(padded_image, dtype=np.float32)
        # Convert PIL-native RGB to BGR as expected by the model
        image_array = image_array[:, :, ::-1]
        return np.expand_dims(image_array, axis=0)

    def tag_image(self, image_path):
        try:
            with Image.open(image_path) as img:
                prepared = self.prepare_image(img)
        except Exception as e:
            return None, f"Failed to load image: {e}"

        input_name = self.session.get_inputs()[0].name
        label_name = self.session.get_outputs()[0].name
        
        # Run model inference
        preds = self.session.run([label_name], {input_name: prepared})[0]
        labels = list(zip(self.tag_names, preds[0].astype(float)))

        # 1. Characters: threshold >= 0.85
        char_tags = [labels[i] for i in self.character_indexes if labels[i][1] >= SCORE_CHARACTER_THRESH]
        char_tags.sort(key=lambda x: x[1], reverse=True)

        # 2. General Tags: threshold >= 0.35
        general_tags = [labels[i] for i in self.general_indexes if labels[i][1] >= SCORE_GENERAL_THRESH]
        general_tags.sort(key=lambda x: x[1], reverse=True)

        # Combine: Characters first, then general tags
        sorted_tags = [item[0] for item in char_tags] + [item[0] for item in general_tags]
        return sorted_tags, None

def run_tagging(force=False):
    print("=" * 60)
    print("LPK STUDIO — DEEP LEARNING MODEL TAGGING")
    print(f"DATABASE: {DB_PATH}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Query all compatible models with thumbnails and their tags
    c.execute("""
        SELECT id, thumbnail_local, tags 
        FROM models 
        WHERE compatible = 1 
          AND thumbnail_local IS NOT NULL 
          AND thumbnail_local != ''
    """)
    all_targets = c.fetchall()
    conn.close()

    # Filter targets based on heuristic if not forcing
    targets = []
    steam_keywords = {"live2d", "spine", "female", "male", "g", "r-15", "r-18", "voice", "text", "face tracking", "drag areas", "hand tracking"}

    for item_id, thumb_path, tags_str in all_targets:
        if force:
            targets.append((item_id, thumb_path))
            continue

        # Parse tags
        try:
            current_tags = json.loads(tags_str) if tags_str else []
        except:
            current_tags = []

        # Heuristic: If tags count is > 5 or contains any non-steam tag, it has deep learning tags
        has_rich_tags = False
        if len(current_tags) > 5:
            has_rich_tags = True
        else:
            for t in current_tags:
                if t.lower() not in steam_keywords:
                    has_rich_tags = True
                    break

        if not has_rich_tags:
            targets.append((item_id, thumb_path))

    if not targets:
        print("No models found that require tagging.")
        return

    print(f"Found {len(targets)} models matching heuristic filter for tagging.")
    
    # Initialize the model tagger
    tagger = WDImageTagger()

    db_updates = []
    tagged_count = 0
    batch_size = 100

    try:
        for idx, (item_id, thumb_rel_path) in enumerate(targets, 1):
            thumb_path = os.path.join(PUBLIC_DIR, thumb_rel_path.lstrip("/").replace("/", os.sep))
            
            if not os.path.exists(thumb_path):
                continue

            tags, err = tagger.tag_image(thumb_path)
            if err:
                print(f"  [{idx}/{len(targets)}] [{item_id}] ERROR: {err}")
                continue

            # Save tags as JSON string array
            tags_json = json.dumps(tags, ensure_ascii=False)
            db_updates.append((tags_json, item_id))
            tagged_count += 1

            character_names_set = set([tagger.tag_names[i] for i in tagger.character_indexes])
            char_prefix = [t for t in tags if t in character_names_set]
            if char_prefix:
                print(f"  [{idx}/{len(targets)}] Tagged {item_id}: Char={char_prefix} | Top Tags: {tags[:6]}")
            else:
                print(f"  [{idx}/{len(targets)}] Tagged {item_id}: Top Tags: {tags[:6]}")

            # Commit batch of 100 items
            if len(db_updates) >= batch_size:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.executemany("UPDATE models SET tags = ? WHERE id = ?", db_updates)
                conn.commit()
                conn.close()
                db_updates = []
                print(f"  --> Committed batch of {batch_size} tags to catalog database.")

        # Commit remaining updates
        if db_updates:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.executemany("UPDATE models SET tags = ? WHERE id = ?", db_updates)
            conn.commit()
            conn.close()
            print(f"  --> Committed final batch of {len(db_updates)} tags to catalog database.")

    except KeyboardInterrupt:
        print("\n[WARNING] Process interrupted by user. Saving progress...")
        if db_updates:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.executemany("UPDATE models SET tags = ? WHERE id = ?", db_updates)
            conn.commit()
            conn.close()
        sys.exit(0)

    print("\n" + "=" * 60)
    print("TAGGING COMPLETE")
    print(f"  Models Tagged successfully : {tagged_count}")
    print("=" * 60)

if __name__ == '__main__':
    force_run = '--force' in sys.argv
    run_tagging(force_run)
