import json
from bpy import context
import bpy
import sys
import os

def find_node_by_id(node: dict, target_id: str):
    if node["id"].split("#")[1] == target_id:
        return node
    for child in node.get("children", []):
        result = find_node_by_id(child, target_id)
        if result:
            return result
    return None

def node_conversion_in_ifc(node: dict, blender_node: bpy.types.Object,parent: bpy.types.Object | None = None):
    found_node = find_node_by_id(node, blender_node.name)
    if blender_node.type is not "MESH":
        if found_node is None:
            print(f"Node {blender_node.name} of type {blender_node.type} not found in JSON, skipping conversion")
            return
        else:
            print("________________________________________________________________________")
            print(f"Converting node {blender_node.name} of type {blender_node.type}")
            original_name=blender_node.name
            bpy.ops.bim.assign_class(ifc_class="IfcElementAssembly")
            bpy.ops.object.select_all(action='DESELECT')
            new_ifc_element=bpy.context.view_layer.objects.active
            bpy.ops.bim.enable_editing_attributes(mass_operation=False) # Enable the editing attributes mode
            new_ifc_element.BIMAttributeProperties.attributes[1].string_value = original_name # Edit the Name attribute
            predefined_type = found_node.get("predefinedType", "NOTDEFINED")
            new_ifc_element.BIMAttributeProperties.attributes[6].enum_value = predefined_type.split("#")[1] # Edit the PredefinedType attribute
            if predefined_type.split("#")[1] == "USERDEFINED":
                object_type = found_node.get("objectType", None)
                if object_type is not None:
                    new_ifc_element.BIMAttributeProperties.attributes[3].string_value = object_type # Edit the ObjectType attribute
            bpy.ops.bim.edit_attributes() # Confirm the editing
            if not parent == None:
                print(f"    And its parent is: {parent.name}")
                # Aggregate the new IfcElementAssmebly under its parent
                bpy.ops.bim.enable_editing_aggregate()
                new_ifc_element.BIMObjectAggregateProperties.relating_object = parent
                bpy.ops.bim.aggregate_assign_object(relating_object=parent.BIMObjectProperties.ifc_definition_id)
                # Recreate the tree in the Blender Menu giving the parent relation to the Blender Object. Is not necessary for the IFC sake, but is useful for the Blender visualization
                new_ifc_element.parent = parent 
            for child in blender_node.children:
                node_conversion_in_ifc(node, child, blender_node)
    else:
        if found_node is None:
            if blender_node.name.endswith("_Part"):
                print("________________________________________________________________________")
                original_name=blender_node.name
                bpy.ops.bim.assign_class(ifc_class="IfcElementAssembly")
                bpy.ops.object.select_all(action='DESELECT')
                new_ifc_element=bpy.context.view_layer.objects.active
                bpy.ops.bim.enable_editing_attributes(mass_operation=False) # Enable the editing attributes mode
                new_ifc_element.BIMAttributeProperties.attributes[1].string_value = original_name # Edit the Name attribute
                new_ifc_element.BIMAttributeProperties.attributes[6].enum_value = "NOTDEFINED" # Edit the PredefinedType attribute
                bpy.ops.bim.edit_attributes() # Confirm the editing
                if not parent == None:
                    print(f"    And its parent is: {parent.name}")
                    # Aggregate the new IfcElementAssmebly under its parent
                    bpy.ops.bim.enable_editing_aggregate()
                    new_ifc_element.BIMObjectAggregateProperties.relating_object = parent
                    bpy.ops.bim.aggregate_assign_object(relating_object=parent.BIMObjectProperties.ifc_definition_id)
                    # Recreate the tree in the Blender Menu giving the parent relation to the Blender Object. Is not necessary for the IFC sake, but is useful for the Blender visualization
                    new_ifc_element.parent = parent 
                for child in blender_node.children:
                    node_conversion_in_ifc(node, child, blender_node)
            else:
                print(f"Node {blender_node.name} of type {blender_node.type} not found in JSON, skipping conversion")
                return
        else:
            print("________________________________________________________________________")
            print(f"Converting node {blender_node.name} of type {blender_node.type}")
            original_name=blender_node.name
            ifc_class = found_node.get("ifcClass", "IfcBuildingElementProxy").split("#")[1]
            bpy.ops.bim.assign_class(ifc_class=ifc_class)
            bpy.ops.object.select_all(action='DESELECT')
            new_ifc_element=bpy.context.view_layer.objects.active
            bpy.ops.bim.enable_editing_attributes(mass_operation=False) # Enable the editing attributes mode
            new_ifc_element.BIMAttributeProperties.attributes[1].string_value = original_name # Edit the Name attribute
            predefined_type = found_node.get("predefinedType", "NOTDEFINED")
            new_ifc_element.BIMAttributeProperties.attributes[6].enum_value = predefined_type.split("#")[1] # Edit the PredefinedType attribute
            if predefined_type.split("#")[1] == "USERDEFINED":
                object_type = found_node.get("objectType", None)
                if object_type is not None:
                    new_ifc_element.BIMAttributeProperties.attributes[3].string_value = object_type # Edit the ObjectType attribute
            bpy.ops.bim.edit_attributes() # Confirm the editing
            if not parent == None:
                print(f"    And its parent is: {parent.name}")
                # Aggregate the new IfcElementAssmebly under its parent
                bpy.ops.bim.enable_editing_aggregate()
                new_ifc_element.BIMObjectAggregateProperties.relating_object = parent
                bpy.ops.bim.aggregate_assign_object(relating_object=parent.BIMObjectProperties.ifc_definition_id)
                # Recreate the tree in the Blender Menu giving the parent relation to the Blender Object. Is not necessary for the IFC sake, but is useful for the Blender visualization
                new_ifc_element.parent = parent 
            for child in blender_node.children:
                node_conversion_in_ifc(node, child, blender_node)



