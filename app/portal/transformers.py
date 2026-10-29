"""
Portal service layer for Distribution Transformers and Network Hierarchy.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from fastapi import HTTPException

from app.cache import transformers_cache
from app.models.transformer import NetworkNode, Transformer, TransformerListResponse
from app.portal.client import portal_client

logger = logging.getLogger(__name__)


def _map_transformer(raw: dict) -> Transformer:
    return Transformer(
        code=raw.get("code") or raw.get("dtCode", ""),
        name=raw.get("name", ""),
        feeder_code=raw.get("feederCode") or raw.get("feeder", ""),
        capacity_kva=raw.get("capacityKva") or raw.get("capacity"),
    )


async def fetch_all_transformers() -> list[Transformer]:
    """Fetch all Distribution Transformers from /portal/dts (paginating all pages)."""
    cache_key = "dts:all"
    cached = await transformers_cache.get(cache_key)
    if cached is not None:
        return cached

    all_dts: list[Transformer] = []
    page = 1
    page_size = 20

    while True:
        resp = await portal_client.get("/portal/dts", params={"page": page})
        if resp.status_code != 200:
            break
        data = resp.json()
        items = data.get("data", []) if isinstance(data, dict) else data
        if not items:
            break

        all_dts.extend([_map_transformer(t) for t in items])

        total = data.get("total") if isinstance(data, dict) else None
        if total and len(all_dts) >= total:
            break
        page += 1

    await transformers_cache.set(cache_key, all_dts)
    return all_dts


async def list_transformers(page: int = 1, page_size: int = 20) -> TransformerListResponse:
    dts = await fetch_all_transformers()
    total = len(dts)
    total_pages = max(1, math.ceil(total / page_size))
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_data = dts[start_idx:end_idx]

    return TransformerListResponse(
        data=page_data,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def build_network_tree() -> NetworkNode:
    """
    Reconstruct the full 7-level distribution network hierarchy tree:
      Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT

    Aggregates meter counts at each level by using the meter inventory.
    """
    cache_key = "network:full_tree"
    cached = await transformers_cache.get(cache_key)
    if cached is not None:
        return cached

    # Import here to avoid circular dependencies
    from app.portal.meters import fetch_all_meters

    meters = await fetch_all_meters()
    dts = await fetch_all_transformers()

    # Map DT code -> DT metadata
    dt_meta = {dt.code: dt for dt in dts}

    # Root tree structure
    root = NetworkNode(
        id="ROOT",
        name="Distribution Network",
        level="root",
        children=[],
        meter_count=len(meters),
    )

    # Dictionary to look up / create nodes at each level:
    # key: (level, code) -> NetworkNode
    nodes: dict[tuple[str, str], NetworkNode] = {}

    for m in meters:
        h = m.hierarchy
        levels_in_order = [
            ("zone", h.zone),
            ("circle", h.circle),
            ("division", h.division),
            ("subdivision", h.subdivision),
            ("substation", h.substation),
            ("feeder", h.feeder),
            ("dt", h.dt),
        ]

        parent_node = root
        for lvl_name, item in levels_in_order:
            if not item:
                continue
            key = (lvl_name, item.code)
            if key not in nodes:
                node = NetworkNode(
                    id=item.code,
                    name=item.name,
                    level=lvl_name,
                    children=[],
                    meter_count=0,
                )
                nodes[key] = node
                parent_node.children.append(node)
            else:
                node = nodes[key]

            # Increment meter count for this subtree
            node.meter_count = (node.meter_count or 0) + 1
            parent_node = node

    await transformers_cache.set(cache_key, root)
    return root
