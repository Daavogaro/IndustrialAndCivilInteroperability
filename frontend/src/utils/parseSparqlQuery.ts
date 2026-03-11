type SparqlTerm = {
  type: "uri" | "literal" | "bnode";
  value: string;
};

type SparqlBinding = Record<string, SparqlTerm>;

export function parseSparqlBindings(bindings: SparqlBinding[]) {
  return bindings.map((binding) => {
    const row: Record<string, string> = {};
    for (const key in binding) {
      row[key] = binding[key].value;
    }
    return row;
  });
}
