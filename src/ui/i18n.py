"""T116 - Internationalization helper for the Streamlit UI.

Holds a dictionary of strings keyed by ``locale -> key -> value`` and
exposes a single ``t(key, locale)`` lookup so the UI keeps its texts
out of the layout code. The default locale is Spanish (matches the
current UI); English is the secondary locale exposed in the sidebar
toggle.

We intentionally do not pull in ``gettext`` or ``babel``: the surface
area is small (a couple of dozen strings) and a plain dictionary keeps
the dependency footprint and the testability profile simple. If the
catalog grows beyond ~200 keys this module is the right place to swap
to a real i18n framework.
"""
from __future__ import annotations

__all__ = [
    "DEFAULT_LOCALE",
    "LOCALES",
    "TRANSLATIONS",
    "t",
]

DEFAULT_LOCALE = "es"
LOCALES = ("es", "en")


TRANSLATIONS: dict[str, dict[str, str]] = {
    "es": {
        "app_title": "Smart Tourism Engine",
        "app_caption": "Booleano Extendido · Semantico · Hibrido · Recomendaciones",
        "language_label": "Idioma",
        "sidebar_search_mode": "Modo de busqueda",
        "sidebar_parameters": "Parametros",
        "sidebar_profile_header": "Tu perfil",
        "sidebar_change_profile": "Cambiar perfil",
        "tab_search": "Buscar destinos",
        "tab_ask": "Preguntar",
        "tab_image": "Buscar por imagen",
        "tab_reco": "Recomendado para ti",
        "search_query_label": "Consulta",
        "search_button": "Buscar",
        "ask_button": "Preguntar",
        "no_results": "Sin resultados para esta consulta.",
        "empty_query_warning": "Escribe una consulta antes de buscar.",
        "empty_question_warning": "Escribe una pregunta antes de continuar.",
        "show_sections": "Agrupar por estrategia de posicionamiento",
        "show_map": "Mostrar mapa interactivo",
        "section_relevant": "Mas relevantes",
        "section_popular": "Populares",
        "section_recent": "Recientes",
        "section_diverse": "Variados (por pais)",
        "reco_button": "Cargar recomendaciones",
        "reco_top_k_label": "Cuantas recomendaciones",
        "reco_anchor": "Anclado al perfil",
        "reco_no_profile": "Configura tu perfil en el onboarding para ver recomendaciones.",
        "reco_no_results": "No hay recomendaciones disponibles todavia.",
        "onboarding_title": "Que tipo de viajero eres?",
        "onboarding_caption": (
            "Elige el perfil que mas se parezca a ti. "
            "Lo usaremos para personalizar la seccion 'Recomendado para ti'."
        ),
        "onboarding_continue": "Continuar",
        "low_confidence_warning": (
            "Informacion insuficiente en el corpus. Considera ampliar la busqueda."
        ),
        "sources_label": "Fuentes utilizadas:",
        "api_error": "Error al consultar la API",
    },
    "en": {
        "app_title": "Smart Tourism Engine",
        "app_caption": "Extended Boolean · Semantic · Hybrid · Recommendations",
        "language_label": "Language",
        "sidebar_search_mode": "Search mode",
        "sidebar_parameters": "Parameters",
        "sidebar_profile_header": "Your profile",
        "sidebar_change_profile": "Change profile",
        "tab_search": "Search destinations",
        "tab_ask": "Ask",
        "tab_image": "Search by image",
        "tab_reco": "Recommended for you",
        "search_query_label": "Query",
        "search_button": "Search",
        "ask_button": "Ask",
        "no_results": "No results for this query.",
        "empty_query_warning": "Type a query before searching.",
        "empty_question_warning": "Type a question before continuing.",
        "show_sections": "Group by positioning strategy",
        "show_map": "Show interactive map",
        "section_relevant": "Most relevant",
        "section_popular": "Popular",
        "section_recent": "Recent",
        "section_diverse": "Diverse (by country)",
        "reco_button": "Load recommendations",
        "reco_top_k_label": "How many recommendations",
        "reco_anchor": "Anchored to profile",
        "reco_no_profile": "Set your profile in the onboarding flow to see recommendations.",
        "reco_no_results": "No recommendations available yet.",
        "onboarding_title": "What kind of traveller are you?",
        "onboarding_caption": (
            "Pick the profile that fits you best. "
            "We'll use it to personalise the 'Recommended for you' tab."
        ),
        "onboarding_continue": "Continue",
        "low_confidence_warning": (
            "Insufficient information in the corpus. Consider broadening the search."
        ),
        "sources_label": "Sources used:",
        "api_error": "Error querying the API",
    },
}


def t(key: str, locale: str = DEFAULT_LOCALE) -> str:
    """Translate ``key`` into ``locale``.

    Falls back to the default locale when the requested locale is
    unknown, and returns the raw key when even the default does not
    have an entry. We never raise: missing translations are a UI
    annoyance, not a runtime error.
    """
    catalog = TRANSLATIONS.get(locale) or TRANSLATIONS[DEFAULT_LOCALE]
    if key in catalog:
        return catalog[key]
    fallback = TRANSLATIONS[DEFAULT_LOCALE]
    return fallback.get(key, key)
