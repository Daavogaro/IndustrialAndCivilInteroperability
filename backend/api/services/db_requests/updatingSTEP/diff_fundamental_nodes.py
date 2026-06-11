"""Diff fundamental-node assemblies between the old (DB) and new (re-imported)
versions of a STEP file, and write/propagate the obsolescence markers.

A *fundamental node* is a node carrying ``x3d:attrib "Fundamental_Node"``. Its
*assembly* is the set of ``x3d:children`` descendants, pruned so that traversal
stops at (but still includes) any descendant that is itself a fundamental node
— i.e. the hierarchy *under* nested fundamental nodes is excluded.

The STEP update pipeline (``gltf_update_STEP.build_node_hierarchy``) reuses the
existing instance numbers for matching metadata labels, so after re-import the
``label.N`` instance names are stable for nodes that persist. That means a plain
set-difference of instance names within a fundamental node's boundary yields
exactly the added/removed entities — which is the "compare by pattern, ignore
the raw instance number" semantics the feature requires.
"""

import requests
from pydantic import BaseModel

from ....models.models import GRAPH_NAMESPACE, VIRTUOSO_URL
from ....routes.sparql_query import sparql_query
from ....routes.projects import _read_projects

X3D = "https://www.web3d.org/specifications/X3dOntology4.0#"
IFC = "https://w3id.org/ifc/IFC4X3_ADD2#"


class SparqlRequest(BaseModel):
    query: str


def _escape_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _label_of(full_name: str) -> str:
    """``"Label.3" -> "Label"``; the trailing ``.N`` instance number is dropped.

    Labels may themselves contain dots (``"Foo.Bar.3"`` -> ``"Foo.Bar"``); only
    the last segment is the instance number.
    """
    return full_name.rsplit(".", 1)[0] if "." in full_name else full_name


def _post_update(query: str) -> None:
    requests.post(
        VIRTUOSO_URL,
        data={"update": query},
        headers={"Accept": "application/sparql-results+json"},
    )


def _build_fundamental_sets(nodes: dict, children: dict) -> dict:
    """Given a flat node map and a parent->children map, return, for every
    fundamental node instance, its boundary descendant name-set.

    Returns ``{ fund_full_name: {"metadata": uri, "names": set[label.N]} }``.
    """
    result: dict = {}
    for uri, info in nodes.items():
        if not info["is_fundamental"]:
            continue
        names: set[str] = set()
        stack = list(children.get(uri, []))
        while stack:
            child_uri = stack.pop()
            child_info = nodes.get(child_uri)
            if child_info is None:
                continue
            names.add(child_info["full_name"])
            if child_info["is_fundamental"]:
                # boundary: include the nested fundamental node, but do not
                # descend into its own subtree.
                continue
            stack.extend(children.get(child_uri, []))
        result[info["full_name"]] = {
            "metadata": info["metadata"],
            "names": names,
        }
    return result


async def snapshot_file_fundamentals(graph: str, file_url: str) -> tuple[dict, set]:
    """Snapshot the current (pre-update) fundamental-node assemblies for a file.

    ``file_url`` is the on-disk gltf path; the File node stores it as
    ``file:///<path-with-forward-slashes>`` (see ``RDF_conversion``).

    Returns ``(fundamentals, all_names)`` where ``fundamentals`` is keyed by
    fundamental instance name (see ``_build_fundamental_sets``) and ``all_names``
    is the set of every ``label.N`` node name in the file before the update —
    used by the re-import to skip nodes that persist.
    """
    safe = (file_url or "").replace("\\", "/")
    query = f"""
    PREFIX x3d: <{X3D}>
    PREFIX pre: <http://www.loc.gov/premis/rdf/v3/>
    SELECT ?node ?metadata ?attrib ?parent
    FROM <{graph}>
    WHERE {{
      ?node x3d:hasParentX3D ?file .
      ?file pre:storedAt ?url .
      ?node x3d:hasMetadata ?metadata .
      OPTIONAL {{ ?node x3d:attrib ?attrib . }}
      OPTIONAL {{ ?node x3d:hasParentCADPart ?parent . }}
      FILTER(STR(?url) = "file:///{safe}")
    }}
    """
    result = await sparql_query(request=SparqlRequest(query=query))
    bindings = result.get("results", {}).get("bindings", [])

    nodes: dict = {}
    children: dict = {}
    for b in bindings:
        uri = b["node"]["value"]
        info = nodes.get(uri)
        if info is None:
            info = {
                "full_name": uri.split("#")[-1],
                "metadata": b["metadata"]["value"],
                "is_fundamental": False,
                "parent": None,
            }
            nodes[uri] = info
        if b.get("attrib", {}).get("value") == "Fundamental_Node":
            info["is_fundamental"] = True
        parent = b.get("parent", {}).get("value")
        if parent and info["parent"] is None:
            info["parent"] = parent

    for uri, info in nodes.items():
        parent = info["parent"]
        if parent is not None:
            children.setdefault(parent, []).append(uri)

    all_names = {info["full_name"] for info in nodes.values()}
    return _build_fundamental_sets(nodes, children), all_names


def build_new_fundamentals(hierarchy: list, existing_nodes: list) -> dict:
    """Build the per-fundamental boundary name-sets from the freshly parsed
    ``GeometryNode`` hierarchy. Fundamental status of a label comes from
    ``existing_nodes`` (its ``attrib`` is ``"Fundamental_Node"``).

    Returns ``{ fund_full_name: {"metadata": uri, "names": set[label.N]} }``.
    """
    attrib_by_label: dict = {}
    for node in existing_nodes:
        attrib = node.get("attrib")
        if attrib:
            attrib_by_label[node["name"]] = attrib

    def is_fundamental(full_name: str) -> bool:
        return attrib_by_label.get(_label_of(full_name)) == "Fundamental_Node"

    result: dict = {}

    def collect(node, target: set) -> None:
        for child in node.children:
            target.add(child.name)
            if is_fundamental(child.name):
                continue
            collect(child, target)

    def walk(node) -> None:
        if is_fundamental(node.name):
            names: set[str] = set()
            collect(node, names)
            result[node.name] = {
                "metadata": str(GRAPH_NAMESPACE[_label_of(node.name)]),
                "names": names,
            }
        for child in node.children:
            walk(child)

    for root in hierarchy:
        walk(root)
    return result


def diff_fundamentals(old: dict, new: dict) -> list:
    """Compare old vs new boundary sets (matched per fundamental instance by
    its ``label.N`` name) and aggregate to product (metadata) level.

    Returns a list of ``{"label", "metadata", "added": [..], "removed": [..]}``
    — one entry per changed product. A product is changed iff at least one of
    its instances gained or lost an entity.
    """
    changed: dict = {}
    for fund_name, new_info in new.items():
        old_info = old.get(fund_name)
        if old_info is None:
            # Brand-new fundamental instance — not a change to an existing
            # product, so it is not flagged as obsolete.
            continue
        added = new_info["names"] - old_info["names"]
        removed = old_info["names"] - new_info["names"]
        if not added and not removed:
            continue
        label = _label_of(fund_name)
        entry = changed.get(label)
        if entry is None:
            entry = {
                "label": label,
                "metadata": new_info["metadata"],
                "added": set(),
                "removed": set(),
            }
            changed[label] = entry
        entry["added"] |= added
        entry["removed"] |= removed

    return [
        {
            "label": entry["label"],
            "metadata": entry["metadata"],
            "added": sorted(entry["added"]),
            "removed": sorted(entry["removed"]),
        }
        for entry in changed.values()
    ]


def drop_changed_fundamental_ifc(graph: str, file_url: str, changed_labels) -> None:
    """Delete the IFC metadata of the changed fundamental nodes *in this file*.

    Other files keep their IFC; only the just-updated file's instances of the
    changed products lose their IFC class / property sets so they must be
    re-entered. Blocking — run via ``run_in_threadpool``.
    """
    safe = (file_url or "").replace("\\", "/")
    for label in changed_labels:
        metadata = str(GRAPH_NAMESPACE[label])
        type_query = f"""
        PREFIX x3d: <{X3D}>
        PREFIX pre: <http://www.loc.gov/premis/rdf/v3/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        DELETE {{ GRAPH <{graph}> {{ ?s rdf:type ?c . }} }}
        WHERE {{
          GRAPH <{graph}> {{
            ?s x3d:hasMetadata <{metadata}> .
            ?s x3d:attrib "Fundamental_Node" .
            ?s x3d:hasParentX3D ?f . ?f pre:storedAt ?url .
            ?s rdf:type ?c .
            FILTER(STRSTARTS(STR(?c), "{IFC}"))
            FILTER(STR(?url) = "file:///{safe}")
          }}
        }}
        """
        prop_query = f"""
        PREFIX x3d: <{X3D}>
        PREFIX pre: <http://www.loc.gov/premis/rdf/v3/>
        DELETE {{ GRAPH <{graph}> {{ ?s ?p ?o . }} }}
        WHERE {{
          GRAPH <{graph}> {{
            ?s x3d:hasMetadata <{metadata}> .
            ?s x3d:attrib "Fundamental_Node" .
            ?s x3d:hasParentX3D ?f . ?f pre:storedAt ?url .
            ?s ?p ?o .
            FILTER(STRSTARTS(STR(?p), "{IFC}"))
            FILTER(STR(?url) = "file:///{safe}")
          }}
        }}
        """
        _post_update(type_query)
        _post_update(prop_query)


def write_and_propagate_markers(diff: list, source_graph: str) -> None:
    """Write ``x3d:hasRemovedEntities`` / ``x3d:hasAddedEntities`` markers on
    every fundamental-node instance of each changed product, across **all**
    known project graphs (idempotent). This single uniform loop covers both the
    source file's instances and the cross-file / cross-project propagation.

    Blocking — run via ``run_in_threadpool``.
    """
    if not diff:
        return

    try:
        graphs = [p["graphUri"] for p in _read_projects()]
    except Exception:
        graphs = [source_graph]
    if source_graph not in graphs:
        graphs.append(source_graph)

    for entry in diff:
        metadata = entry["metadata"]
        triples = []
        for name in entry["removed"]:
            triples.append(f'?s x3d:hasRemovedEntities "{_escape_literal(name)}"^^xsd:string .')
        for name in entry["added"]:
            triples.append(f'?s x3d:hasAddedEntities "{_escape_literal(name)}"^^xsd:string .')
        if not triples:
            continue
        insert_block = "\n            ".join(triples)
        for graph in graphs:
            query = f"""
            PREFIX x3d: <{X3D}>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            INSERT {{ GRAPH <{graph}> {{
            {insert_block}
            }} }}
            WHERE {{
              GRAPH <{graph}> {{
                ?s x3d:hasMetadata <{metadata}> .
                ?s x3d:attrib "Fundamental_Node" .
              }}
            }}
            """
            _post_update(query)
