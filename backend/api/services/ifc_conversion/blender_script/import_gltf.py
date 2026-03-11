import json

import bpy
import sys
import os


def select_hierarchy(obj):
    obj.select_set(True)
    selected = [obj]

    for child in obj.children:
        selected.extend(select_hierarchy(child))

    return selected
def create_hierarchy(node: dict, parent=None):

    file_url = node.get("fileUrl")

    if file_url:
        bpy.ops.import_scene.gltf(filepath=file_url)
        node_obj = bpy.context.view_layer.objects.active

        world_matrix = node_obj.matrix_world.copy()

        if parent:
            node_obj.parent = parent
            node_obj.matrix_world = world_matrix
        else:
            if node_obj.name != node.get("id").split("#")[1]:
                obj = bpy.data.objects.get(node.get("id").split("#")[1] )
                if obj:
                    world_matrix = obj.matrix_world.copy()
                    obj.parent=None
                    obj.matrix_world = world_matrix
                    bpy.ops.object.select_all(action='DESELECT')
                    selected_objects = select_hierarchy(obj)
                    unselected_objects = [obj for obj in bpy.data.objects if obj not in selected_objects]
                    for unselected in unselected_objects:
                        bpy.data.objects.remove(unselected, do_unlink=True)

    else:
        bpy.ops.object.empty_add(type='PLAIN_AXES', align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
        empty_obj = bpy.context.view_layer.objects.active
        print(empty_obj)
        empty_obj.name = node.get("id").split("#")[1]

        if parent:
            empty_obj.parent = parent

        for child in node.get("children", []):
            create_hierarchy(child, empty_obj)


# Get arguments after `--`
argv = sys.argv
argv = argv[argv.index("--") + 1:]  # only args after --


json_path = os.path.abspath(argv[0])
save_blend = len(argv) > 2 and argv[1].strip().lower() in {"1", "true", "yes"}

with open(json_path, encoding="utf-8") as f:
    node = json.load(f)



# Clear the existing scene (optional)
bpy.ops.wm.read_factory_settings(use_empty=True)

# Import the GLTF file
print("STATUS: Loading node data")
create_hierarchy(node)

print("STATUS: GLTF import completed")

if save_blend:
    output_blend = os.path.splitext(json_path)[0] + "_imported.blend"
    print(f"STATUS: Saving blend file to {output_blend}")
    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    print(f"STATUS: GLTF imported and saved to {output_blend}")
else:
    print("STATUS: GLTF import completed without saving a blend file")