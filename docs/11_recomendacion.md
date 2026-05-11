# Módulo de Recomendación

El módulo de recomendación complementa los modos de búsqueda (Booleano Extendido, semántico, híbrido) con un canal "Recomendado para ti" que sugiere destinos sin requerir una consulta explícita por parte del usuario.

A diferencia del recuperador, que parte de una query, el recomendador parte de un **perfil** y devuelve destinos relevantes para ese perfil. Esto cubre dos escenarios típicos del producto:

1. El usuario abre la aplicación sin saber qué buscar y quiere descubrir opciones que encajen con su estilo.
2. El usuario ya hizo varias búsquedas y queremos enriquecer la experiencia con sugerencias coherentes con su histórico.

---

## T091 — Modelo de perfil de usuario

`src/recommendation/user_profile.py` define la clase `UserProfile` y el constructor de embeddings `build_profile_embedding`.

### Esquema

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `str` (obligatorio) | Identificador estable del perfil. Sirve como clave en `st.session_state` y como input del endpoint `/recommend`. |
| `name` | `str \| None` | Etiqueta legible (por ejemplo, `mochilero`). Útil cuando el perfil se construye a partir de un preset sintético (ver T092). |
| `interests` | `list[str]` | Tags declarados por el usuario o heredados de un perfil sintético (`playa`, `montaña`, `cultura`). |
| `history` | `list[str]` | Ids de destinos con los que el usuario interactuó. Hoy se rellena desde el onboarding o desde acciones explícitas; sirve de gancho para futuros features de feedback. |
| `embedding` | `list[float] \| None` | Vector agregado del perfil en el mismo espacio que los destinos (384 dim, igual que `TextEmbedder`). Se calcula bajo demanda y se cachea en el campo. |

### Cálculo del embedding agregado

`build_profile_embedding(profile, embedder, history_embeddings=None)` agrega la señal en tres pasos:

1. **Intereses → vector**: cada tag se embebe con `TextEmbedder.embed(tag)` y se promedia componente a componente. Esto da un vector estable incluso si el usuario no ha interactuado con ningún destino.
2. **Historial → vector**: si se pasa `history_embeddings` (mapa `destination_id → vector` extraído de Qdrant), se promedian los vectores de los destinos que el usuario ya consultó.
3. **Fusión**: se promedian los dos vectores anteriores con peso igual y se aplica L2-normalización. Pesos iguales evitan que un clickstream ruidoso ahogue las preferencias declaradas; la normalización mantiene el producto punto equivalente al coseno (compatible con la métrica `Cosine` de la colección `destinations_text` de Qdrant).

Si no hay señal (sin intereses y sin historial cubierto por `history_embeddings`), el constructor devuelve `None` y el recomendador puede caer en un fallback genérico (popular, último indexado, etc.).

### Decisiones de diseño

- **Mismo espacio que los destinos**: usar `TextEmbedder` (384 dim, `all-MiniLM-L6-v2`) garantiza que `coseno(perfil, destino)` esté bien definido contra cualquier punto de la colección `destinations_text` sin re-encoding ni proyección.
- **Embedding lazy**: el perfil puede vivir sin embedding (recién creado u offline) y materializarlo cuando el recomendador lo necesita. Persistir un vector que rápidamente se vuelve obsoleto contra cambios de catálogo no aporta valor.
- **Tag normalization fuera**: la normalización textual (acentos, minúsculas) ocurre dentro del embedder; el perfil guarda los tags tal cual los declara el usuario para poder mostrarlos en la UI.
