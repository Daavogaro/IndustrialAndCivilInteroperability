import json
from bpy import context
import bpy
import sys
import os
import ifcopenshell
import bonsai.tool.ifc as ifcTool
import bonsai.tool as tool



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
            reduce_mesh(obj)
            reparent(obj, current_fundamental)

        # ---- RECURSE ----
        for child in children:
            clean_hierarchy(child, current_fundamental)

def find_node_by_id(node: dict, target_id: str):
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
                    unselected_objects = [obj for obj in bpy.data.objects if obj not in selected_objects and not obj.name.startswith("Ifc")]
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

def create_empty_at_cursor_with_element_orientation( element: ifcopenshell.entity_instance) -> bpy.types.Object:
    # Ensure BlenderBIM updates the placement first
    element_obj = tool.Ifc.get_object(element)
    name = "Port_" + element.Name
    obj = bpy.data.objects.new(name, None)
    # Now element_obj.matrix_world is correct
    obj.matrix_world = element_obj.matrix_world.copy()
    return obj

def add_port(ifc: type[tool.Ifc], system: type[tool.System], element: ifcopenshell.entity_instance) -> bpy.types.Object:
    system.load_ports(element, system.get_ports(element))
    obj = create_empty_at_cursor_with_element_orientation(element)
    port = system.run_root_assign_class(obj=obj, ifc_class="IfcDistributionPort", should_add_representation=False)
    ifc.run("system.assign_port", element=element, port=port)
    return obj

def node_conversion_in_ifc(node: dict, blender_node: bpy.types.Object, parent: bpy.types.Object | None = None):
    def _enum_from_uri(value: str, default: str = "NOTDEFINED") -> str:
        if not value:
            return default
        return value.split("#")[-1]

    def _run_in_view3d(operation):
        for window in context.window_manager.windows:
            screen = window.screen
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    with context.temp_override(window=window, area=area):
                        return operation()
        raise RuntimeError("No VIEW_3D area found for BIM operators")

    def _assign_and_configure(
        target_obj: bpy.types.Object,
        original_name: str,
        ifc_class: str,
        predefined_type: str,
        object_type: str | None,
        predefined_index: int,
        parent_obj: bpy.types.Object | None,
    ) -> bpy.types.Object:
        def _operation():
            target_obj.select_set(True)
            bpy.context.view_layer.objects.active = target_obj

            bpy.ops.bim.assign_class(ifc_class=ifc_class)
            bpy.ops.object.select_all(action="DESELECT")

            new_ifc_element = bpy.context.view_layer.objects.active
            bpy.ops.bim.enable_editing_attributes(mass_operation=False)
            attributes = new_ifc_element.BIMAttributeProperties.attributes
            attributes[1].string_value = original_name
            if ifc_class not in {"IfcDistributionElement"}:
                attributes[predefined_index].enum_value = predefined_type

            if predefined_type == "USERDEFINED" and object_type:
                attributes[3].string_value = object_type

            bpy.ops.bim.edit_attributes()

            if parent_obj is not None and ifc_class not in {"IfcDistributionElement"}:
                print(f"    And its parent is: {parent_obj.name}")
                bpy.ops.bim.enable_editing_aggregate()
                new_ifc_element.BIMObjectAggregateProperties.relating_object = parent_obj
                bpy.ops.bim.aggregate_assign_object(relating_object=parent_obj.BIMObjectProperties.ifc_definition_id)
                new_ifc_element.parent = parent_obj
            if ifc_class in {"IfcDistributionElement","IfcDistributionFlowElement", "IfcDistributionChamberElement","IfcEnergyConversionDevice","IfcFlowController","IfcFlowFitting","IfcFlowMovingDevice","IfcFlowSegment","IfcFlowStorageDevice","IfcFlowTerminal","IfcFlowTreatmentDevice",}:
                ifc_obj=ifcTool.Ifc.get_entity(new_ifc_element)
                port = add_port(tool.Ifc, tool.System, ifc_obj)
                port.parent = new_ifc_element
                port.matrix_parent_inverse = new_ifc_element.matrix_world.inverted()

            return new_ifc_element

        return _run_in_view3d(_operation)

    found_node = find_node_by_id(node, blender_node.name)
    original_name = blender_node.name

    if blender_node.type != "MESH" and found_node is None:
        print(f"Node {blender_node.name} of type {blender_node.type} not found in JSON, skipping conversion")
        return

    if blender_node.type == "MESH" and found_node is None and not blender_node.name.endswith("_Part"):
        print(f"Node {blender_node.name} of type {blender_node.type} not found in JSON, skipping conversion")
        return

    print("________________________________________________________________________")
    print(f"Converting node {blender_node.name} of type {blender_node.type}")
    print(blender_node)

    if found_node is None:
        ifc_class = "IfcElementAssembly"
        predefined_type = "NOTDEFINED"
        object_type = None
        predefined_index = 6
    elif blender_node.type != "MESH":
        ifc_class = "IfcElementAssembly"
        predefined_type = _enum_from_uri(found_node.get("predefinedType", "NOTDEFINED"))
        object_type = found_node.get("objectType")
        predefined_index = 6
    else:
        ifc_class = _enum_from_uri(found_node.get("ifcClass", "IfcBuildingElementProxy"), "IfcBuildingElementProxy")
        predefined_type = _enum_from_uri(found_node.get("predefinedType", "NOTDEFINED"))
        object_type = found_node.get("objectType")
        predefined_index = 5

    new_parent = _assign_and_configure(
        target_obj=blender_node,
        original_name=original_name,
        ifc_class=ifc_class,
        predefined_type=predefined_type,
        object_type=object_type,
        predefined_index=predefined_index,
        parent_obj=parent,
    )
    

    for child in blender_node.children:
        node_conversion_in_ifc(node, child, new_parent)




# Get arguments after `--`
argv = sys.argv
argv = argv[argv.index("--") + 1:]  # only args after --


json_path = os.path.abspath(argv[0])
save_blend = len(argv) > 2 and argv[1].strip().lower() in {"1", "true", "yes"}

with open(json_path, encoding="utf-8") as f:
    node:dict = json.load(f)



# Clear the existing scene (optional)
# bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.bim.create_project()
bpy.ops.bim.new_project(preset='metric_m')


# Import the GLTF file
print("STATUS: Loading node data")
create_hierarchy(node)
blender_node = bpy.data.objects.get(node["id"].split("#")[1])
if blender_node:
    node_conversion_in_ifc(node, blender_node)


print("STATUS: GLTF import completed")

if save_blend:
    output_blend = os.path.splitext(json_path)[0] + "_imported.blend"
    print(f"STATUS: Saving blend file to {output_blend}")
    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    print(f"STATUS: GLTF imported and saved to {output_blend}")
else:
    print("STATUS: GLTF import completed without saving a blend file")