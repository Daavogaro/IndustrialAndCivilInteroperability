import json

import bpy
import sys
import os

# Get arguments after `--`
argv = sys.argv
argv = argv[argv.index("--") + 1:]  # only args after --

if len(argv) < 2:
    raise ValueError("Expected GLTF path and JSON path after --")

gltf_path = os.path.abspath(argv[0])
json_path = os.path.abspath(argv[1])
save_blend = len(argv) > 2 and argv[2].strip().lower() in {"1", "true", "yes"}

with open(json_path, encoding="utf-8") as f:
    data = json.load(f)

if not os.path.exists(gltf_path):
    raise FileNotFoundError(f"File not found: {gltf_path}")

# Clear the existing scene (optional)
bpy.ops.wm.read_factory_settings(use_empty=True)

# Import the GLTF file
print("STATUS: Loading node data")
print(f"STATUS: Starting GLTF import from {gltf_path}")
bpy.ops.import_scene.gltf(filepath=gltf_path)

print("STATUS: GLTF import completed")

if save_blend:
    output_blend = os.path.splitext(gltf_path)[0] + "_imported.blend"
    print(f"STATUS: Saving blend file to {output_blend}")
    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    print(f"STATUS: GLTF imported and saved to {output_blend}")
else:
    print("STATUS: GLTF import completed without saving a blend file")