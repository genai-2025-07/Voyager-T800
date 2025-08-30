"""
Itinerary generation endpoints using RAG pipeline.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.chains.itinerary_chain import full_response


logger = logging.getLogger(__name__)
router = APIRouter(prefix='/itinerary', tags=['itinerary'])


class ItineraryRequest(BaseModel):
    """Request model for itinerary generation."""

    query: str


class ItineraryResponse(BaseModel):
    """Response model for generated itinerary."""

    itinerary: str


@router.post('/generate', response_model=ItineraryResponse)
async def generate_itinerary(request: ItineraryRequest):
    try:
        itinerary = full_response(request.query)
        return ItineraryResponse(itinerary=itinerary)

    except Exception:
        raise HTTPException(status_code=500, detail='Failed to generate itinerary. Please try again.')
