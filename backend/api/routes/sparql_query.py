# backend/api/routes/sparql_query.py
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from SPARQLWrapper import SPARQLWrapper, JSON
import os
from ..models.models import VIRTUOSO_URL,GRAPH_NAMESPACE, X3D_NAMESPACE

router = APIRouter()

class SparqlRequest(BaseModel):
    query: str

def execute_sparql(query: str):

    sparql = SPARQLWrapper(VIRTUOSO_URL)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(20)

    return sparql.query().convert()

@router.post("/sparql-query")
async def sparql_query(request: SparqlRequest):
    try:
        return await run_in_threadpool(execute_sparql, request.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing query: {e}")