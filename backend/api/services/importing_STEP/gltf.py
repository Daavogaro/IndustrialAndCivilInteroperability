from pygltflib import GLTF2
import numpy as np
import base64
import os
import re

from ...services.importing_STEP.RDF_conversion import NameAndNumber

from ...services.db_requests.name_and_number import name_and_number_query

# ------------------------------------------------------------
# BUFFER PRELOAD (read each buffer only once)
# ------------------------------------------------------------

def preload_buffers(gltf, gltf_file_dir):
    buffer_cache = []

    for buffer in gltf.buffers:
        if buffer.uri:
            if buffer.uri.startswith("data:"):
                comma = buffer.uri.find(',')
                buffer_bytes = base64.b64decode(buffer.uri[comma + 1:])
            else:
                bin_path = os.path.join(gltf_file_dir, buffer.uri)
                with open(bin_path, 'rb') as f:
                    buffer_bytes = f.read()
        else:
            # GLB binary blob
            buffer_bytes = gltf.binary_blob()

        buffer_cache.append(buffer_bytes)

    return buffer_cache


# ------------------------------------------------------------
# ACCESSOR LOADER (FLOAT VEC3 only, fallback path)
# ------------------------------------------------------------

def load_accessor_data(gltf, accessor_idx, buffer_cache):
    accessor = gltf.accessors[accessor_idx]
    buffer_view = gltf.bufferViews[accessor.bufferView]
    buffer_bytes = buffer_cache[buffer_view.buffer]

    start = (buffer_view.byteOffset or 0) + (accessor.byteOffset or 0)
    length = accessor.count * 3 * 4  # FLOAT32 VEC3

    data = buffer_bytes[start:start + length]

    vertices = np.frombuffer(data, dtype=np.float32).reshape(accessor.count, 3)
    return vertices


# ------------------------------------------------------------
# FAST MESH DIMENSIONS (uses accessor min/max when available)
# ------------------------------------------------------------

def get_mesh_dimensions(gltf, mesh_index, buffer_cache):
    mesh = gltf.meshes[mesh_index]

    min_vals = np.array([np.inf, np.inf, np.inf])
    max_vals = np.array([-np.inf, -np.inf, -np.inf])

    for prim in mesh.primitives:
        pos_accessor_idx = prim.attributes.POSITION
        if pos_accessor_idx is None:
            continue

        accessor = gltf.accessors[pos_accessor_idx]

        # ✅ Fast path: use stored bounds (most glTF files have this)
        if accessor.min is not None and accessor.max is not None:
            min_vals = np.minimum(min_vals, np.array(accessor.min))
            max_vals = np.maximum(max_vals, np.array(accessor.max))
        else:
            # Fallback: decode vertex buffer
            vertices = load_accessor_data(gltf, pos_accessor_idx, buffer_cache)
            min_vals = np.minimum(min_vals, vertices.min(axis=0))
            max_vals = np.maximum(max_vals, vertices.max(axis=0))

    dims = max_vals - min_vals
    return dims.tolist()


# ------------------------------------------------------------
# NODE HIERARCHY BUILDER (with mesh dimension cache)
# ------------------------------------------------------------

INVALID_NAME_CHARS = r"[ /\\:\*\?<>\[\]=]"


def sanitize_node_name(raw_name: str) -> str:
    sanitized = re.sub(INVALID_NAME_CHARS, "_", raw_name)
    sanitized = re.sub(r"_+", "_", sanitized)
    return sanitized.strip("_") or "Node"

def build_node_hierarchy(gltf, buffer_cache, node_index, mesh_cache, nameAndNumberList):
    node = gltf.nodes[node_index]
    raw_name = node.name or f"Node_{node_index}"
    clean_name = sanitize_node_name(raw_name)
    

    parts = clean_name.split(".")
    label= ".".join(parts[:-1]) if len(parts) > 1 else clean_name
    number = 1
    def get_by_name(items: list[NameAndNumber], target: str) -> NameAndNumber | None:
        return next((item for item in items if item["name"] == target), None)
    name_and_number = get_by_name(nameAndNumberList, label)
    if name_and_number is not None:
        number = name_and_number["number"] + 1
        name_and_number["number"] = number
    else:
        nameAndNumberList.append({"name": label, "number": number})   
    node.name = f"{label}.{str(number)}"
    node_data = {
        "name": f"{label}.{str(number)}",
        "index": node_index,
        "dimensions": None,
        "children": []
    }

    if node.mesh is not None:
        if node.mesh not in mesh_cache:
            mesh_cache[node.mesh] = get_mesh_dimensions(
                gltf, node.mesh, buffer_cache
            )

        dims = mesh_cache[node.mesh]
        node_data["dimensions"] = {
            "x": round(dims[0], 4),
            "y": round(dims[1], 4),
            "z": round(dims[2], 4),
        }

    if node.children:
        for child_idx in node.children:
            node_data["children"].append(
                build_node_hierarchy(gltf, buffer_cache, child_idx, mesh_cache, nameAndNumberList)
            )

    return node_data


# ------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------

async def return_gltf_hierarchy(gltf_path):
    gltf_dir = os.path.dirname(gltf_path)
    gltf = GLTF2().load(gltf_path)
    nameAndNumberList = await name_and_number_query()

    buffer_cache = preload_buffers(gltf, gltf_dir)
    mesh_cache = {}

    scenes_data = []

    for scene_index, scene in enumerate(gltf.scenes):
        scene_data = {
            "scene_index": scene_index,
            "nodes": []
        }

        for root_node_idx in scene.nodes:
            scene_data["nodes"].append(
                build_node_hierarchy(
                    gltf,
                    buffer_cache,
                    root_node_idx,
                    mesh_cache,
                    nameAndNumberList
                )
            )

        scenes_data.append(scene_data)

    gltf.save(gltf_path) 

    return scenes_data
