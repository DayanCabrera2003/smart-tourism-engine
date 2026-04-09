import math
from collections import defaultdict

__all__ = ["InvertedIndex"]

DocId = str
# Postings con TF crudo: lista de (doc_id, freq)
Postings = list[tuple[DocId, int]]
# Postings con peso TF-IDF: lista de (doc_id, weight)
TfIdfPostings = list[tuple[DocId, float]]


class InvertedIndex:
    """
    Índice invertido en memoria con soporte de TF-IDF y normas para similitud coseno.

    Estructura interna:
        _raw:    dict[term, dict[doc_id, tf_crudo]]
        _tfidf:  dict[term, dict[doc_id, peso_tfidf]]   (tras compute_tf_idf)
        _norms:  dict[doc_id, norma_l2]                 (tras compute_tf_idf)
    """

    def __init__(self) -> None:
        # term → {doc_id → freq}
        self._raw: dict[str, dict[DocId, int]] = defaultdict(dict)
        self._doc_count: int = 0
        # Poblados por compute_tf_idf()
        self._tfidf: dict[str, dict[DocId, float]] = {}
        self._norms: dict[DocId, float] = {}

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

    def compute_tf_idf(self) -> None:
        """
        Calcula los pesos TF-IDF para cada par (término, documento) y las
        normas L2 de cada documento para similitud coseno.

        Fórmulas:
            TF(t, d)  = freq(t, d) / max_freq(d)      (TF normalizado)
            IDF(t)    = log( N / df(t) ) + 1           (IDF suavizado)
            w(t, d)   = TF(t, d) * IDF(t)
            norm(d)   = sqrt( sum( w(t,d)^2 ) )

        Debe llamarse después de añadir todos los documentos con add_document().
        Invalida resultados anteriores si se llama varias veces.
        """
        N = self._doc_count
        if N == 0:
            return

        # Paso 1: calcular la frecuencia máxima por documento
        max_freq: dict[DocId, int] = defaultdict(int)
        for postings in self._raw.values():
            for doc_id, freq in postings.items():
                if freq > max_freq[doc_id]:
                    max_freq[doc_id] = freq

        # Paso 2: calcular TF-IDF
        self._tfidf = {}
        for term, postings in self._raw.items():
            df = len(postings)
            idf = math.log(N / df) + 1
            self._tfidf[term] = {}
            for doc_id, freq in postings.items():
                tf = freq / max_freq[doc_id]
                self._tfidf[term][doc_id] = tf * idf

        # Paso 3: calcular normas L2 por documento
        norms_sq: dict[DocId, float] = defaultdict(float)
        for postings in self._tfidf.values():
            for doc_id, weight in postings.items():
                norms_sq[doc_id] += weight**2
        self._norms = {doc_id: math.sqrt(sq) for doc_id, sq in norms_sq.items()}

    def get_postings(self, term: str) -> Postings:
        """
        Devuelve la lista de postings (TF crudo) para un término.

        Returns:
            Lista de tuplas (doc_id, freq) ordenada por doc_id.
            Lista vacía si el término no está en el índice.
        """
        return sorted(self._raw.get(term, {}).items())

    def get_tfidf_postings(self, term: str) -> TfIdfPostings:
        """
        Devuelve los postings con peso TF-IDF para un término.

        Requiere haber llamado compute_tf_idf() previamente.

        Returns:
            Lista de tuplas (doc_id, weight) ordenada por doc_id.
            Lista vacía si el término no está en el índice o no se calculó TF-IDF.
        """
        return sorted(self._tfidf.get(term, {}).items())

    def get_norm(self, doc_id: DocId) -> float:
        """
        Devuelve la norma L2 del vector TF-IDF de un documento.

        Requiere haber llamado compute_tf_idf() previamente.

        Returns:
            Norma L2 del documento. 0.0 si no existe o no se calculó.
        """
        return self._norms.get(doc_id, 0.0)

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
