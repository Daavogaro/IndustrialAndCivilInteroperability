import json
from bpy import context
import bpy
import sys
import os

def create_bbox(obj, fundamental_parent=None):

    original_mesh_name = obj.data.name
    original_object_name = obj.name

    # rename old object
    obj.data.name = f"{original_mesh_name}_old"
    obj.name = f"{original_object_name}_old"

    # copy bounding box vertices (local space)
    verts = [v[:] for v in obj.bound_box]

    faces = [
        (0,1,2,3),
        (4,5,6,7),
        (0,1,5,4),
        (2,3,7,6),
        (1,2,6,5),
        (0,3,7,4)
    ]

    mesh = bpy.data.meshes.new(original_mesh_name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    bbox = bpy.data.objects.new(original_object_name, mesh)
    # maintain hierarchy
    bbox.parent = fundamental_parent if fundamental_parent else obj.parent
    # preserve transform
    bbox.matrix_world = obj.matrix_world.copy()

  

    # link to same collections
    for col in obj.users_collection:
        col.objects.link(bbox)

    # copy materials safely
    for slot in obj.material_slots:
        if slot.material:
            bbox.data.materials.append(slot.material)
    bpy.data.objects.remove(obj, do_unlink=True)
    print(f"Bounding box created for: {original_object_name}")

    return bbox


# ------------------------------------------------------------
# Hierarchy Cleaning
# ------------------------------------------------------------

def reparent_children(obj, new_parent):
    if new_parent:
        for child in list(obj.children):
            world_matrix = child.matrix_world.copy()
            child.parent = new_parent
            child.matrix_world = world_matrix

def reparent(obj, new_parent):
    if new_parent:
        world_matrix = obj.matrix_world.copy()
        obj.parent = new_parent
        obj.matrix_world = world_matrix

def reduce_mesh(obj):
    if obj.type == 'MESH':
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        print(obj.name)
        for window in context.window_manager.windows:
            screen = window.screen
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    with context.temp_override(window=window, area=area):
                        bpy.ops.object.editmode_toggle()
                        bpy.ops.mesh.select_all(action='SELECT')
                        bpy.ops.mesh.quads_convert_to_tris()
                        bpy.ops.mesh.remove_doubles()
                        bpy.ops.mesh.select_all(action='SELECT')
                        bpy.ops.mesh.tris_convert_to_quads()
                        bpy.ops.mesh.select_all(action='SELECT')
                        bpy.ops.mesh.delete_loose()
                        bpy.ops.mesh.select_all(action='SELECT')
                        bpy.ops.mesh.face_make_planar()
                        bpy.ops.mesh.select_all(action='SELECT')
                        bpy.ops.mesh.dissolve_limited()   
                        bpy.ops.mesh.dissolve_limited(angle_limit=0.261799)
                        bpy.ops.mesh.dissolve_limited(angle_limit=0.04)
                        bpy.ops.object.editmode_toggle()
                        bpy.ops.object.select_all(action='DESELECT')
                    break



def clean_hierarchy(node, current_fundamental=None):
    obj_name = node["id"].split("#")[1]
    obj = bpy.data.objects.get(obj_name)

    if not obj:
        print(f"Object '{obj_name}' not found in scene")
        return

    is_fundamental = node.get("isFundamental", False)
    to_delete = node.get("toBeDeleted", False)
    to_simplify = node.get("toBeSimplified", False)
    children = node.get("children", [])

    # ----------------------------
    # CASE 1: FUNDAMENTAL NODE
    # ----------------------------
    if is_fundamental:
        if current_fundamental and obj != current_fundamental:
            reparent(obj, current_fundamental)

        new_fundamental = obj

        for child in children:
            clean_hierarchy(child, new_fundamental)

    # ----------------------------
    # CASE 2: NON-FUNDAMENTAL NODE
    # ----------------------------
    else:
        # ---- DELETE ----
        if to_delete and obj.type == "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)
            return  # stop recursion entirely

        # ---- SIMPLIFY ----
        if to_simplify and obj.type == "MESH":
            new_obj = create_bbox(obj)
            obj = new_obj  # continue processing with the new bbox object

        # ---- REPARENT ----
        if current_fundamental and obj != current_fundamental:
            reparent(obj, current_fundamental)

        # ---- RECURSE ----
        for child in children:
            clean_hierarchy(child, current_fundamental)

def find_node_by_id(node, target_id):
    if node["id"].split("#")[1] == target_id:
        return node
    for child in node.get("children", []):
        result = find_node_by_id(child, target_id)
        if result:
            return result
    return None



def join_children(obj: bpy.types.Object, node: dict):
    mesh_children = []
    assembly_children = []
    bpy.context.view_layer.objects.active = None
    bpy.ops.object.select_all(action="DESELECT")
    for child in obj.children:
        if child.type == "MESH":
            child_node = find_node_by_id(node, child.name)
            if child_node and not child_node.get("isFundamental", False):
                mesh_children.append(child)
        else:
            if len(child.children)>0:
                assembly_children.append(child)
            else:
                bpy.data.objects.remove(child, do_unlink=True)
    if len(mesh_children) > 0:
        for child in mesh_children:
            child.select_set(True)
        active_obj = mesh_children[0]
        bpy.context.view_layer.objects.active = active_obj
        mesh_children=[]

        for window in context.window_manager.windows:
            screen = window.screen
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    with context.temp_override(window=window, area=area):
                        bpy.ops.object.join()
                    break
                
        joined_obj = bpy.context.view_layer.objects.active
        old_name = obj.name
        parent = obj.parent
        world_matrix = joined_obj.matrix_world.copy()
        children= obj.children
        sobstitute_parent = False
        if len(children) > 1:
            for child in children:
                if not child==joined_obj and not child.type == "MESH":
                    sobstitute_parent = False
                if not child==joined_obj and child.type == "MESH":
                    sobstitute_parent = True
        if len(children) == 1:
            sobstitute_parent = True
        if sobstitute_parent:
            # Sobstitute the father node with a mesh node that contains the joined meshes
            new_obj= bpy.data.objects.new(joined_obj.name,joined_obj.data.copy())
            for collection in obj.users_collection:
                collection.objects.link(new_obj)
            # Reassign the properties
            bpy.data.objects.remove(joined_obj, do_unlink=True)
            children= obj.children
            bpy.data.objects.remove(obj, do_unlink=True)
            new_obj.name = old_name
            new_obj.data.name = old_name
            new_obj.parent = parent
            new_obj.matrix_world =world_matrix
            # Reassign all the nodes to the new object
            for child in children:
                old_world = child.matrix_world.copy()
                child.parent = new_obj
                child.matrix_world = old_world
        else:
            if len(children) > 1:
                joined_obj.name = f"{obj.name}_Part"
                joined_obj.data.name = f"{obj.name}_Part"
    if len(assembly_children) > 0:
        for child in assembly_children:
            child_node = find_node_by_id(node, child.name)
            if child_node:
                join_children(child, child_node)


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
            if node.get("isFundamental", False):
                clean_hierarchy(node, node_obj)
            join_children(node_obj, node)
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
                    if node.get("isFundamental", False):
                        clean_hierarchy(node, obj)
                    join_children(obj, node)
            else:
                if node.get("isFundamental", False):
                    clean_hierarchy(node, node_obj)
                join_children(node_obj, node)

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
# bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.bim.create_project()
bpy.ops.bim.new_project(preset='metric_m')


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