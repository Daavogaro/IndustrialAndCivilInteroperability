import { StatusString } from "../../../../../components/Sidebar/MessagePanel";
import { fetchQuery } from "../../../../../utils/fetchQuery";
import { buildTree, TreeNode } from "../../buildTree";
export type UpdateButtonsProps = {
  setTree: (tree: TreeNode[]) => void;
  setMessage: (message: { status: StatusString; text: string }) => void;
};

export async function refreshStepHierarchy(
  setTree: (tree: TreeNode[]) => void,
  setMessage: (message: { status: StatusString; text: string }) => void,
) {
  const graphName = "http://localhost:8890/Elettra2/";
  const queryRootElement = `
    PREFIX x3d:  <https://www.web3d.org/specifications/X3dOntology4.0#>
    SELECT ?root ?cadType ?metadata ?visible ?display ?dimensions ?attrib ?fileUrl
    FROM <${graphName}>
    WHERE {
      ?root a x3d:CADAssembly .
      ?root a ?cadType .
      ?root x3d:hasMetadata ?metadata .
      OPTIONAL { ?root x3d:bboxDisplay ?display . }
      OPTIONAL { ?root x3d:bboxSize ?dimensions . }
      OPTIONAL { ?root x3d:attrib ?attrib . }
      OPTIONAL { ?root x3d:visible ?visible . }.
      OPTIONAL {
      ?root x3d:hasParentX3D ?urlObject .
      ?urlObject x3d:url ?fileUrl .
      }
      FILTER NOT EXISTS {
        ?root x3d:hasParentCADPart ?p .
      }
        FILTER(STRSTARTS(STR(?cadType), "https://www.web3d.org/specifications/X3dOntology4.0#"))
    }

    `;

  const queryChildren = `
    PREFIX x3d:  <https://www.web3d.org/specifications/X3dOntology4.0#>
    SELECT ?parent ?child ?cadType ?metadata ?visible ?display ?dimensions ?attrib ?fileUrl
    FROM <${graphName}>
    WHERE {
      ?child x3d:hasParentCADPart ?parent .
      ?child a ?cadType .
      ?child x3d:hasMetadata ?metadata .
      OPTIONAL { ?child x3d:visible ?visible . }.
      OPTIONAL { ?child x3d:bboxDisplay ?display . }
      OPTIONAL { ?child x3d:bboxSize ?dimensions . }
      OPTIONAL { ?child x3d:attrib ?attrib . }
      OPTIONAL {
      ?child x3d:hasParentX3D ?urlObject .
      ?urlObject x3d:url ?fileUrl .
      }
      FILTER(STRSTARTS(STR(?cadType), "https://www.web3d.org/specifications/X3dOntology4.0#"))
    }

    `;

  const ifcQuery = `
    PREFIX x3d:  <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX ifc: <https://standards.buildingsmart.org/IFC/DEV/IFC4/ADD2_TC1/OWL#>
    PREFIX express: <https://w3id.org/express#>
    SELECT ?node ?ifcClass ?gidValue ?predefinedType ?userdefinedType
    FROM <${graphName}>
    WHERE {
      ?node a ?ifcClass .
      ?node x3d:hasMetadata ?metadata .
      ?node ifc:globalId_IfcRoot ?globalId .
      ?globalId rdf:value ?gidValue .
      OPTIONAL {
      ?node ?p ?predefinedType .}
      OPTIONAL {
      ?node ifc:objectType_IfcObject ?label .
      ?label rdf:value ?userdefinedType .}

      FILTER(STRSTARTS(STR(?ifcClass), "https://standards.buildingsmart.org/IFC/DEV/IFC4/ADD2_TC1/OWL#"))
      FILTER(STRSTARTS(STR(?p), "https://standards.buildingsmart.org/IFC/DEV/IFC4/ADD2_TC1/OWL#predefinedType_"))



    }
    `;

  try {
    // fetch roots
    const rootData = await fetchQuery(queryRootElement);

    const roots = rootData.map((r: any) => ({
      uri: r.root,
      attrib: r.attrib,
      visible: r.visible,
      display: r.display,
      dimensions: r.dimensions,
      cadType: r.cadType,
      metadata: r.metadata,
      fileUrl: r.fileUrl,
    }));

    // fetch edges
    const edgeData = await fetchQuery(queryChildren);
    const edges = edgeData.map((e: any) => ({
      parent: e.parent,
      child: e.child,
      cadType: e.cadType,
      metadata: e.metadata,
      visible: e.visible,
      display: e.display,
      dimensions: e.dimensions,
      attrib: e.attrib,
      fileUrl: e.fileUrl,
    }));
    const ifcData = await fetchQuery(ifcQuery);
    const ifcs = ifcData.map((i: any) => ({
      node: i.node,
      ifcClass: i.ifcClass,
      predefinedType: i.predefinedType,
      userdefinedType: i.userdefinedType,
    }));

    // build tree
    const hierarchy = buildTree(edges, roots, ifcs);
    setTree(hierarchy);
    setMessage({
      status: "success",
      text: "Hierarchy updated",
    });
  } catch (err) {
    console.error("Hierarchy build failed", err);
    setMessage({
      status: "error",
      text: "Failed to build hierarchy",
    });
  }
}

export function UpdateHierarchyButton({
  setTree,
  setMessage,
}: UpdateButtonsProps) {
  const buildHierarchy = async () => {
    await refreshStepHierarchy(setTree, setMessage);
  };
  return (
    <span
      className="generalButton material-icons-round"
      style={{}}
      onClick={buildHierarchy}>
      refresh
    </span>
  );
}
