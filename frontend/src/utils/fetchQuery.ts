import { parseSparqlBindings } from "./parseSparqlQuery";

export const fetchQuery = async (query: string) => {
  const res = await fetch("http://localhost:8000/api/sparql-query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });

  const data = await res.json();
  return parseSparqlBindings(data.results.bindings);
};
