import json
import bpy

# ------------------------------------------------------------
# Create BIM project
# ------------------------------------------------------------


# ------------------------------------------------------------
# JSON path
# ------------------------------------------------------------

json_path = r"tmp\JSON\f20659e7-028f-4a66-9d7b-b6e7adbc7625.json"

bpy.ops.object.select_all(action="DESELECT")



# ------------------------------------------------------------
# Bounding Box Creator
# ------------------------------------------------------------

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


def clean_hierarchy(node, fundamental_parent=None):
    obj_name = node["id"].split("#")[1]
    obj = bpy.data.objects.get(obj_name)

    if not obj:
        print(f"Object '{obj_name}' not found in scene")
        return

    is_fundamental = node.get("isFundamental", False)
    to_delete = node.get("toBeDeleted", False)
    to_simplify = node.get("toBeSimplified", False)

    # update fundamental parent
    if is_fundamental and node.get("children",False):
        fundamental_parent = obj

    # process children first
    for child in node.get("children", []):
        clean_hierarchy(child, fundamental_parent)

    # delete takes priority
    if to_delete:
        print(f"Deleting object: {obj.name}")
        reparent_children(obj, fundamental_parent)
        bpy.data.objects.remove(obj, do_unlink=True)
        return

    # simplify
    if to_simplify and obj.type == "MESH":
        print(f"Simplifying object: {obj.name}")
        reparent_children(obj, fundamental_parent)
        create_bbox(obj, fundamental_parent)
        bpy.data.objects.remove(obj, do_unlink=True)

# ------------------------------------------------------------
# Load JSON and start process
# ------------------------------------------------------------

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
            assembly_children.append(child)
    if len(mesh_children) > 0:
        for child in mesh_children:
            child.select_set(True)
        
        bpy.context.view_layer.objects.active = mesh_children[0]
        mesh_children=[]
        bpy.ops.object.join()
        joined_obj = bpy.context.view_layer.objects.active
        old_name = obj.name
        parent = obj.parent
        world_matrix = joined_obj.matrix_world.copy()
        children= obj.children
        sobstitute_parent = False
        # if len(children) > 1:
        #     for child in children:
        #         if not child==joined_obj and not child.type == "MESH":
        #             sobstitute_parent = False
        #         if not child==joined_obj and child.type == "MESH":
        #             sobstitute_parent = True
        # if len(children) == 1:
        #     sobstitute_parent = True
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
    if len(assembly_children) > 0:
        for child in assembly_children:
            join_children(child,find_node_by_id(node,child.name))


with open(json_path, encoding="utf-8") as f:
    file_url = r"tmp\gLTF\PSI_SLS2_Girder_Superbend.gltf"
    data = json.load(f)
    bpy.ops.import_scene.gltf(filepath=file_url)
    root_name = data["id"].split("#")[1]
    root_obj = bpy.data.objects.get(root_name)

    if root_obj:
        if data["isFundamental"]:
            clean_hierarchy(data, root_obj)
        else:
            clean_hierarchy(data)
        # join_children(root_obj,data)
    else:
        print(f"Root object '{root_name}' not found in scene")