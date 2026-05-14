# Steam LPK Packager

A tool to extract `.lpk` files (Live2DViewerEX format) and package them into usable ZIP files for Spine or Live2D. It can handle both standalone `.zip` files and folders downloaded from the Steam Workshop.

## Features
- Extracts `.lpk` files automatically.
- Detects if the model is **Spine** or **Live2D**.
- Organizes textures, motions, and sounds into a clean structure.
- Renames files to standard conventions (e.g., `skeleton_0.skel`, `model3.json`).
- Packages the result into a clean ZIP file ready for use.

## Usage
1. Place your source `.zip` files or Steam Workshop folders in a directory named `packages` next to the script.
2. Run the script:
   ```bash
   python batch_extract_models.py
   ```
3. The extracted and packaged models will appear in `live2d_packages` and `spine_packages`.

## Dependencies
- Python 3.x
- FFmpeg (must be available in your system PATH for audio conversion)
- Pillow (for texture processing)

## Credits
This tool bundles the `lpk2moc3-spine` converter logic.
