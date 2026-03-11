# Dockerized-Site-Template

Comandi per caricare triple su Virtuoso

- grant SPARQL_UPDATE to "SPARQL" da mettere in Database>InterativeSQL. Questo comando permette a tutti di caricare le triple

Comando per scaricare un file TTL da Virtuoso:
CONSTRUCT { ?s ?p ?o }
WHERE {
GRAPH <http://localhost:8890/Elettra2/> {
?s ?p ?o
}
}
