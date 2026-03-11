type TopbarProps = {
  title: string;
};

export function Topbar({ title }: TopbarProps) {
  return (
    <header
      style={{
        padding: 10,
        marginTop: 10,
        backgroundColor: "var(--primary-300)",
        display: "flex",
        justifyContent: "space-between",
      }}>
      <h1>{title}</h1>
    </header>
  );
}
