export type SelectNodeButtonProps = {
  uri: string;
  onClick: (uri: string) => void;
};

export function SelectNode({ uri, onClick }: SelectNodeButtonProps) {
  return (
    <span
      className="generalButton material-icons-round"
      style={{
        padding: "2px",
        borderRadius: "5px",
        cursor: "pointer",
        fontSize: 18,
      }}
      onClick={() => onClick(uri)}>
      check_box_outline_blank
    </span>
  );
}
