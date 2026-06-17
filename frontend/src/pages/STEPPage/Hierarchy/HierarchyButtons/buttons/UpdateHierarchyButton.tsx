import { StatusString } from "../../../../../components/Sidebar/MessagePanel";
import { fetchQuery } from "../../../../../utils/fetchQuery";
import { buildTree, TreeNode } from "../../buildTree";
import { useProject } from "../../../../../context/ProjectContext";

export type UpdateButtonsProps = {
  setTree: (tree: TreeNode[]) => void;
  setMessage: (message: { status: StatusString; text: string }) => void;
};

export async function refreshStepHierarchy(
  graphUri: string,
  setTree: (tree: TreeNode[]) => void,
  setMessage: (message: { status: StatusString; text: string }) => void,
) {
  const queryRootElement = `
    PREFIX x3d:  <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX pre: <http://www.loc.gov/premis/rdf/v3/>
    SELECT ?root ?cadType ?metadata ?visible ?display ?dimensions ?attrib ?fileUrl
    FROM <${graphUri}>
    WHERE {
      ?root a x3d:CADAssembly .
      ?root a ?cadType .
      ?root x3d:hasMetadata ?metadata .
      OPTIONAL { ?root x3d:bboxDisplay ?display . }
      OPTIONAL { ?root x3d:bboxSize ?dimensions . }
      OPTIONAL { ?root x3d:attrib ?attrib . }
      OPTIONAL { ?root x3d:visible ?visible . }.
      OPTIONAL {
      ?root x3d:hasParentX3D ?file .
      ?file a pre:File.
      ?file pre:storedAt ?fileUrl .
      }
      FILTER NOT EXISTS {
        ?root x3d:hasParentCADPart ?p .
      }
        FILTER(STRSTARTS(STR(?cadType), "https://www.web3d.org/specifications/X3dOntology4.0#"))
    }

    `;

  const queryChildren = `
    PREFIX x3d:  <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX pre: <http://www.loc.gov/premis/rdf/v3/>
    SELECT ?parent ?child ?cadType ?metadata ?visible ?display ?dimensions ?attrib ?fileUrl
    FROM <${graphUri}>
    WHERE {
      ?child x3d:hasParentCADPart ?parent .
      ?child a ?cadType .
      ?child x3d:hasMetadata ?metadata .
      OPTIONAL { ?child x3d:visible ?visible . }.
      OPTIONAL { ?child x3d:bboxDisplay ?display . }
      OPTIONAL { ?child x3d:bboxSize ?dimensions . }
      OPTIONAL { ?child x3d:attrib ?attrib . }
      OPTIONAL {
      ?child x3d:hasParentX3D ?file .
      ?file a pre:File .
      ?file pre:storedAt ?fileUrl .
      }
      FILTER(STRSTARTS(STR(?cadType), "https://www.web3d.org/specifications/X3dOntology4.0#"))
    }

    `;

  const ifcQuery = `
    PREFIX x3d:  <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
    PREFIX express: <https://w3id.org/express#>
    SELECT ?node ?ifcClass ?gidValue ?predefinedType ?objectType
    FROM <${graphUri}>
    WHERE {
      ?node a ?ifcClass .
      ?node x3d:hasMetadata ?metadata .
      ?node ifc:globalId_IfcRoot ?globalId .
      ?globalId rdf:value ?gidValue .
      OPTIONAL {
      ?node ?p ?predefinedType .}
      OPTIONAL {
      ?node ifc:objectType_IfcObject ?label .
      ?label rdf:value ?objectType .}

      FILTER(STRSTARTS(STR(?ifcClass), "https://w3id.org/ifc/IFC4X3_ADD2#"))
      FILTER(STRSTARTS(STR(?p), "https://w3id.org/ifc/IFC4X3_ADD2#predefinedType_"))



    }
    `;

  const ifcPsetQuery = `
  PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
    PREFIX express: <https://w3id.org/express#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?node ?psetName ?propName ?propValue ?datatype
    FROM <${graphUri}>
    WHERE {
      ?s a ifc:IfcRelDefinesByProperties .
      ?s ifc:relatedObjects_IfcRelDefinesByProperties ?node .
      ?s ifc:relatingPropertyDefinition_IfcRelDefinesByProperties ?pset .
      ?pset ifc:name_IfcRoot ?label .
      ?label express:hasString ?psetName .

      ?pset ifc:hasProperties_IfcPropertySet ?prop .
      ?prop ifc:name_IfcProperty ?identifier .
      ?identifier express:hasString ?propName .

      ?prop ifc:nominalValue_IfcPropertySingleValue ?value .
      ?value ?p ?propValue .
      ?p a owl:DatatypeProperty .
      BIND(DATATYPE(?propValue) AS ?datatype)
    }
  `;

  // IfcDistributionPort attributes, keyed back to the element node via IfcRelNests.
  const portQuery = `
    PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
    SELECT ?node ?portName ?systemType ?predefinedType ?flowDirection
    FROM <${graphUri}>
    WHERE {
      ?rel a ifc:IfcRelNests .
      ?rel ifc:relatingObject_IfcRelNests ?node .
      ?rel ifc:relatedObjects_IfcRelNests ?port .
      ?port a ifc:IfcDistributionPort .
      OPTIONAL {
        ?port ifc:name_IfcRoot ?nameLabel .
        ?nameLabel rdf:value ?portName .
      }
      OPTIONAL { ?port ifc:systemType_IfcDistributionPort ?systemType . }
      OPTIONAL { ?port ifc:predefinedType_IfcDistributionPort ?predefinedType . }
      OPTIONAL { ?port ifc:flowDirection_IfcDistributionPort ?flowDirection . }
    }
  `;

  // IfcDistributionPort property sets, keyed back to the element node via
  // IfcRelNests (the pset is defined on the port, ?node is the element).
  const portPsetQuery = `
    PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
    PREFIX express: <https://w3id.org/express#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?node ?psetName ?propName ?propValue ?datatype
    FROM <${graphUri}>
    WHERE {
      ?rel a ifc:IfcRelNests .
      ?rel ifc:relatingObject_IfcRelNests ?node .
      ?rel ifc:relatedObjects_IfcRelNests ?port .
      ?port a ifc:IfcDistributionPort .

      ?s a ifc:IfcRelDefinesByProperties .
      ?s ifc:relatedObjects_IfcRelDefinesByProperties ?port .
      ?s ifc:relatingPropertyDefinition_IfcRelDefinesByProperties ?pset .
      ?pset ifc:name_IfcRoot ?label .
      ?label express:hasString ?psetName .

      ?pset ifc:hasProperties_IfcPropertySet ?prop .
      ?prop ifc:name_IfcProperty ?identifier .
      ?identifier express:hasString ?propName .

      ?prop ifc:nominalValue_IfcPropertySingleValue ?value .
      ?value ?p ?propValue .
      ?p a owl:DatatypeProperty .
      BIND(DATATYPE(?propValue) AS ?datatype)
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
      fileUrl: r.fileUrl
        ? r.fileUrl.replace("file:///", "")
        : r.fileUrl,
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
      fileUrl: e.fileUrl
        ? e.fileUrl.replace("file:///", "")
        : e.fileUrl,
    }));
    const ifcData = await fetchQuery(ifcQuery);
    const ifcs = ifcData.map((i: any) => ({
      node: i.node,
      ifcClass: i.ifcClass,
      predefinedType: i.predefinedType,
      objectType: i.objectType,
    }));
    const ifcPsetData = await fetchQuery(ifcPsetQuery);
    const ifcPsets = ifcPsetData.map((p: any) => ({
      node: p.node,
      psetName: p.psetName,
      propName: p.propName,
      propValue: p.propValue,
      datatype: p.datatype,
    }));
    const portRawData = await fetchQuery(portQuery);
    const portData = portRawData.map((p: any) => ({
      node: p.node,
      portName: p.portName,
      systemType: p.systemType,
      predefinedType: p.predefinedType,
      flowDirection: p.flowDirection,
    }));
    const portPsetRawData = await fetchQuery(portPsetQuery);
    const portPsets = portPsetRawData.map((p: any) => ({
      node: p.node,
      psetName: p.psetName,
      propName: p.propName,
      propValue: p.propValue,
      datatype: p.datatype,
    }));

    // build tree
    const hierarchy = buildTree(
      edges,
      roots,
      ifcs,
      ifcPsets,
      portData,
      portPsets,
    );
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
  const { activeProject } = useProject();

  const buildHierarchy = async () => {
    await refreshStepHierarchy(activeProject?.graphUri ?? "", setTree, setMessage);
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
