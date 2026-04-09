from collections import defaultdict

__all__ = ["InvertedIndex"]

DocId = str
# Postings: lista de (doc_id, frecuencia)
Postings = list[tuple[DocId, int]]


class InvertedIndex:
    """
    Índice invertido en memoria.

    Estructura interna:
        _index: dict[term, list[(doc_id, freq)]]

    Cada entrada mapea un término a la lista de documentos que lo contienen
    junto con la frecuencia de aparición (TF crudo) en ese documento.
    """

    def __init__(self) -> None:
        # term → {doc_id → freq}
        self._raw: dict[str, dict[DocId, int]] = defaultdict(dict)
        self._doc_count: int = 0

    def add_document(self, doc_id: DocId, tokens: list[str]) -> None:
        """
        Indexa un documento dado su identificador y sus tokens preprocesados.

        Args:
            doc_id: Identificador único del documento.
            tokens: Lista de tokens (ya normalizados y stemizados).
        """
        self._doc_count += 1
        freq: dict[str, int] = defaultdict(int)
        for token in tokens:
            freq[token] += 1
        for term, count in freq.items():
            self._raw[term][doc_id] = count

    def get_postings(self, term: str) -> Postings:
        """
        Devuelve la lista de postings para un término.

        Args:
            term: Término a consultar (debe estar en la misma forma normalizada
                  que los tokens indexados).

        Returns:
            Lista de tuplas (doc_id, freq) ordenada por doc_id.
            Lista vacía si el término no está en el índice.
        """
        postings = self._raw.get(term, {})
        return sorted(postings.items())

    @property
    def doc_count(self) -> int:
        """Número de documentos indexados."""
        return self._doc_count

    @property
    def vocabulary(self) -> set[str]:
        """Conjunto de términos en el índice."""
        return set(self._raw.keys())

    def __len__(self) -> int:
        return len(self._raw)

    def __contains__(self, term: str) -> bool:
        return term in self._raw
