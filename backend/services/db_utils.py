"""Database utility functions for common query patterns.

Provides helpers that reduce redundant database round-trips,
e.g. combining count + find into a single $facet aggregation.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def paginated_query(
    collection,
    query: dict,
    sort: list,
    skip: int,
    limit: int,
    projection: dict | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Execute a single MongoDB query that returns both data and total count.

    Replaces the common pattern of:
        total = await collection.count_documents(query)
        data = await collection.find(query, proj).sort(...).skip(...).limit(...).to_list(...)

    with a single $facet aggregation that fetches both in one round-trip.

    Args:
        collection: Motor collection object
        query: MongoDB filter dict
        sort: List of (field, direction) tuples, e.g. [("name", 1), ("created_at", -1)]
        skip: Number of documents to skip
        limit: Maximum number of documents to return
        projection: Optional MongoDB projection dict (excluding _id is added automatically)

    Returns:
        Tuple of (data_list, total_count)
    """
    pipeline: list[dict[str, Any]] = [
        {"$match": query},
    ]

    if sort:
        sort_spec = dict(sort)
        pipeline.append({"$sort": sort_spec})

    # Build the data sub-pipeline
    data_pipeline: list[dict[str, Any]] = [
        {"$skip": skip},
        {"$limit": limit},
    ]
    if projection is not None:
        # Ensure _id is excluded
        proj = dict(projection)
        proj["_id"] = 0
        data_pipeline.append({"$project": proj})

    pipeline.append(
        {
            "$facet": {
                "data": data_pipeline,
                "total": [{"$count": "count"}],
            }
        }
    )

    result = await (await collection.aggregate(pipeline)).to_list(1)
    if result:
        data = result[0].get("data", [])
        total_list = result[0].get("total", [])
        total = total_list[0]["count"] if total_list else 0
        return data, total
    return [], 0
