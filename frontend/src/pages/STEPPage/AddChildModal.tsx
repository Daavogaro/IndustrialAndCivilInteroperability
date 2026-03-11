import { useState } from "react";
import { toogleModal } from "../../utils/htmlFunctions";

type AddChildModalProps = {
  uri: string | null;
};

export function AddChildModal({ uri }: AddChildModalProps) {
  const graphName = "http://localhost:8890/Elettra2/";
  const [value, setValue] = useState("");

  const handleConfirmAddChild = (name: string) => {
    const fetchChild = async (
      graph: string,
      child: string,
      parent: string | null,
    ) => {
      const response = await fetch("http://localhost:8000/api/add-child", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          child: child,
          parent: parent,
          graph: graph,
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text);
      }

      const data = await response.json();
      return data;
    };

    fetchChild(graphName, name, uri);

    setValue("");
    toogleModal("add-child-modal");
  };

  return (
    <dialog
      id="add-child-modal"
      style={{
        backgroundColor: "var(--background-100)",
        padding: 10,
        borderRadius: 10,
      }}>
      <div>
        <h3 style={{ color: "white", paddingBottom: 10 }}>
          Write the name of the new child node:
        </h3>
        {uri ? (
          <p style={{ color: "white", marginBottom: 10 }}>
            Parent node: {uri.split("#")[1]}
          </p>
        ) : (
          <p style={{ color: "white", marginBottom: 10 }}>
            No parent node selected, creation of a new root node
          </p>
        )}
        <div
          style={{
            color: "white",
            marginBottom: 5,
            display: "flex",
            columnGap: 5,
            alignItems: "center",
          }}>
          <p>https://elettra2.0#</p>
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </div>

        <div
          style={{
            display: "flex",
            columnGap: 10,
            justifyContent: "flex-end",
          }}>
          <button
            id="cancel-button"
            style={{ backgroundColor: "grey" }}
            onClick={() => {
              toogleModal("add-child-modal");
              setValue("");
            }}>
            <span className="material-icons-round">cancel</span>
            Cancel
          </button>
          <button
            style={{ backgroundColor: "rgb(18, 145, 18)" }}
            onClick={() => {
              handleConfirmAddChild(value);
            }}>
            <span className="material-icons-round">check</span>
            Create
          </button>
        </div>
      </div>
    </dialog>
  );
}
