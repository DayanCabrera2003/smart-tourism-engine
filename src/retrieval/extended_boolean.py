"""T032 — Esqueleto del Modelo Booleano Extendido (p-norm).

Referencia:
    Salton, G., Fox, E. A., & Wu, H. (1983).
    Extended Boolean information retrieval.
    Communications of the ACM, 26(11), 1022-1036.
"""

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
