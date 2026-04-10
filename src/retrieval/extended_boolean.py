"""T032/T033/T037 — Modelo Booleano Extendido (p-norm).

Referencia:
    Salton, G., Fox, E. A., & Wu, H. (1983).
    Extended Boolean information retrieval.
    Communications of the ACM, 26(11), 1022-1036.
"""

from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.indexing.inverted_index import InvertedIndex
    from src.retrieval.query_parser import Node

__all__ = ["ExtendedBoolean"]


def _leaf_terms(ast: Node) -> list[str]:
    """Extrae todos los términos hoja (TermNode) del AST en orden de aparición."""
    from src.retrieval.query_parser import AndNode, OrNode, TermNode  # evita ciclo

    if isinstance(ast, TermNode):
        return [ast.term]
    if isinstance(ast, (AndNode, OrNode)):
        terms: list[str] = []
        for child in ast.children:
            terms.extend(_leaf_terms(child))
        return terms
    return []


class ExtendedBoolean:
    """
    Modelo Booleano Extendido basado en la norma-p (Salton, Fox & Wu, 1983).

    Interpola entre el Booleano puro (p→∞) y el Vectorial (p=1),
    permitiendo ranking continuo sobre consultas con estructura lógica AND/OR.

    Atributos:
        p: Parámetro de la norma. Debe ser > 0.
           Valores típicos para turismo: p ∈ [2, 5].
           p=1 → comportamiento vectorial.
           p→∞ → comportamiento Booleano puro.
    """

    def __init__(self, p: float = 2.0) -> None:
        """
        Inicializa el modelo con el parámetro de norma p.

        Args:
            p: Parámetro de la norma-p. Debe ser estrictamente positivo.

        Raises:
            ValueError: Si p ≤ 0.
        """
        if p <= 0:
            raise ValueError(f"El parámetro p debe ser > 0, se recibió: {p}")
        self.p = p

    def or_norm(self, weights: Sequence[float]) -> float:
        """Similitud OR p-norm (Salton, Fox & Wu, 1983, ecuación 4).

        Fórmula:
            sim_or = ( Σ wᵢᵖ / n ) ^ (1/p)

        Con p=1 se obtiene la media aritmética (comportamiento vectorial).
        Con p→∞ converge al máximo (Booleano puro: OR estricto).

        Args:
            weights: Pesos TF-IDF normalizados de los términos de la consulta
                     en el documento evaluado. Cada peso debe estar en [0, 1].

        Returns:
            Similitud en [0, 1]. Devuelve 0.0 si la lista está vacía.
        """
        n = len(weights)
        if n == 0:
            return 0.0
        return (sum(w ** self.p for w in weights) / n) ** (1.0 / self.p)

    def and_norm(self, weights: Sequence[float]) -> float:
        """Similitud AND p-norm (Salton, Fox & Wu, 1983, ecuación 5).

        Fórmula:
            sim_and = 1 - ( Σ (1 - wᵢ)ᵖ / n ) ^ (1/p)

        Con p=1 se obtiene la media aritmética (comportamiento vectorial).
        Con p→∞ converge al mínimo (Booleano puro: todos los términos deben ocurrir).

        Args:
            weights: Pesos TF-IDF normalizados de los términos de la consulta
                     en el documento evaluado. Cada peso debe estar en [0, 1].

        Returns:
            Similitud en [0, 1]. Devuelve 0.0 si la lista está vacía.
        """
        n = len(weights)
        if n == 0:
            return 0.0
        return 1.0 - (sum((1.0 - w) ** self.p for w in weights) / n) ** (1.0 / self.p)

    def evaluate(self, ast: Node, doc_weights: dict[str, float]) -> float:
        """Evalúa recursivamente el AST aplicando las fórmulas p-norm (T036).

        Recorre el árbol producido por ``parse_query`` y combina los pesos
        TF-IDF del documento usando AND/OR p-norm según el nodo visitado.

        Args:
            ast:         Árbol AST generado por ``parse_query``.
            doc_weights: Pesos TF-IDF normalizados del documento a evaluar,
                         con claves ya en forma de stem.  Los términos
                         ausentes se tratan como peso ``0.0``.

        Returns:
            Similitud en ``[0, 1]``.
        """
        from src.retrieval.query_parser import AndNode, OrNode, TermNode  # evita ciclo en runtime

        if isinstance(ast, TermNode):
            return doc_weights.get(ast.term, 0.0)
        if isinstance(ast, AndNode):
            weights = [self.evaluate(child, doc_weights) for child in ast.children]
            return self.and_norm(weights)
        if isinstance(ast, OrNode):
            weights = [self.evaluate(child, doc_weights) for child in ast.children]
            return self.or_norm(weights)
        return 0.0  # nodo desconocido

    def search(
        self,
        query: str,
        index: InvertedIndex,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """Búsqueda end-to-end con ranking p-norm (T037).

        Flujo:
            1. Parsea ``query`` → AST.
            2. Extrae los términos hoja del AST.
            3. Recupera los postings TF-IDF de cada término en el índice.
            4. Construye ``doc_weights`` normalizado (TF-IDF / norma-L2) por doc.
            5. Evalúa el AST contra cada candidato y ordena por score.

        Args:
            query:  Consulta con operadores AND/OR (mayúsculas).
            index:  Índice invertido con TF-IDF ya calculado
                    (``compute_tf_idf()`` debe haberse llamado).
            top_k:  Número máximo de resultados a devolver.

        Returns:
            Lista de ``(doc_id, score)`` ordenada de mayor a menor similitud,
            con como máximo ``top_k`` elementos.
        """
        from src.retrieval.query_parser import parse_query  # evita ciclo en runtime

        ast = parse_query(query)

        # Recopilar pesos TF-IDF normalizados por documento
        # doc_weights_raw[doc_id][term] = tfidf_weight
        doc_weights_raw: dict[str, dict[str, float]] = defaultdict(dict)
        for term in _leaf_terms(ast):
            for doc_id, weight in index.get_tfidf_postings(term):
                doc_weights_raw[doc_id][term] = weight

        # Normalizar por la norma L2 del documento → pesos en [0, 1]
        scores: dict[str, float] = {}
        for doc_id, raw in doc_weights_raw.items():
            norm = index.get_norm(doc_id)
            if norm == 0.0:
                doc_weights: dict[str, float] = {t: 0.0 for t in raw}
            else:
                doc_weights = {t: w / norm for t, w in raw.items()}
            scores[doc_id] = self.evaluate(ast, doc_weights)

        return heapq.nlargest(top_k, scores.items(), key=lambda x: x[1])

    def score(self, query: str, doc_id: str) -> float:
        """
        Calcula la similitud p-norm entre una consulta y un documento.

        Esqueleto — implementación completa en T033 (OR) y T034 (AND).

        Args:
            query:  Consulta con operadores AND/OR/NOT.
            doc_id: Identificador del documento a puntuar.

        Returns:
            Similitud en [0, 1]. Actualmente siempre devuelve 0.0.
        """
        return 0.0
