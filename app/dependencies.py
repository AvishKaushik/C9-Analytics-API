"""FastAPI dependency injection helpers."""

from functools import lru_cache
from shared.grid_client import GridClient
from .config import get_settings


@lru_cache
def get_grid_client() -> GridClient:
    return GridClient()
