"""T032/T033 — Modelo Booleano Extendido (p-norm).

Referencia:
    Salton, G., Fox, E. A., & Wu, H. (1983).
    Extended Boolean information retrieval.
    Communications of the ACM, 26(11), 1022-1036.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["ExtendedBoolean"]


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
