from typing import Any

from app.config import get_settings
from app.index_store import CatalogIndex
from app.indexer.characters import scan_characters
from app.indexer.references import scan_references_for_folder
from app.storage.json_store import load_optional_json


def build_index() -> CatalogIndex:
    s = get_settings()
    mappings = load_optional_json(s.data_dir / s.character_mappings_file)
    characters = scan_characters()
    references: dict[str, list[dict[str, Any]]] = {}
    for c in characters:
        folder = c["folder"]
        references[folder] = scan_references_for_folder(folder)
    return CatalogIndex(characters=characters, references=references, mappings=mappings)