"""
Distribution Transformer and Network routes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from app.models.transformer import NetworkNode, TransformerListResponse
from app.portal.transformers import build_network_tree, list_transformers

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Network"])


@router.get("/transformers", response_model=TransformerListResponse, summary="List distribution transformers")
async def get_transformers(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Returns a paginated list of Distribution Transformers (DTs) with their parent feeder
    and rated capacity (kVA).
    """
    return await list_transformers(page=page, page_size=page_size)


@router.get("/network", response_model=NetworkNode, summary="Complete 7-level network hierarchy tree")
async def get_network_hierarchy():
    """
    Reconstructs and returns the full 7-level distribution network hierarchy tree:
    
    Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> Distribution Transformer (DT)
    
    Each node includes its code, name, level, and aggregated meter count.
    """
    return await build_network_tree()
