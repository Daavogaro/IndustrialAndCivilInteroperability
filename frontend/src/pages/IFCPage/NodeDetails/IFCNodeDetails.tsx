import React, { useEffect, useState } from "react";
import { TreeNode } from "../../STEPPage/Hierarchy/buildTree";
import { StatusString } from "../../../components/Sidebar/MessagePanel";
import { DownloadIFCButton } from "./DownloadIFCButton";

type PropertyInputType = "text" | "number" | "boolean" | "select";

type PropertySpec = {
  name: string;
  inputType: PropertyInputType;
  options?: string[];
};

type PSetSpec = {
  name: string;
  properties: PropertySpec[];
};

const IFC_CLASS_TO_PREDEFINED_TYPES: Record<string, string[]> = {
  IfcElementAssembly: ["NOTDEFINED", "ACCESSORY_ASSEMBLY", "ARCH", "BEAM_GRID", "BRACED_FRAME", "GIRDER", "REINFORCEMENT_UNIT", "RIGID_FRAME", "SLAB_FIELD", "TRUSS", "USERDEFINED"],
  IfcWall: ["NOTDEFINED", "MOVABLE", "PARAPET", "PARTITIONING", "PLUMBINGWALL", "POLYGONAL", "SHEAR", "SOLIDWALL", "STANDARD", "ELEMENTEDWALL", "USERDEFINED"],
  IfcSlab: ["NOTDEFINED", "FLOOR", "ROOF", "LANDING", "BASESLAB", "USERDEFINED"],
};

const IFC_CLASSES = Object.keys(IFC_CLASS_TO_PREDEFINED_TYPES);

const IFC_CLASS_TO_PSETS: Record<string, PSetSpec[]> = {
  IfcElementAssembly: [
    {
      name: "Pset_ElementAssemblyCommon",
      properties: [
        { name: "Reference", inputType: "text" },
        { name: "Status", inputType: "select", options: ["NEW", "EXISTING", "DEMOLISH", "TEMPORARY", "NOTKNOWN", "UNSET"] },
        { name: "IsExternal", inputType: "boolean" },
        { name: "LoadBearing", inputType: "boolean" },
        { name: "FireRating", inputType: "text" },
      ],
    },
  ],
  IfcWall: [
    {
      name: "Pset_WallCommon",
      properties: [
        { name: "Reference", inputType: "text" },
        { name: "IsExternal", inputType: "boolean" },
        { name: "LoadBearing", inputType: "boolean" },
        { name: "ThermalTransmittance", inputType: "number" },
        { name: "FireRating", inputType: "text" },
        { name: "AcousticRating", inputType: "text" },
      ],
    },
  ],
  IfcSlab: [
    {
      name: "Pset_SlabCommon",
      properties: [
        { name: "Reference", inputType: "text" },
        { name: "IsExternal", inputType: "boolean" },
        { name: "LoadBearing", inputType: "boolean" },
        { name: "PitchAngle", inputType: "number" },
        { name: "FireRating", inputType: "text" },
      ],
    },
  ],
};

type IFCNodeDetailsProps = {
  uri: string | null;
  tree: TreeNode[];
  setNodeUri: (uri: string | null) => void;
  setMessage: (message: { status: StatusString; text: string }) => void;
};
const findNode = (nodes: TreeNode[], uri: string | null): TreeNode | null => {
  for (const node of nodes) {
    if (node.id === uri) return node;

    const foundInChildren = findNode(node.children, uri);
    if (foundInChildren) return foundInChildren;
  }
  return null;
};

export function IFCNodeDetails({
  uri,
  tree,
  setNodeUri,
  setMessage,
}: IFCNodeDetailsProps) {
  const [treeNodeData, setTreeNodeData] = useState<TreeNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ifcClass, setIfcClass] = useState<string>("None");
  const [predefinedType, setPredefinedType] = useState<string>("NOTDEFINED");
  const [userdefinedType, setUserdefinedType] = useState<string>("");
  const [selectedPsets, setSelectedPsets] = useState<Record<string, boolean>>(
    {},
  );
  const [propertyValues, setPropertyValues] = useState<
    Record<string, Record<string, string | number | boolean>>
  >({});
  const graphName = "http://localhost:8890/Elettra2/";

  const availablePredefinedTypes =
    ifcClass === "None"
      ? ["NOTDEFINED"]
      : IFC_CLASS_TO_PREDEFINED_TYPES[ifcClass] ?? ["NOTDEFINED"];

  const availablePsets = ifcClass === "None" ? [] : IFC_CLASS_TO_PSETS[ifcClass] ?? [];

  const getDefaultPropertyValue = (property: PropertySpec) => {
    if (property.inputType === "boolean") {
      return false;
    }
    if (property.inputType === "number") {
      return "";
    }
    if (property.inputType === "select") {
      return property.options?.[0] ?? "";
    }
    return "";
  };

  const togglePsetSelection = (psetName: string, checked: boolean) => {
    setSelectedPsets((prev) => ({ ...prev, [psetName]: checked }));

    if (!checked) {
      setPropertyValues((prev) => {
        const next = { ...prev };
        delete next[psetName];
        return next;
      });
      return;
    }

    const pset = availablePsets.find((item) => item.name === psetName);
    if (!pset) {
      return;
    }

    setPropertyValues((prev) => {
      if (prev[psetName]) {
        return prev;
      }
      const defaults: Record<string, string | number | boolean> = {};
      pset.properties.forEach((property) => {
        defaults[property.name] = getDefaultPropertyValue(property);
      });
      return { ...prev, [psetName]: defaults };
    });
  };

  const updatePropertyValue = (
    psetName: string,
    propertyName: string,
    value: string | number | boolean,
  ) => {
    setPropertyValues((prev) => ({
      ...prev,
      [psetName]: {
        ...(prev[psetName] ?? {}),
        [propertyName]: value,
      },
    }));
  };

  const onIFCPropertiesFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (ifcClass === "None") {
      setMessage({ status: "error", text: "Please select an IFC Class" });
      return;
    }

    const selectedPropertySets: Record<
      string,
      Record<string, string | number | boolean>
    > = {};

    Object.entries(selectedPsets)
      .filter(([, isSelected]) => isSelected)
      .forEach(([psetName]) => {
        selectedPropertySets[psetName] = propertyValues[psetName] ?? {};
      });

    // TODO: aggiungere logiche per editing esistenti e non solo per aggiungere nuovi nodi
    const res = await fetch("/api/add-ifc-properties", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        graph: graphName,
        metadata: treeNodeData?.metadata,
        ifc_class: ifcClass,
        predefined_type: predefinedType,
        userdefined_type: userdefinedType,
        property_sets: selectedPropertySets,
      }),
    });

    const data = await res.json();
    setMessage({ status: "success", text: data.text });
    setIfcClass("None");
    setPredefinedType("NOTDEFINED");
    setUserdefinedType("");
    setSelectedPsets({});
    setPropertyValues({});
  };

  const onIfcClassChange = (selectedIfcClass: string) => {
    setIfcClass(selectedIfcClass);
    const nextTypes =
      selectedIfcClass === "None"
        ? ["NOTDEFINED"]
        : IFC_CLASS_TO_PREDEFINED_TYPES[selectedIfcClass] ?? ["NOTDEFINED"];
    setPredefinedType(nextTypes[0]);
    setSelectedPsets({});
    setPropertyValues({});
  };

  const onIFCPropertiesFormReset = () => {
    setIfcClass("None");
    setPredefinedType("NOTDEFINED");
    setUserdefinedType("");
    setSelectedPsets({});
    setPropertyValues({});
  };

  useEffect(() => {
    if (!uri) return;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        const nodeData = findNode(tree, uri);
        setTreeNodeData(nodeData);
      } catch (err) {
        setError("Failed to fetch node data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [uri]);

  if (!uri) return <p>No node selected.</p>;
  if (loading) return <p>Loading...</p>;
  if (error) return <p>{error}</p>;
  if (!treeNodeData) return null;

  return (
    <div
      style={{
        backgroundColor: "var(--background-100)",
        padding: 10,
        border: "1px solid var(--grey-2)",
        borderRadius: 5,
        marginTop: 10,
      }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3 style={{ marginBottom: 10 }}>
          {treeNodeData.metadata.split("#")[1]}
        </h3>
        <DownloadIFCButton node={treeNodeData} setMessage={setMessage} />
      </div>
      <form
        id="ifc-properties-form"
        onSubmit={(e) => onIFCPropertiesFormSubmit(e)}
        onReset={onIFCPropertiesFormReset}
        style={{
          border: "1px solid var(--grey-4)",
          padding: 10,
          borderRadius: 10,
        }}>
        <h4 style={{ paddingBottom: 10 }}>Basic properties</h4>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 10,
          }}>
          <div className="ifc-card">
            <h5 style={{ paddingBottom: 10 }}>IFC Class</h5>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <img src="./IFC-logo.png" style={{ height: 30, width: 30 }} />
              <select
                name="ifcClass"
                id="ifcClass"
                style={{ height: 23 }}
                value={ifcClass}
                onChange={(e) => onIfcClassChange(e.target.value)}>
                <option value="None">None</option>
                {IFC_CLASSES.map((ifcClassOption) => (
                  <option key={ifcClassOption} value={ifcClassOption}>
                    {ifcClassOption}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="ifc-card">
            <h5 style={{ paddingBottom: 10 }}>Predefined Type</h5>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="material-icons-round" style={{ fontSize: 28 }}>
                local_offer
              </span>
              <select
                name="predefinedType"
                id="predefinedType"
                style={{ height: 23 }}
                value={predefinedType}
                onChange={(e) => setPredefinedType(e.target.value)}>
                {availablePredefinedTypes.map((predefinedTypeOption) => (
                  <option key={predefinedTypeOption} value={predefinedTypeOption}>
                    {predefinedTypeOption}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="ifc-card">
            <h5 style={{ paddingBottom: 10 }}>Userdefined Type</h5>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="material-icons-round" style={{ fontSize: 28 }}>
                notes
              </span>
              <input
                id="userdefinedTypeInput"
                name="userdefinedTypeInput"
                type="text"
                placeholder="Only for USERDEFINED"
                value={userdefinedType}
                disabled={predefinedType !== "USERDEFINED"}
                onChange={(e) => setUserdefinedType(e.target.value)}
                style={{ height: 19 }}
              />
            </div>
          </div>
        </div>

        <h4 style={{ padding: "10px 0" }}>Property Sets</h4>
        {ifcClass === "None" ? (
          <p style={{ color: "var(--grey-6)" }}>
            Select an IFC Class to configure Property Sets.
          </p>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {availablePsets.map((pset) => (
              <div
                key={pset.name}
                className="ifc-card"
                style={{ border: "1px solid var(--grey-3)" }}>
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 10,
                    cursor: "pointer",
                  }}>
                  <input
                    type="checkbox"
                    checked={!!selectedPsets[pset.name]}
                    onChange={(e) =>
                      togglePsetSelection(pset.name, e.target.checked)
                    }
                  />
                  <strong>{pset.name}</strong>
                </label>

                {selectedPsets[pset.name] && (
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
                      gap: 10,
                    }}>
                    {pset.properties.map((property) => {
                      const value = propertyValues[pset.name]?.[property.name];
                      return (
                        <div key={property.name}>
                          <label
                            htmlFor={`${pset.name}-${property.name}`}
                            style={{ display: "block", marginBottom: 4 }}>
                            {property.name}
                          </label>
                          {property.inputType === "boolean" ? (
                            <input
                              id={`${pset.name}-${property.name}`}
                              type="checkbox"
                              checked={!!value}
                              onChange={(e) =>
                                updatePropertyValue(
                                  pset.name,
                                  property.name,
                                  e.target.checked,
                                )
                              }
                            />
                          ) : property.inputType === "select" ? (
                            <select
                              id={`${pset.name}-${property.name}`}
                              value={String(value ?? "")}
                              onChange={(e) =>
                                updatePropertyValue(
                                  pset.name,
                                  property.name,
                                  e.target.value,
                                )
                              }>
                              {(property.options ?? []).map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <input
                              id={`${pset.name}-${property.name}`}
                              type={property.inputType}
                              value={String(value ?? "")}
                              onChange={(e) =>
                                updatePropertyValue(
                                  pset.name,
                                  property.name,
                                  property.inputType === "number"
                                    ? e.target.value
                                    : e.target.value,
                                )
                              }
                              style={{ width: "100%" }}
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        <div
          style={{
            display: "flex",
            columnGap: 10,
            justifyContent: "flex-end",
            marginTop: 10,
          }}>
          <button
            id="cancel-button"
            style={{ backgroundColor: "grey" }}
            type="reset"
            onClick={() => {}}>
            <span className="material-icons-round">cancel</span>
            Cancel
          </button>
          <button
            style={{ backgroundColor: "rgb(18, 145, 18)" }}
            type="submit"
            onClick={() => {}}>
            <span className="material-icons-round">check</span>
            Apply
          </button>
        </div>
      </form>
    </div>
  );
}
