from dataclasses import dataclass
from pathlib import Path
import re
import numpy as np
from OCC.Core.BRep import BRep_Tool
from OCC.Core import BRepTools
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.ShapeFix import ShapeFix_Shape
from OCC.Core.TDF import TDF_Label, TDF_LabelSequence
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import topods
from OCC.Core.XCAFDoc import XCAFDoc_ColorTool, XCAFDoc_DocumentTool
from pygltflib import (
    GLTF2, Accessor, Asset, Buffer, BufferView, FLOAT, Material, Mesh, Node,
    PbrMetallicRoughness, Primitive, Scene, UNSIGNED_INT,
)

@dataclass
class PartMesh:
    name: str
    color: tuple[float, float, float, float]
    vertices: np.ndarray
    indices: np.ndarray

@dataclass
class AssemblyNode:
    name: str
    mesh: PartMesh | None
    children: list["AssemblyNode"]
    transform: list[float] | None = None


@dataclass
class XcafContext:
    doc: TDocStd_Document
    shape_tool: object
    color_tool: object

def extract_rgba(quantity_color_obj):
    default = (0.8, 0.8, 0.8, 1.0)
    if quantity_color_obj is None: return default
    try: return (float(quantity_color_obj.Red()), float(quantity_color_obj.Green()), float(quantity_color_obj.Blue()), 1.0)
    except Exception: return default

def triangulate_shape(shape, deflection: float, unit_scale: float):
    fixer = ShapeFix_Shape(shape)
    fixer.Perform()
    shape = fixer.Shape()
    BRepTools.breptools.Clean(shape)
    # Use stricter angular deflection and ensure meshing is performed.
    mesher = BRepMesh_IncrementalMesh(shape, deflection, False, 0.2, True)
    mesher.Perform()
    vertices, indices = [], []
    vertex_offset = 0
    skipped_faces = 0
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = topods.Face(exp.Current())
        loc = face.Location()
        triangulation = BRep_Tool.Triangulation(face, loc)
        if triangulation is None:
            # Some STEP faces are not triangulated at shape-level meshing pass.
            # Retry directly on the face before giving up.
            face_mesher = BRepMesh_IncrementalMesh(face, deflection, False, 0.2, True)
            face_mesher.Perform()
            triangulation = BRep_Tool.Triangulation(face, loc)
            if triangulation is None:
                skipped_faces += 1
                exp.Next()
                continue
        trsf = loc.Transformation()
        for i in range(1, triangulation.NbNodes() + 1):
            pnt = triangulation.Node(i).Transformed(trsf)
            vertices.append([pnt.X() * unit_scale, pnt.Y() * unit_scale, pnt.Z() * unit_scale])
        for i in range(1, triangulation.NbTriangles() + 1):
            tri = triangulation.Triangle(i)
            i1, i2, i3 = tri.Get()
            # Keep winding coherent for reversed faces.
            if face.Orientation() == TopAbs_REVERSED:
                i2, i3 = i3, i2
            indices.append([vertex_offset + i1 - 1, vertex_offset + i2 - 1, vertex_offset + i3 - 1])
        vertex_offset += triangulation.NbNodes()
        exp.Next()
    if skipped_faces:
        print(f"[WARN] Skipped {skipped_faces} untriangulated face(s).")
    if not vertices or not indices: return None, None
    return np.asarray(vertices, dtype=np.float32), np.asarray(indices, dtype=np.uint32).reshape(-1)

def load_xcaf(step_path: str):
    doc = TDocStd_Document("pythonocc-hierarchy-step-import")
    shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool(doc.Main())
    step_reader = STEPCAFControl_Reader()
    step_reader.SetColorMode(True)
    step_reader.SetLayerMode(True)
    step_reader.SetNameMode(True)
    step_reader.SetMatMode(True)
    step_reader.SetGDTMode(True)
    status = step_reader.ReadFile(step_path)
    if status != IFSelect_RetDone: raise RuntimeError(f"Cannot read STEP file: {step_path}")
    if not step_reader.Transfer(doc): raise RuntimeError(f"STEP transfer failed: {step_path}")
    return XcafContext(doc=doc, shape_tool=shape_tool, color_tool=color_tool)

def label_name(label, fallback: str):
    name = label.GetLabelName()
    return name if name else fallback


def sanitize_node_name(name: str):
    if not name:
        return "unnamed"

    # Keep the last ".suffix" untouched and sanitize everything before it.
    head, tail = (name.rsplit(".", 1) + [None])[:2] if "." in name else (name, None)
    safe_head = re.sub(r"[^A-Za-z0-9]", "_", head)
    safe_head = re.sub(r"_+", "_", safe_head)
    if not safe_head:
        safe_head = "unnamed"

    if tail is None:
        return safe_head
    return f"{safe_head}.{tail}"

def resolve_color(shape, label, color_tool):
    color = Quantity_Color(0.8, 0.8, 0.8, Quantity_TOC_RGB)
    if color_tool.GetInstanceColor(shape, 0, color) or color_tool.GetInstanceColor(shape, 1, color) or color_tool.GetInstanceColor(shape, 2, color):
        return color
    if XCAFDoc_ColorTool.GetColor(label, 0, color) or XCAFDoc_ColorTool.GetColor(label, 1, color) or XCAFDoc_ColorTool.GetColor(label, 2, color):
        return color
    return None

def compose_location(loc_stack):
    merged = TopLoc_Location()
    for loc in loc_stack: merged = merged.Multiplied(loc)
    return merged


def location_to_matrix(location, unit_scale: float):
    trsf = location.Transformation()
    translation = trsf.TranslationPart()
    return [
        trsf.Value(1, 1), trsf.Value(2, 1), trsf.Value(3, 1), 0.0,
        trsf.Value(1, 2), trsf.Value(2, 2), trsf.Value(3, 2), 0.0,
        trsf.Value(1, 3), trsf.Value(2, 3), trsf.Value(3, 3), 0.0,
        translation.X() * unit_scale,
        translation.Y() * unit_scale,
        translation.Z() * unit_scale,
        1.0,
    ]


def compose_matrices(parent_matrix, child_matrix):
    if parent_matrix is None:
        return child_matrix
    if child_matrix is None:
        return parent_matrix
    parent = np.asarray(parent_matrix, dtype=np.float64).reshape((4, 4), order="F")
    child = np.asarray(child_matrix, dtype=np.float64).reshape((4, 4), order="F")
    return (parent @ child).reshape(-1, order="F").tolist()


def decode_step_string(value: str):
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        value = value[1:-1]
    value = value.replace("''", "'")

    def repl(match):
        hex_blob = match.group(1)
        chars = []
        for i in range(0, len(hex_blob), 4):
            chunk = hex_blob[i:i + 4]
            if len(chunk) == 4:
                try:
                    chars.append(chr(int(chunk, 16)))
                except ValueError:
                    return match.group(0)
        return "".join(chars)

    return re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\", repl, value)


def split_step_args(arg_text: str):
    args = []
    token = []
    depth = 0
    in_string = False
    i = 0
    while i < len(arg_text):
        ch = arg_text[i]
        if in_string:
            token.append(ch)
            if ch == "'":
                if i + 1 < len(arg_text) and arg_text[i + 1] == "'":
                    token.append("'")
                    i += 1
                else:
                    in_string = False
        else:
            if ch == "'":
                in_string = True
                token.append(ch)
            elif ch == "(":
                depth += 1
                token.append(ch)
            elif ch == ")":
                depth -= 1
                token.append(ch)
            elif ch == "," and depth == 0:
                args.append("".join(token).strip())
                token = []
            else:
                token.append(ch)
        i += 1
    if token:
        args.append("".join(token).strip())
    return args


def parse_ref(token: str):
    m = re.match(r"#(\d+)$", token.strip())
    return int(m.group(1)) if m else None


def parse_ref_list(token: str):
    return [int(m.group(1)) for m in re.finditer(r"#(\d+)", token)]


def extract_step_entity_signature(rhs: str):
    rhs = rhs.strip()

    m = re.match(r"\s*([A-Z0-9_]+)\s*\(", rhs, flags=re.DOTALL)
    if not m:
        m = re.match(r"\(\s*([A-Z0-9_]+)\s*\(", rhs, flags=re.DOTALL)
    if not m:
        return None, None

    etype = m.group(1)
    start = m.end()
    depth = 1
    in_string = False
    i = start

    while i < len(rhs):
        ch = rhs[i]
        if in_string:
            if ch == "'":
                if i + 1 < len(rhs) and rhs[i + 1] == "'":
                    i += 1
                else:
                    in_string = False
        else:
            if ch == "'":
                in_string = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return etype, rhs[start:i]
        i += 1

    return None, None


def build_nauo_manifold_map(step_path: str):
    try:
        with open(step_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except OSError:
        return {}

    entities = {}
    in_string = False
    chunk = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        chunk.append(ch)
        if in_string:
            if ch == "'":
                if i + 1 < len(raw) and raw[i + 1] == "'":
                    chunk.append(raw[i + 1])
                    i += 1
                else:
                    in_string = False
        else:
            if ch == "'":
                in_string = True
            elif ch == ";":
                statement = "".join(chunk).strip()
                chunk = []
                m = re.match(r"#(\d+)\s*=\s*(.+);$", statement, flags=re.DOTALL)
                if m:
                    entities[int(m.group(1))] = m.group(2).strip()
        i += 1

    entity_type_by_id = {}
    nauo_id_by_entity = {}
    pds_target_ref = {}
    rr_ids_by_pds = {}
    rep1_by_rr = {}
    item_ids_by_rep = {}

    for eid, rhs in entities.items():
        etype, arg_text = extract_step_entity_signature(rhs)
        if not etype:
            continue
        entity_type_by_id[eid] = etype
        args = split_step_args(arg_text)

        if etype == "NEXT_ASSEMBLY_USAGE_OCCURRENCE" and len(args) >= 1:
            nauo_id = decode_step_string(args[0])
            nauo_id_by_entity[eid] = nauo_id

        elif etype == "PRODUCT_DEFINITION_SHAPE" and len(args) >= 3:
            target_ref = parse_ref(args[2])
            if target_ref is not None:
                pds_target_ref[eid] = target_ref

        elif etype == "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION":
            rr_ref = parse_ref(args[0]) if len(args) >= 1 else None
            pds_ref = parse_ref(args[1]) if len(args) >= 2 else None
            if rr_ref is None or pds_ref is None:
                refs = []
                for token in args:
                    refs.extend(parse_ref_list(token))
                if len(refs) >= 2:
                    rr_ref = refs[0]
                    pds_ref = refs[1]
            if rr_ref is not None and pds_ref is not None:
                rr_ids_by_pds.setdefault(pds_ref, []).append(rr_ref)

        elif etype == "REPRESENTATION_RELATIONSHIP":
            rep1_ref = parse_ref(args[2]) if len(args) >= 3 else None
            if rep1_ref is None:
                refs = []
                for token in args:
                    refs.extend(parse_ref_list(token))
                if refs:
                    rep1_ref = refs[0]
            if rep1_ref is not None:
                rep1_by_rr[eid] = rep1_ref

        elif etype.endswith("SHAPE_REPRESENTATION") and len(args) >= 2:
            item_ids_by_rep[eid] = parse_ref_list(args[1])

    nauo_to_manifold_items = {}
    seen_by_nauo = {}
    for pds_id, target_ref in pds_target_ref.items():
        nauo_id = nauo_id_by_entity.get(target_ref)
        if not nauo_id:
            continue
        manifold_item_ids = nauo_to_manifold_items.setdefault(nauo_id, [])
        seen = seen_by_nauo.setdefault(nauo_id, set())
        for rr_id in rr_ids_by_pds.get(pds_id, []):
            rep1_id = rep1_by_rr.get(rr_id)
            if rep1_id is None:
                continue
            item_ids = item_ids_by_rep.get(rep1_id, [])
            for item_id in item_ids:
                if entity_type_by_id.get(item_id) != "MANIFOLD_SOLID_BREP":
                    continue
                if item_id in seen:
                    continue
                seen.add(item_id)
                manifold_item_ids.append(item_id)

    return nauo_to_manifold_items

def build_assembly_tree(shape_tool, color_tool, step_path: str, deflection: float, unit_scale: float):
    label_seq = TDF_LabelSequence()
    shape_tool.GetFreeShapes(label_seq)
    nauo_to_manifold_items = build_nauo_manifold_map(step_path)

    auto_name_counter = {"value": 0}

    def unique_name(prefix: str):
        auto_name_counter["value"] += 1
        return f"{prefix}_{auto_name_counter['value']}"

    def transform_from_label(label):
        local_loc = shape_tool.GetLocation(label)
        if local_loc.IsIdentity():
            return None
        return location_to_matrix(local_loc, unit_scale)

    def manifold_candidate_shapes(shape):
        solids = []
        exp = TopExp_Explorer(shape, TopAbs_SOLID)
        while exp.More():
            solids.append(topods.Solid(exp.Current()))
            exp.Next()
        return solids

    def make_mesh_node(shape, label, fallback_name: str, fallback_color=None, transform_override=None):
        color = resolve_color(shape, label, color_tool) if label is not None else None
        color = color or fallback_color
        vertices, indices = triangulate_shape(shape, deflection, unit_scale)
        if vertices is None:
            return None
        mesh = PartMesh(
            name=sanitize_node_name(fallback_name),
            color=extract_rgba(color),
            vertices=vertices,
            indices=indices,
        )
        if transform_override is not None:
            node_transform = transform_override
        elif label is not None:
            node_transform = transform_from_label(label)
        else:
            node_transform = None
        return AssemblyNode(name=mesh.name, mesh=mesh, children=[], transform=node_transform)

    def visit(label):
        if shape_tool.IsReference(label):
            referred = TDF_Label()
            shape_tool.GetReferredShape(label, referred)
            raw_instance_id = label_name(label, unique_name("reference"))
            instance_id = sanitize_node_name(raw_instance_id)
            mapped_manifold_items = nauo_to_manifold_items.get(raw_instance_id)
            node_transform = transform_from_label(label)

            if mapped_manifold_items:
                referred_shape = shape_tool.GetShape(referred)
                referred_color = resolve_color(referred_shape, referred, color_tool)
                manifold_shapes = manifold_candidate_shapes(referred_shape)

                if len(mapped_manifold_items) == 1:
                    target_shape = manifold_shapes[0] if manifold_shapes else referred_shape
                    mesh_node = make_mesh_node(
                        target_shape,
                        referred,
                        fallback_name=raw_instance_id,
                        fallback_color=referred_color,
                    )
                    if mesh_node:
                        mesh_node.name = instance_id
                        if mesh_node.mesh:
                            mesh_node.mesh.name = instance_id
                        mesh_node.transform = compose_matrices(node_transform, mesh_node.transform)
                        return mesh_node
                    return AssemblyNode(name=instance_id, mesh=None, children=[], transform=node_transform)

                children = []
                child_base_name = instance_id.replace(".", "_")
                pair_count = min(len(mapped_manifold_items), len(manifold_shapes))
                if pair_count != len(mapped_manifold_items):
                    print(
                        f"[WARN] NAUO {raw_instance_id}: expected {len(mapped_manifold_items)} manifold solids, "
                        f"found {len(manifold_shapes)} solid shape(s)."
                    )
                for i in range(1, pair_count + 1):
                    child_name = f"{child_base_name}_{i}"
                    child_mesh = make_mesh_node(
                        manifold_shapes[i - 1],
                        None,
                        fallback_name=child_name,
                        fallback_color=referred_color,
                    )
                    if child_mesh:
                        child_mesh.name = child_name
                        if child_mesh.mesh:
                            child_mesh.mesh.name = child_name
                        children.append(child_mesh)

                if children:
                    return AssemblyNode(name=instance_id, mesh=None, children=children, transform=node_transform)

                mesh_node = make_mesh_node(
                    referred_shape,
                    referred,
                    fallback_name=raw_instance_id,
                    fallback_color=referred_color,
                )
                if mesh_node:
                    mesh_node.name = instance_id
                    if mesh_node.mesh:
                        mesh_node.mesh.name = instance_id
                    mesh_node.transform = compose_matrices(node_transform, mesh_node.transform)
                    return mesh_node

                return AssemblyNode(name=instance_id, mesh=None, children=[], transform=node_transform)

            referred_node = visit(referred)
            if referred_node:
                referred_node.transform = compose_matrices(node_transform, referred_node.transform)
                referred_node.name = instance_id
                if referred_node.mesh:
                    referred_node.mesh.name = instance_id
                return referred_node
            return AssemblyNode(name=instance_id, mesh=None, children=[], transform=node_transform)
        if shape_tool.IsAssembly(label):
            node = AssemblyNode(
                name=sanitize_node_name(label_name(label, unique_name("assembly"))),
                mesh=None,
                children=[],
                transform=transform_from_label(label),
            )
            components = TDF_LabelSequence()
            shape_tool.GetComponents(label, components)
            for i in range(1, components.Length() + 1):
                child_node = visit(components.Value(i))
                if child_node: node.children.append(child_node)
            return node
        if shape_tool.IsSimpleShape(label) or shape_tool.IsShape(label):
            shape = shape_tool.GetShape(label)
            parent_name = sanitize_node_name(label_name(label, unique_name("part")))
            parent_color = resolve_color(shape, label, color_tool)
            return make_mesh_node(
                shape,
                label,
                fallback_name=parent_name,
                fallback_color=parent_color,
            )
        return None
    roots = []
    for i in range(1, label_seq.Length() + 1):
        root_node = visit(label_seq.Value(i))
        if root_node: roots.append(root_node)
    return roots

# Rotate -90° around X to convert Z-up (STEP/CAD) → Y-up (glTF/Three.js).
# Column-major order: col0=[1,0,0,0], col1=[0,0,-1,0], col2=[0,1,0,0], col3=[0,0,0,1]
_ZUP_TO_YUP = [1, 0, 0, 0,  0, 0, -1, 0,  0, 1, 0, 0,  0, 0, 0, 1]

def export_gltf(step_path: str, output_path: str, deflection: float = 0.01, unit_scale: float = 0.001) -> str:
    xcaf = load_xcaf(step_path)
    assembly_roots = build_assembly_tree(xcaf.shape_tool, xcaf.color_tool, step_path, deflection, unit_scale)
    if not assembly_roots: raise RuntimeError("No triangulated geometry was extracted.")
    for root in assembly_roots:
        root.transform = compose_matrices(_ZUP_TO_YUP, root.transform)
    gltf = GLTF2(asset=Asset(version="2.0"), scene=0, scenes=[Scene(nodes=[])], nodes=[], meshes=[], materials=[], accessors=[], bufferViews=[], buffers=[Buffer(byteLength=0)])
    binary_blob, material_by_color = bytearray(), {}
    def append_mesh(part):
        color_key = tuple(round(c, 6) for c in part.color)
        if color_key not in material_by_color:
            gltf.materials.append(Material(pbrMetallicRoughness=PbrMetallicRoughness(baseColorFactor=list(part.color), metallicFactor=0.0, roughnessFactor=0.7), doubleSided=True))
            material_by_color[color_key] = len(gltf.materials) - 1
        v_bytes, i_bytes = part.vertices.tobytes(), part.indices.tobytes()
        def add_view(data, target):
            offset = len(binary_blob)
            binary_blob.extend(data)
            while len(binary_blob) % 4 != 0: binary_blob.append(0)
            gltf.bufferViews.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(data), target=target))
            return len(gltf.bufferViews) - 1
        v_view, i_view = add_view(v_bytes, 34962), add_view(i_bytes, 34963)
        gltf.accessors.append(Accessor(bufferView=v_view, componentType=FLOAT, count=len(part.vertices), type="VEC3", max=part.vertices.max(axis=0).tolist(), min=part.vertices.min(axis=0).tolist()))
        v_acc = len(gltf.accessors) - 1
        gltf.accessors.append(Accessor(bufferView=i_view, componentType=UNSIGNED_INT, count=len(part.indices), type="SCALAR"))
        i_acc = len(gltf.accessors) - 1
        gltf.meshes.append(Mesh(name=part.name, primitives=[Primitive(attributes={"POSITION": v_acc}, indices=i_acc, material=material_by_color[color_key])]))
        return len(gltf.meshes) - 1
    def add_node_recursive(tree_node):
        m_idx = append_mesh(tree_node.mesh) if tree_node.mesh else None
        gltf_node = Node(name=tree_node.name, mesh=m_idx, children=[], matrix=tree_node.transform)
        gltf.nodes.append(gltf_node)
        curr_idx = len(gltf.nodes) - 1
        if tree_node.children:
            for child in tree_node.children: gltf_node.children.append(add_node_recursive(child))
        if not gltf_node.children: gltf_node.children = None
        return curr_idx
    for root in assembly_roots: gltf.scenes[0].nodes.append(add_node_recursive(root))
    output_file = Path(output_path)
    if output_file.suffix.lower() != ".gltf":
        output_file = output_file.with_suffix(".gltf")
    bin_file = output_file.with_suffix(".bin")

    gltf.buffers[0].byteLength = len(binary_blob)
    gltf.buffers[0].uri = bin_file.name
    with open(bin_file, "wb") as f:
        f.write(binary_blob)
    gltf.save_json(str(output_file))
    return str(output_file)
