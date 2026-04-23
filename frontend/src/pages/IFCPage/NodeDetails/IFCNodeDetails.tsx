import React, { useEffect, useRef, useState } from "react";
import { TreeNode } from "../../STEPPage/Hierarchy/buildTree";
import { StatusString } from "../../../components/Sidebar/MessagePanel";
import { DownloadIFCButton } from "./DownloadIFCButton";
import ifcPropertySchemaData from "./ifcPropertySchema.json";
import resourcesSchemaData from "./resourcesIFCSchema.json";

type PropertyInputType = "text" | "number" | "boolean" | "select";

type PropertySpec = {
  name: string;
  dataType: string;
  options?: string[];
};

type ResourceSpec = {
  name: string;
  inputType: PropertyInputType;
  dataType: string;
};

type IFCResourcesSchema = {
  classes: ResourceSpec[];
};

type PSetSpec = {
  name: string;
  properties: PropertySpec[];
};

type PropertyPayload = {
  value: string | number | boolean;
  ifc_value: string;
  data_type: string;
};

type IFCClassSchema = {
  name: string;
  predefinedTypes: string[];
  propertySets: PSetSpec[];
};

type IFCPropertySchema = {
  classes: IFCClassSchema[];
};

const IFC_PROPERTY_SCHEMA = ifcPropertySchemaData as IFCPropertySchema;
const IFC_RESOURCES_SCHEMA = resourcesSchemaData as IFCResourcesSchema;
const IFC_CLASSES = IFC_PROPERTY_SCHEMA.classes.map((item) => item.name);

const IFC_RESOURCE_BY_NAME: Record<string, ResourceSpec> =
  IFC_RESOURCES_SCHEMA.classes.reduce<Record<string, ResourceSpec>>(
    (acc, item) => {
      acc[item.name] = item;
      return acc;
    },
    {},
  );

const IFC_CLASS_TO_PREDEFINED_TYPES: Record<string, string[]> =
  IFC_PROPERTY_SCHEMA.classes.reduce<Record<string, string[]>>((acc, item) => {
    acc[item.name] = item.predefinedTypes;
    return acc;
  }, {});

const IFC_CLASS_TO_PSETS: Record<string, PSetSpec[]> =
  IFC_PROPERTY_SCHEMA.classes.reduce<Record<string, PSetSpec[]>>(
    (acc, item) => {
      acc[item.name] = item.propertySets;
      return acc;
    },
    {},
  );

const resolvePropertyInputType = (
  property: PropertySpec,
): PropertyInputType => {
  if (property.options && property.options.length > 0) {
    return "select";
  }

  return IFC_RESOURCE_BY_NAME[property.dataType]?.inputType ?? "text";
};

const resolvePropertyPrimitiveDataType = (property: PropertySpec): string => {
  return IFC_RESOURCE_BY_NAME[property.dataType]?.dataType ?? "UNKNOWN";
};

const normalizeIfcName = (value?: string | null): string => {
  if (!value) {
    return "";
  }

  return value.split("#").pop() ?? value;
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
  const initializedForUri = useRef<string | null>(null);
  const [treeNodeData, setTreeNodeData] = useState<TreeNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ifcClass, setIfcClass] = useState<string>("None");
  const [predefinedType, setPredefinedType] = useState<string>("NOTDEFINED");
  const [objectType, setobjectType] = useState<string>("");
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
      : (IFC_CLASS_TO_PREDEFINED_TYPES[ifcClass] ?? ["NOTDEFINED"]);

  const availablePsets =
    ifcClass === "None" ? [] : (IFC_CLASS_TO_PSETS[ifcClass] ?? []);

  const getDefaultPropertyValue = (property: PropertySpec) => {
    const inputType = resolvePropertyInputType(property);

    if (inputType === "boolean") {
      return false;
    }
    if (inputType === "number") {
      return "";
    }
    if (inputType === "select") {
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
      Record<string, PropertyPayload>
    > = {};

    Object.entries(selectedPsets)
      .filter(([, isSelected]) => isSelected)
      .forEach(([psetName]) => {
        const psetSpec = availablePsets.find((item) => item.name === psetName);
        if (!psetSpec) {
          return;
        }

        const propertyPayload: Record<string, PropertyPayload> = {};

        psetSpec.properties.forEach((property) => {
          propertyPayload[property.name] = {
            value: propertyValues[psetName]?.[property.name] ?? "",
            ifc_value: property.dataType,
            data_type: resolvePropertyPrimitiveDataType(property),
          };
        });

        selectedPropertySets[psetName] = propertyPayload;
      });

    // TODO: aggiungere logiche per editing esistenti e non solo per aggiungere nuovi nodi

    const body = {
      graph: graphName,
      metadata: treeNodeData?.metadata,
      ifc_class: ifcClass,
      predefined_type: predefinedType,
      userdefined_type: objectType,
      property_sets: selectedPropertySets,
    };
    console.log(body);

    const res = await fetch("/api/add-ifc-properties", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    setMessage({ status: "success", text: data.text });
    setIfcClass("None");
    setPredefinedType("NOTDEFINED");
    setobjectType("");
    setSelectedPsets({});
    setPropertyValues({});
  };

  const onIfcClassChange = (selectedIfcClass: string) => {
    setIfcClass(selectedIfcClass);
    const nextTypes =
      selectedIfcClass === "None"
        ? ["NOTDEFINED"]
        : (IFC_CLASS_TO_PREDEFINED_TYPES[selectedIfcClass] ?? ["NOTDEFINED"]);
    setPredefinedType(nextTypes[0]);
    setSelectedPsets({});
    setPropertyValues({});
  };

  const onIFCPropertiesFormReset = () => {
    setIfcClass("None");
    setPredefinedType("NOTDEFINED");
    setobjectType("");
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

  useEffect(() => {
    if (!treeNodeData) {
      return;
    }

    if (initializedForUri.current === uri) {
      return;
    }

    const nextIfcClass = normalizeIfcName(treeNodeData.ifcClass) || "None";
    const nextPredefinedType =
      normalizeIfcName(treeNodeData.predefinedType) || "NOTDEFINED";

    setIfcClass(nextIfcClass);
    setPredefinedType(nextPredefinedType);
    setobjectType(treeNodeData.objectType ?? "");
    setSelectedPsets({});
    setPropertyValues({});
    initializedForUri.current = uri;
  }, [treeNodeData]);

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
        maxHeight: "90vh",
        overflowY: "auto",
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
                  <option
                    key={predefinedTypeOption}
                    value={predefinedTypeOption}>
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
                id="objectTypeInput"
                name="objectTypeInput"
                type="text"
                placeholder="Only for USERDEFINED"
                value={objectType}
                disabled={predefinedType !== "USERDEFINED"}
                onChange={(e) => setobjectType(e.target.value)}
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
                      gridTemplateColumns:
                        "repeat(auto-fill, minmax(220px, 1fr))",
                      gap: 10,
                    }}>
                    {pset.properties.map((property) => {
                      const inputType = resolvePropertyInputType(property);
                      const primitiveDataType =
                        resolvePropertyPrimitiveDataType(property);
                      const value = propertyValues[pset.name]?.[property.name];

                      return (
                        <div
                          key={property.name}
                          style={{
                            border: "1px solid var(--grey-3)",
                            padding: 10,
                            borderRadius: 5,
                            backgroundColor: "var(--background-100)",
                          }}>
                          <label
                            htmlFor={`${pset.name}-${property.name}`}
                            style={{ display: "block", marginBottom: 4 }}>
                            {property.name}
                          </label>
                          <div
                            style={{
                              marginBottom: 8,
                              color: "var(--grey-6)",
                              fontSize: 12,
                            }}>
                            <div>Resource: {property.dataType}</div>
                            <div>Datatype: {primitiveDataType}</div>
                          </div>
                          {inputType === "boolean" ? (
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
                          ) : inputType === "select" ? (
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
                              type={inputType}
                              value={String(value ?? "")}
                              onChange={(e) =>
                                updatePropertyValue(
                                  pset.name,
                                  property.name,
                                  inputType === "number"
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
