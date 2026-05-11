import { useEffect, useState } from "react";

import { StatusString } from "../../components/Sidebar/MessagePanel";
import { Topbar } from "../../components/Topbar";
import { fetchQuery } from "../../utils/fetchQuery";
import { UpdateFileButton } from "./UpdateFileButton";
import { UpdateSTEPModal } from "./UpdateSTEPModal";

type UpdateFilesPageProps = {
    setMessage: (message: { status: StatusString; text: string }) => void;
};

export function UpdateFilesPage({ setMessage }: UpdateFilesPageProps) {
    const [fileUrls, setFileUrls] = useState<{ fileUrl: string; time: string; ownerFirstName: string; ownerLastName: string }[]>([]);
    const [fileName, setFileName] = useState<string>("");

    useEffect(() => {
        const fetchFiles = async () => {
            const graphName = "http://localhost:8890/Elettra2/";

            const queryFiles = `
                PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
                PREFIX pre: <http://www.loc.gov/premis/rdf/v3/>
                PREFIX prov: <http://www.w3.org/ns/prov#>
                PREFIX foaf: <http://xmlns.com/foaf/0.1/>

                SELECT DISTINCT ?fileUrl ?time ?ownerFirstName ?ownerLastName
                FROM <${graphName}>
                WHERE {
                    ?file a pre:File .
                    ?file pre:storedAt ?fileUrl .
                    ?file prov:generatedAtTime ?time .
                    ?file prov:wasAttributedTo ?owner .
                    ?owner foaf:firstName ?ownerFirstName .
                    ?owner foaf:lastName ?ownerLastName .
                }
            `;

            try {
                const fileData = await fetchQuery(queryFiles);

                const urls = fileData.map((r: any) => ({
                    fileUrl: r.fileUrl.replace("file:///",""),
                    time: r.time,
                    ownerFirstName: r.ownerFirstName,
                    ownerLastName: r.ownerLastName,
                }));

                console.log("Fetched file URLs:", urls);

                setFileUrls(urls);

                setMessage({
                    status: "success",
                    text: "Files fetched successfully",
                });
            } catch (err) {
                console.error("File fetch failed", err);

                setMessage({
                    status: "error",
                    text: "Failed to fetch files",
                });
            }
        };

        fetchFiles();
    }, [setMessage]);

    return (
        <div>
            <UpdateSTEPModal fileName={fileName} setMessage={setMessage} />
            <Topbar title="Update Files" />

            <div style={{ padding: "1rem" }}>
                <h3>Fetched Files</h3>

                <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "1rem" }}>
                    <thead>
                        <tr style={{ borderBottom: "2px solid #ddd" }}>
                            <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: "bold" }}>FileURL</th>
                            <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: "bold" }}>Date</th>
                            <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: "bold" }}>Author</th>
                            <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: "bold" }}>Update</th>
                        </tr>
                    </thead>
                    <tbody>
                        {fileUrls.map((file, index) => (
                            <tr key={index} >
                                <td style={{ padding: "0.75rem" }}>{file.fileUrl.split("/tmp/gLTF/")[1].replace(".gltf", "")}</td>
                                <td style={{ padding: "0.75rem" }}>{file.time.replace("T", "   ").replace("Z", "")}</td>
                                <td style={{ padding: "0.75rem" }}>{file.ownerFirstName} {file.ownerLastName}</td>
                                <td style={{ padding: "0.75rem", display: "flex", alignItems: "center", justifyContent: "center" }}>
                                    <UpdateFileButton setFileName={setFileName} fileName={file.fileUrl} />
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}