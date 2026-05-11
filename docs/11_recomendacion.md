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

---

## T092 — Perfiles sintéticos predefinidos

`src/recommendation/synthetic_profiles.py` define seis personas que actúan como presets de onboarding y como anclas para el recomendador pseudo-colaborativo (T094). Cada perfil sintético es un `UserProfile` instanciado con un id estable (`synthetic:<nombre>`) y un conjunto curado de intereses que representan los flavours dominantes del corpus.

### Catálogo de perfiles

| Id | Intereses (resumen) | Cuándo aplica |
|---|---|---|
| `mochilero` | aventura, naturaleza, bajo presupuesto, hostales, trekking | Viajero independiente con poco presupuesto; prioriza experiencias auténticas sobre comodidad. |
| `familia` | familias, playa, parques, actividades para niños, seguridad | Familias con menores; necesita destinos seguros y con servicios para todas las edades. |
| `luna_de_miel` | romántico, playa tranquila, atardeceres, spa, lujo discreto | Parejas en celebración; busca privacidad y experiencias íntimas. |
| `aventurero` | aventura, montaña, trekking, deportes extremos, selva | Viajero que prioriza adrenalina; rutas exigentes en montaña, selva o mar. |
| `cultural` | cultura, historia, museos, arquitectura, gastronomía, patrimonio | Viajero interesado en patrimonio, arte y gastronomía local. |
| `lujo` | lujo, hoteles 5 estrellas, gastronomía, experiencias exclusivas, spa | Alto presupuesto; busca destinos icónicos y servicios premium. |

### API

- `SYNTHETIC_PROFILES`: dict `id → UserProfile` instanciado al importar el módulo.
- `SYNTHETIC_PROFILE_DESCRIPTIONS`: descripciones en español usadas por la UI.
- `list_synthetic_profile_ids()`: lista estable para dropdowns y radios.
- `get_synthetic_profile(profile_id)`: devuelve una **copia profunda** del perfil. La copia evita que el historial de un usuario contamine el preset compartido.

### Decisiones de diseño

- **Seis perfiles, no más**: superar seis presets satura la decisión inicial del usuario sin aportar cobertura adicional, porque los segmentos turísticos del corpus solapan más allá de ese número.
- **Intereses en español**: la UI los muestra tal cual, y el embedder `all-MiniLM-L6-v2` es multilingüe, por lo que no se pierde calidad al embeber tags en español contra descripciones de destinos en cualquier idioma del catálogo.
- **Namespace `synthetic:`**: distingue los perfiles preset de los perfiles reales en `user_id`, evitando colisiones si en el futuro se persisten usuarios reales.

---

## T093 — Recomendador content-based

`src/recommendation/content_based.py` define `ContentBasedRecommender`, que rankea destinos por similitud coseno entre el embedding del perfil y los vectores indexados en Qdrant.

### Algoritmo

1. Recibe un `UserProfile` y materializa su embedding con `build_profile_embedding` (puede usar `history_embeddings` opcional para integrar historial real).
2. Si el perfil no tiene señal (sin intereses ni historial cubierto), devuelve `[]` para que la capa de aplicación caiga en un fallback en lugar de inventar resultados.
3. Consulta `VectorStore.search(collection, query_vector, top_k=fetch_k)` sobre la colección `destinations_text` (la misma que usan T053 y T055). Se sobre-pesca (`fetch_k = max(2*top_k, top_k + |excluded|)`) para garantizar `top_k` resultados tras filtrar.
4. Filtra ids presentes en `profile.history` ∪ `exclude` (parámetro opcional del recomendador) y devuelve hasta `top_k` resultados con `(destination_id, score, payload)`.

### Fórmula

Para un perfil con embedding $u$ y un destino con embedding $d_i$:

$$
\mathrm{score}(u, d_i) = \frac{u \cdot d_i}{\|u\| \cdot \|d_i\|}
$$

Ambos vectores están L2-normalizados por construcción (`build_profile_embedding` y `TextEmbedder` lo garantizan), por lo que el producto punto que devuelve Qdrant ya es el coseno.

### Decisiones de diseño

- **Reusar la colección semántica**: en lugar de duplicar embeddings en una colección dedicada a recomendación, el módulo consulta `destinations_text`. Esto evita inconsistencias entre los dos índices y comparte la inversión de T052/T060.
- **Fallback explícito**: la ausencia de señal no se reemplaza dentro del recomendador; la capa superior decide qué mostrar (perfiles populares, último indexado, etc.). Mantener el recomendador puro facilita probarlo en aislamiento.
- **Filtro de historial transparente**: el filtrado ocurre tras la búsqueda usando los ids del payload, lo que evita imponer filtros server-side que limiten la flexibilidad de Qdrant si el corpus crece.

---

## T094 — Recomendador pseudo-colaborativo

`src/recommendation/collaborative.py` define `CollaborativeRecommender`, que aproxima el filtrado colaborativo cuando todavía no hay suficientes interacciones reales para entrenarlo.

### Algoritmo

1. **Snapping a persona**: embebe el perfil del usuario y los seis perfiles sintéticos (T092) con el mismo `TextEmbedder` y elige la persona cuya similitud coseno con el usuario es máxima.
2. **Reuso del content-based**: usa el `ContentBasedRecommender` (T093) con la **copia** de esa persona para producir el ranking final. La copia hereda el historial del usuario, de modo que un destino que el usuario ya visitó queda excluido aunque "los demás de esa persona" lo habrían recomendado.
3. **Fallback**: si el perfil no produce embedding (sin intereses ni historial), devuelve `[]` para no fabricar señal.

### Cache de embeddings de personas

Los seis personas son fijos durante el ciclo de vida del proceso, por lo que sus embeddings se computan una vez y se cachean en la instancia (`_persona_embeddings`). Cada request paga una sola búsqueda en Qdrant: la del content-based final, no seis adicionales para re-embeber las personas.

### Justificación del enfoque "frío"

- **Sin matriz de interacciones**: el proyecto no recolecta ratings ni clicks de cohortes de usuarios. Un colaborativo clásico (KNN sobre usuarios o factorización matricial) requeriría datos que aún no existen.
- **Perfiles sintéticos como sustitutos de cohortes**: cada persona representa un cluster ideal del catálogo, así que recomendar "lo que la persona X consumiría" se comporta como un colaborativo entre usuarios alineados a esa persona.
- **Convergencia con el content-based al solapar señal**: cuando el usuario declara muchos intereses, su embedding se acerca a más de una persona; el recomendador resuelve el empate por coseno máximo, evitando volver al content-based puro.

---

## T095 — Recomendador híbrido

`src/recommendation/hybrid.py` define `HybridRecommender`, que combina las dos ramas con un promedio ponderado.

### Fórmula

Para cada destino candidato $d$:

$$
\mathrm{score}_{\text{hybrid}}(d) = \alpha \cdot \mathrm{score}_{\text{content}}(d) + (1 - \alpha) \cdot \mathrm{score}_{\text{collab}}(d)
$$

con $\alpha \in [0, 1]$. Si una rama no devuelve $d$, su contribución es 0 (no se inventa similitud para suplir el hueco).

### Estrategia de fusion

1. Se piden `2 * top_k` candidatos a cada rama para tener material suficiente tras la unión.
2. Se construye un diccionario `destination_id → score_fused` agregando ambas ramas.
3. Se ordena descendente por `score_fused` y se devuelve `top_k`.
4. El payload preserva el del content-based cuando ambas ramas devolvieron el destino; si solo aparece en colaborativo, se usa el payload de esa rama.

### Decisiones de diseño

- **`alpha=0.6` por defecto**: el content-based reacciona inmediatamente al perfil declarado, así que pesa un poco más; la rama colaborativa aporta diversidad sin dominar. El valor es configurable por request.
- **Ramas independientes**: no se comparte estado entre ambas (la rama colaborativa hace su propio snapping). Esto evita acoplamientos sutiles y permite cachear los embeddings de personas dentro de la rama colaborativa sin afectar al content-based.
- **Sin renormalización post-fusion**: los scores entrantes ya están en $[0, 1]$ (coseno), por lo que el resultado fundido permanece en el mismo rango. Esto permite tratar el score como una "similitud" consistente con los modos de búsqueda.




