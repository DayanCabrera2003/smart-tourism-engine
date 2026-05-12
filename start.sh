#!/usr/bin/env bash
# Smart Tourism Engine — arranque automatizado.
#
# - Levanta Qdrant (Docker) si no esta corriendo.
# - Re-siembra SQLite si esta vacio.
# - Verifica que las colecciones de Qdrant tengan puntos; advierte si no.
# - Lanza uvicorn y streamlit en background con logs en /tmp.
# - Imprime el unico link que necesitas abrir cuando todo este listo.
#
# Uso:
#   ./start.sh           # arranca todo
#   ./start.sh --stop    # mata API + UI + Qdrant
#   ./start.sh --status  # solo reporta estado
#
# Logs:
#   /tmp/sri-api.log    (uvicorn)
#   /tmp/sri-ui.log     (streamlit)
#
# PIDs:
#   /tmp/sri-api.pid
#   /tmp/sri-ui.pid

set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

VENV_PY="$PROJECT_DIR/venv/bin/python"
VENV_ACTIVATE="$PROJECT_DIR/venv/bin/activate"

API_HOST="127.0.0.1"
API_PORT="8000"
UI_PORT="8501"

QDRANT_CONTAINER="sri-qdrant"
QDRANT_PORT="6333"

API_LOG="/tmp/sri-api.log"
UI_LOG="/tmp/sri-ui.log"
API_PID="/tmp/sri-api.pid"
UI_PID="/tmp/sri-ui.pid"

# Colores
if [[ -t 1 ]]; then
    BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'
else
    BOLD=''; GREEN=''; YELLOW=''; RED=''; RESET=''
fi

log()   { echo "${BOLD}>${RESET} $*"; }
ok()    { echo "  ${GREEN}OK${RESET} $*"; }
warn()  { echo "  ${YELLOW}!${RESET}  $*"; }
fail()  { echo "  ${RED}X${RESET}  $*"; }

# ─── helpers ───────────────────────────────────────────────────────────────

is_pid_alive() {
    local pidfile="$1"
    [[ -f "$pidfile" ]] || return 1
    local pid
    pid="$(cat "$pidfile" 2>/dev/null)" || return 1
    [[ -n "$pid" ]] || return 1
    kill -0 "$pid" 2>/dev/null
}

wait_for_http() {
    local url="$1" max_seconds="${2:-30}" label="$3"
    local elapsed=0
    while (( elapsed < max_seconds )); do
        if curl -sS --max-time 2 "$url" >/dev/null 2>&1; then
            ok "$label disponible en $url"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    fail "$label no respondio en $max_seconds segundos ($url)"
    return 1
}

ensure_qdrant() {
    if curl -sS --max-time 2 "http://localhost:${QDRANT_PORT}/collections" >/dev/null 2>&1; then
        ok "Qdrant ya esta corriendo en ${QDRANT_PORT}"
        return 0
    fi
    if ! command -v docker >/dev/null 2>&1; then
        fail "Docker no esta instalado. Instalalo o levanta Qdrant a mano."
        return 1
    fi
    # Si el contenedor existe pero esta parado, arrancalo. Si no, creale.
    if docker ps -a --format '{{.Names}}' | grep -qx "$QDRANT_CONTAINER"; then
        log "Reiniciando contenedor $QDRANT_CONTAINER"
        docker start "$QDRANT_CONTAINER" >/dev/null
    else
        log "Lanzando contenedor $QDRANT_CONTAINER"
        docker run -d --rm \
            --name "$QDRANT_CONTAINER" \
            -p ${QDRANT_PORT}:6333 \
            -p 6334:6334 \
            -v "${PROJECT_DIR}/qdrant_storage:/qdrant/storage" \
            qdrant/qdrant >/dev/null
    fi
    wait_for_http "http://localhost:${QDRANT_PORT}/collections" 30 "Qdrant"
}

count_qdrant_points() {
    local collection="$1"
    curl -sS --max-time 2 "http://localhost:${QDRANT_PORT}/collections/${collection}" 2>/dev/null \
        | "$VENV_PY" -c "import json,sys; d=json.load(sys.stdin); print(d['result']['points_count'])" 2>/dev/null \
        || echo "-1"
}

reseed_sqlite_if_needed() {
    local count
    count="$("$VENV_PY" -c "
from sqlalchemy import select, func
from src.ingestion.store import Session, destinations
with Session() as s:
    print(s.execute(select(func.count()).select_from(destinations)).scalar())
" 2>/dev/null)" || count=0
    if (( count >= 200 )); then
        ok "SQLite con $count filas"
        return 0
    fi
    warn "SQLite con $count filas (re-sembrando desde JSONL...)"
    "$VENV_PY" - <<'PY'
import json
from src.ingestion.models import Destination
from src.ingestion.store import upsert_destination
n = 0
for line in open("data/processed/destinations.jsonl"):
    upsert_destination(Destination.model_validate(json.loads(line)))
    n += 1
print(f"Re-sembradas {n} filas")
PY
}

start_api() {
    if is_pid_alive "$API_PID"; then
        ok "API ya corriendo (pid $(cat "$API_PID"))"
        return 0
    fi
    if curl -sS --max-time 2 "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
        warn "Puerto ${API_PORT} ocupado por otro proceso; usando el existente"
        return 0
    fi
    log "Arrancando API (uvicorn) en :${API_PORT}"
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE"
    nohup uvicorn src.api.main:app --host "$API_HOST" --port "$API_PORT" \
        >"$API_LOG" 2>&1 &
    echo $! > "$API_PID"
    wait_for_http "http://${API_HOST}:${API_PORT}/health" 30 "API"
}

start_ui() {
    if is_pid_alive "$UI_PID"; then
        ok "UI ya corriendo (pid $(cat "$UI_PID"))"
        return 0
    fi
    if curl -sS --max-time 2 "http://localhost:${UI_PORT}/" >/dev/null 2>&1; then
        warn "Puerto ${UI_PORT} ocupado por otro proceso; usando el existente"
        return 0
    fi
    log "Arrancando UI (streamlit) en :${UI_PORT}"
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE"
    nohup streamlit run src/ui/app.py \
        --server.port "$UI_PORT" \
        --server.headless true \
        --browser.gatherUsageStats false \
        >"$UI_LOG" 2>&1 &
    echo $! > "$UI_PID"
    wait_for_http "http://localhost:${UI_PORT}/" 30 "UI"
}

stop_all() {
    log "Deteniendo UI"
    if is_pid_alive "$UI_PID"; then
        kill "$(cat "$UI_PID")" 2>/dev/null && ok "UI detenida"
    else
        warn "UI no estaba corriendo"
    fi
    rm -f "$UI_PID"

    log "Deteniendo API"
    if is_pid_alive "$API_PID"; then
        kill "$(cat "$API_PID")" 2>/dev/null && ok "API detenida"
    else
        warn "API no estaba corriendo"
    fi
    rm -f "$API_PID"

    log "Deteniendo Qdrant"
    if docker ps --format '{{.Names}}' | grep -qx "$QDRANT_CONTAINER"; then
        docker stop "$QDRANT_CONTAINER" >/dev/null && ok "Qdrant detenida"
    else
        warn "Qdrant no estaba corriendo (o no es el contenedor sri-qdrant)"
    fi
}

status() {
    echo
    echo "${BOLD}== Estado Smart Tourism Engine ==${RESET}"
    if curl -sS --max-time 2 "http://localhost:${QDRANT_PORT}/collections" >/dev/null 2>&1; then
        local pt pi
        pt="$(count_qdrant_points destinations_text)"
        pi="$(count_qdrant_points destinations_image)"
        ok "Qdrant: ${QDRANT_PORT} (text=$pt, image=$pi)"
    else
        fail "Qdrant: no responde en ${QDRANT_PORT}"
    fi
    if curl -sS --max-time 2 "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
        ok "API: http://${API_HOST}:${API_PORT}/docs"
    else
        fail "API: no responde en ${API_PORT}"
    fi
    if curl -sS --max-time 2 "http://localhost:${UI_PORT}/" >/dev/null 2>&1; then
        ok "UI: http://localhost:${UI_PORT}/"
    else
        fail "UI: no responde en ${UI_PORT}"
    fi
    echo
}

# ─── flujo principal ──────────────────────────────────────────────────────

case "${1:-start}" in
    --stop|-s|stop)
        stop_all
        status
        exit 0
        ;;
    --status|status)
        status
        exit 0
        ;;
    --help|-h|help)
        sed -n '2,25p' "$0"
        exit 0
        ;;
esac

log "Verificando entorno"
if [[ ! -x "$VENV_PY" ]]; then
    fail "venv no encontrado en $PROJECT_DIR/venv. Crea el venv primero."
    exit 1
fi
ok "venv presente"

log "Levantando Qdrant"
ensure_qdrant || { fail "Qdrant no levanto; aborto."; exit 1; }

log "Verificando colecciones Qdrant"
pt="$(count_qdrant_points destinations_text)"
pi="$(count_qdrant_points destinations_image)"
if (( pt < 1 )); then
    warn "destinations_text vacia. Corre: source venv/bin/activate && python scripts/init_qdrant.py && python -m src.cli embed"
else
    ok "destinations_text: $pt puntos"
fi
if (( pi < 1 )); then
    warn "destinations_image vacia. Corre: source venv/bin/activate && python scripts/init_qdrant_images.py && python -m src.cli embed-images"
else
    ok "destinations_image: $pi puntos"
fi

log "Verificando SQLite"
reseed_sqlite_if_needed

log "Levantando API"
start_api || { fail "API no levanto; revisa $API_LOG"; exit 1; }

log "Levantando UI"
start_ui || { fail "UI no levanto; revisa $UI_LOG"; exit 1; }

status

echo "${BOLD}${GREEN}Listo.${RESET} Abre en tu navegador:"
echo
echo "    ${BOLD}http://localhost:${UI_PORT}/${RESET}"
echo
echo "Logs:"
echo "    API: tail -f $API_LOG"
echo "    UI:  tail -f $UI_LOG"
echo
echo "Para detener todo: ${BOLD}./start.sh --stop${RESET}"
