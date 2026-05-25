# Referencias

Esta sección contiene la bibliografía y referencias técnicas utilizadas durante el desarrollo del proyecto.

---

## Modelos de Recuperación de Información

1. **Salton, G., Fox, E. A., & Wu, H.** (1983). *Extended Boolean Information Retrieval.* Communications of the ACM, 26(11), 1022-1036. Define el modelo Booleano Extendido con norma-p que usamos en `src/retrieval/extended_boolean.py`.

2. **Salton, G., Wong, A., & Yang, C. S.** (1975). *A Vector Space Model for Automatic Indexing.* Communications of the ACM, 18(11), 613-620. Modelo vectorial clásico que motiva el caso `p=1` del Booleano Extendido.

3. **Manning, C. D., Raghavan, P., & Schütze, H.** (2008). *Introduction to Information Retrieval.* Cambridge University Press. Referencia general; usamos en particular los capítulos 1-2 (índice invertido), 6 (pesos y normalizaciones), 8 (evaluación: precision, recall, MAP, MRR, nDCG) y 13 (clasificación).

4. **Croft, W. B., Metzler, D., & Strohman, T.** (2009). *Search Engines: Information Retrieval in Practice.* Pearson. Capítulo 8 cubre métricas de evaluación; consultado para definir las convenciones de borde de `precision_at_k` y `nDCG`.

5. **Robertson, S. E., & Spärck Jones, K.** (1976). *Relevance Weighting of Search Terms.* Journal of the American Society for Information Science, 27(3), 129-146. Fundamento del esquema TF-IDF que aplica `InvertedIndex.compute_tf_idf`.

---

## Diversificación

6. **Carbonell, J., & Goldstein, J.** (1998). *The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries.* SIGIR '98. Algoritmo Maximal Marginal Relevance que implementa `src/retrieval/diversify.py`.

---

## Embeddings densos y modelos multimodales

7. **Reimers, N., & Gurevych, I.** (2019). *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.* EMNLP-IJCNLP. Base de la familia `sentence-transformers` que utiliza `TextEmbedder`.

8. **Wang, L., Yang, N., Huang, X., Yang, L., Majumder, R., & Wei, F.** (2024). *Multilingual E5 Text Embeddings: A Technical Report.* arXiv:2402.05672. Familia E5 multilingüe; el sistema usa la variante `intfloat/multilingual-e5-small` (118 M parámetros, 384 dim) como embedder de texto para Wikivoyage EN + Wikipedia ES.

9. **Radford, A., et al.** (2021). *Learning Transferable Visual Models From Natural Language Supervision.* ICML 2021 (paper CLIP de OpenAI). Modelo `clip-ViT-B-32` que usa `ClipEmbedder` para el espacio multimodal (512 dim).

---

## Retrieval-Augmented Generation

9. **Lewis, P., et al.** (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS 2020. Marco general del pipeline RAG implementado en `src/rag/pipeline.py`.

10. **Izacard, G., & Grave, E.** (2021). *Leveraging Passage Retrieval with Generative Models for Open Domain Question Answering.* EACL 2021. Justificación del enfoque "retrieve-then-read" que se sigue en `/ask`.

---

## Recomendación

11. **Lops, P., de Gemmis, M., & Semeraro, G.** (2011). *Content-based Recommender Systems: State of the Art and Trends.* En *Recommender Systems Handbook*. Base del `ContentBasedRecommender` de `src/recommendation/content_based.py`.

12. **Su, X., & Khoshgoftaar, T. M.** (2009). *A Survey of Collaborative Filtering Techniques.* Advances in Artificial Intelligence, 2009. Marco de referencia para el `CollaborativeRecommender` (versión pseudo-colaborativa por cold-start).

---

## Herramientas y librerías

13. **Qdrant Team** (2024). *Qdrant Vector Database Documentation.* https://qdrant.tech/documentation/

14. **FastAPI** (Ramírez, S., 2018-presente). https://fastapi.tiangolo.com/

15. **Streamlit** (2019-presente). https://streamlit.io/

16. **LlamaIndex** (Liu, J., 2022-presente). https://docs.llamaindex.ai/

17. **Tavily** (2023-presente). https://tavily.com/

18. **Google Gemini** (Google DeepMind, 2024-presente). https://ai.google.dev/

---

## Fuente de datos

19. **Wikivoyage Contributors.** (2026). *Wikivoyage: The Free Worldwide Travel Guide.* https://www.wikivoyage.org/. Licencia CC BY-SA 3.0.

20. **OpenTripMap.** (2024). *OpenTripMap API.* https://opentripmap.io/

---

## Plantilla de informe

21. **Springer LNCS** (Lecture Notes in Computer Science). Plantilla LaTeX usada para exportar la documentación a PDF (T114). https://www.springer.com/gp/computer-science/lncs/conference-proceedings-guidelines
