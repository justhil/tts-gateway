"""兼容旧 import：请使用 app.index_store。"""
from app.index_store import CatalogIndex, get_index, invalidate_index

__all__ = ["CatalogIndex", "get_index", "invalidate_index"]