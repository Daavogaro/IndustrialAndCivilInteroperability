import requests
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from ..models.models import VIRTUOSO_URL, GRAPH_NAMESPACE, X3D_NAMESPACE
from .projects import assert_known_graph

router = APIRouter()


class ReviewRequest(BaseModel):
    metadata_uri: str
    graph: str


def _clear_flags(graph: str, metadata_uri: str) -> None:
    # Presence-only flags: deleting an absent flag is a harmless no-op, so the
    # operation is idempotent and needs no existence check.
    update = f"""
        PREFIX x3d: <{X3D_NAMESPACE}>
        DELETE WHERE {{ GRAPH <{graph}> {{ <{metadata_uri}> x3d:hasAddedEntities ?a }} }};
        DELETE WHERE {{ GRAPH <{graph}> {{ <{metadata_uri}> x3d:hasRemovedEntities ?r }} }}
    """
    response = requests.post(
        VIRTUOSO_URL,
        data={"update": update},
        headers={"Accept": "application/sparql-results+json"},
        timeout=15,
    )
    response.raise_for_status()


@router.post("/review-changes")
async def review_changes(request: ReviewRequest):
    # Allowlist-validate the graph and prefix-validate the metadata URI before it is
    # interpolated into the SPARQL update (SPARQL-injection guard).
    assert_known_graph(request.graph)

    if not request.metadata_uri.startswith(str(GRAPH_NAMESPACE)):
        raise HTTPException(
            status_code=400,
            detail=f"metadata_uri must start with {GRAPH_NAMESPACE}",
        )

    try:
        await run_in_threadpool(_clear_flags, request.graph, request.metadata_uri)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear review flags: {e}")

    return {"status": "success"}
