"""T092 - Synthetic profiles that bootstrap the recommender.

We do not have explicit user data when the system launches, so the
recommender starts from a curated catalog of synthetic personas. Each
persona is a frozen ``UserProfile`` with a curated set of interest tags
that match the dominant flavours of the corpus.

These profiles serve two purposes:

1. Onboarding: the UI presents them as one-click presets so a brand new
   user can get a meaningful "Recomendado para ti" feed immediately.
2. Cold-start collaborative signal: T094 (pseudo-collaborative
   recommender) snaps an arbitrary user profile to the nearest synthetic
   persona and uses that persona's profile as a proxy for "users like
   you".
"""
from __future__ import annotations

from src.recommendation.user_profile import UserProfile

__all__ = [
    "SYNTHETIC_PROFILE_DESCRIPTIONS",
    "SYNTHETIC_PROFILES",
    "get_synthetic_profile",
    "list_synthetic_profile_ids",
]


SYNTHETIC_PROFILE_DESCRIPTIONS: dict[str, str] = {
    "mochilero": (
        "Viajeros independientes y de bajo presupuesto que priorizan "
        "aventura, naturaleza y experiencias auténticas sobre comodidad."
    ),
    "familia": (
        "Familias con niños o adolescentes que buscan destinos seguros, "
        "actividades para todas las edades y servicios accesibles."
    ),
    "luna_de_miel": (
        "Parejas que buscan destinos románticos, playas tranquilas, "
        "atardeceres y experiencias íntimas."
    ),
    "aventurero": (
        "Viajeros que priorizan deportes, adrenalina y rutas exigentes en "
        "montaña, selva o mar."
    ),
    "cultural": (
        "Viajeros interesados en historia, arte, gastronomía local y "
        "patrimonio arquitectónico."
    ),
    "lujo": (
        "Viajeros con alto presupuesto que buscan hoteles de gama alta, "
        "experiencias exclusivas y destinos icónicos."
    ),
}


_SYNTHETIC_PROFILE_INTERESTS: dict[str, list[str]] = {
    "mochilero": [
        "aventura",
        "naturaleza",
        "bajo presupuesto",
        "hostales",
        "rutas alternativas",
        "trekking",
    ],
    "familia": [
        "familias",
        "playa",
        "parques",
        "actividades para niños",
        "seguridad",
        "gastronomía",
    ],
    "luna_de_miel": [
        "romántico",
        "playa tranquila",
        "atardeceres",
        "spa",
        "lujo discreto",
        "naturaleza",
    ],
    "aventurero": [
        "aventura",
        "montaña",
        "trekking",
        "deportes extremos",
        "selva",
        "rafting",
    ],
    "cultural": [
        "cultura",
        "historia",
        "museos",
        "arquitectura",
        "gastronomía",
        "patrimonio",
    ],
    "lujo": [
        "lujo",
        "hoteles 5 estrellas",
        "gastronomía",
        "experiencias exclusivas",
        "spa",
        "destinos icónicos",
    ],
}


def _build_synthetic_profiles() -> dict[str, UserProfile]:
    """Materialize the synthetic profile dictionary.

    Kept as a function (rather than a literal at import time) so any
    future logic that derives interests from the corpus or from an
    external config file has a single place to hook into.
    """
    profiles: dict[str, UserProfile] = {}
    for profile_id, interests in _SYNTHETIC_PROFILE_INTERESTS.items():
        profiles[profile_id] = UserProfile(
            id=f"synthetic:{profile_id}",
            name=profile_id,
            interests=list(interests),
        )
    return profiles


SYNTHETIC_PROFILES: dict[str, UserProfile] = _build_synthetic_profiles()


def list_synthetic_profile_ids() -> list[str]:
    """Stable list of available synthetic profile ids for UI dropdowns."""
    return list(_SYNTHETIC_PROFILE_INTERESTS.keys())


def get_synthetic_profile(profile_id: str) -> UserProfile:
    """Return a fresh copy of the named synthetic profile.

    We return a copy (not the cached instance) so callers can mutate the
    profile - for example, by appending history entries - without
    contaminating the shared catalog used by other requests.
    """
    if profile_id not in SYNTHETIC_PROFILES:
        raise KeyError(
            f"Unknown synthetic profile: {profile_id!r}. "
            f"Available: {list_synthetic_profile_ids()}"
        )
    return SYNTHETIC_PROFILES[profile_id].model_copy(deep=True)
