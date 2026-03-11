import json
import bpy


json_path = r"tmp\JSON\4f70f3fb-a94a-4bd8-a9f7-ff27cc0472d1.json"
bpy.context.view_layer.objects.active = None
bpy.ops.object.select_all(action='SELECT')
for obj in bpy.context.selected_objects:
    if obj.type == 'MESH':
        if obj.data.users > 1:
            obj.data = obj.data.copy()
bpy.ops.object.select_all(action='DESELECT')
with open(json_path, encoding="utf-8") as f:
    data = json.load(f)
    root_node = data["id"].split("#")[1]
    obj: bpy.types.Object = bpy.data.objects.get(root_node)

    if obj:
        world_matrix = obj.matrix_world.copy()
        obj.parent=None
        obj.matrix_world = world_matrix
        

        
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.select_grouped(type='CHILDREN_RECURSIVE')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        selected_objects = bpy.context.selected_objects
        unselected_objects = [obj for obj in bpy.data.objects if obj not in selected_objects]
        for unselected in unselected_objects:
            bpy.data.objects.remove(unselected, do_unlink=True)

    else:
        print(f"Object '{root_node}' not found in scene")
