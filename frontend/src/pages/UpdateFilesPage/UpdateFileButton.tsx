export function UpdateFileButton({ fileUrl }: { fileUrl: string }) {
  return (
    <span
      className="generalButton material-icons-round"
      style={{
        padding: "2px",
        borderRadius: "5px",
        cursor: "pointer",
      }}
      onClick={() => console.log(fileUrl)}>
      autorenew
    </span>
  );
}
