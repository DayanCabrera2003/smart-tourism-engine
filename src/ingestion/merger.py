"""
Fusión y deduplicación de destinos turísticos desde múltiples fuentes.

- Deduplica por nombre y coordenadas (distancia haversine < 1km).
- Mantiene la mayor cantidad de información consolidada.

Uso:
    from src.ingestion.merger import merge_destinations
    destinos = merge_destinations([wikivoyage_list, opentripmap_list, ...])
"""
from math import atan2, cos, radians, sin, sqrt
from typing import List

from src.ingestion.models import Destination

HAVERSINE_THRESHOLD_KM = 1.0

def haversine(coord1, coord2):
    """
    Calcula la distancia Haversine (en km) entre dos coordenadas (lat, lon).
    """
    if not coord1 or not coord2:
        return float('inf')
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371.0  # Radio de la Tierra en km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def merge_destinations(list_of_lists: List[List[Destination]]) -> List[Destination]:
    """
    Fusiona y deduplica destinos de varias fuentes.
    Dos destinos se consideran duplicados si:
      - name.lower() coincide (ignorando acentos y espacios extra)
      - distancia Haversine < 1km
    Devuelve una lista consolidada.
    """
    from src.ingestion.normalize import normalize_text
    merged = []
    seen = []  # Lista de (nombre_normalizado, coordenadas)
    for source_list in list_of_lists:
        for dest in source_list:
            name_norm = normalize_text(dest.name)
            coord = dest.coordinates
            found = False
            for i, (n2, c2) in enumerate(seen):
                coords_match = (coord is None and c2 is None) or (
                    haversine(coord, c2) < HAVERSINE_THRESHOLD_KM
                )
                if name_norm == n2 and coords_match:
                    # Fusionar: prioriza el primer destino, añade tags e imágenes.
                    merged[i].tags = list(set(merged[i].tags) | set(dest.tags))
                    merged[i].image_urls = list(set(merged[i].image_urls) | set(dest.image_urls))
                    if not merged[i].description and dest.description:
                        merged[i].description = dest.description
                    if not merged[i].region and dest.region:
                        merged[i].region = dest.region
                    found = True
                    break
            if not found:
                merged.append(dest)
                seen.append((name_norm, coord))
    return merged
