"""T062 — Plantilla de prompt para el sistema RAG de turismo."""
from __future__ import annotations

__all__ = ["build_prompt"]

_TEMPLATE = """\
Eres un asistente de turismo experto. Responde la pregunta del usuario \
basándote ÚNICAMENTE en los siguientes destinos:

{context}

Reglas:
- Usa referencias inline [1], [2], etc. para citar los destinos.
- Si la información proporcionada no es suficiente para responder, \
responde exactamente: "No tengo suficiente información para responder."
- No inventes datos que no aparezcan en el contexto.

Pregunta: {query}
Respuesta:"""


def build_prompt(query: str, context: str) -> str:
    """Construye el prompt RAG combinando el contexto y la pregunta."""
    return _TEMPLATE.format(context=context, query=query)
