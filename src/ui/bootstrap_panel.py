"""Streamlit panel that surfaces the bootstrap pipeline and reset actions.

Splits the UI into two reusable pieces:

* :func:`render_bootstrap_banner` — a thin warning shown across every
  tab whenever the system is not yet queryable. Lets the user jump
  to the system tab without losing the current context.
* :func:`render_bootstrap_tab` — the full panel with status, progress
  bar, log tail and the three action buttons (Initialize, Reset
  indexes, Reset everything).

While a bootstrap is running the panel reruns itself every two seconds
so the progress bar moves without manual refreshes. Polling is bounded
to the bootstrap tab; other tabs read the cached needed/status pair
once per render to keep the latency low.
"""
from __future__ import annotations

import time
from typing import Any

import httpx


def _api_get(api_url: str, path: str) -> dict[str, Any] | None:
    try:
        response = httpx.get(f"{api_url}{path}", timeout=5.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


def _api_post(api_url: str, path: str) -> tuple[bool, dict[str, Any] | None]:
    try:
        response = httpx.post(f"{api_url}{path}", timeout=10.0)
        response.raise_for_status()
        return True, response.json()
    except httpx.HTTPError as exc:
        return False, {"error": str(exc)}


def bootstrap_needed(api_url: str) -> tuple[bool, list[str]]:
    payload = _api_get(api_url, "/bootstrap/needed")
    if payload is None:
        # If the API is unreachable we cannot tell; assume needed so the
        # user sees the banner instead of a silently broken UI.
        return True, ["api unreachable"]
    return bool(payload.get("needed", False)), list(payload.get("reasons", []))


def bootstrap_status(api_url: str) -> dict[str, Any] | None:
    return _api_get(api_url, "/bootstrap/status")


def render_bootstrap_banner(st, api_url: str) -> bool:
    """Show a warning banner if the system is not ready.

    Returns ``True`` when the system is ready and the rest of the page
    can render normally. When ``False``, the caller should consider
    blocking the rest of the UI (e.g. skip the search tabs).
    """
    needed, reasons = bootstrap_needed(api_url)
    if not needed:
        return True
    reason_text = ", ".join(reasons) if reasons else "missing data"
    st.warning(
        "Sistema no inicializado ("
        + reason_text
        + "). Abre el tab 'Sistema' y pulsa 'Inicializar sistema'."
    )
    return False


def _phase_lines(phases: list[dict[str, str]], current_index: int) -> list[str]:
    lines: list[str] = []
    for idx, phase in enumerate(phases):
        if idx < current_index:
            marker = "[OK]"
        elif idx == current_index:
            marker = "[..]"
        else:
            marker = "[  ]"
        lines.append(f"{marker} {phase.get('label') or phase.get('key')}")
    return lines


def render_bootstrap_tab(st, api_url: str) -> None:
    """Full panel: status + progress + actions."""
    st.subheader("Estado del sistema")

    needed, reasons = bootstrap_needed(api_url)
    if needed:
        st.warning(
            "Sistema no inicializado. Razones: " + (", ".join(reasons) or "n/a")
        )
    else:
        st.success("Sistema listo para responder consultas.")

    snap = bootstrap_status(api_url) or {}
    status = snap.get("status", "idle")
    phases = snap.get("phases", []) or []
    phase_index = int(snap.get("phase_index", -1))
    percent = float(snap.get("percent", 0.0))
    message = snap.get("message") or ""
    error = snap.get("error")
    log_tail = snap.get("log", []) or []

    if status == "running":
        st.info(f"Bootstrap en curso: {snap.get('phase_label') or ''}")
        st.progress(min(max(percent / 100.0, 0.0), 1.0))
        if message:
            st.caption(message)
        with st.expander("Fases", expanded=True):
            for line in _phase_lines(phases, phase_index):
                st.text(line)
        with st.expander("Log (ultimas lineas)", expanded=False):
            st.code("\n".join(log_tail[-15:]) or "(vacio)")
        # Self-refresh while running so the user sees real progress.
        time.sleep(2)
        st.rerun()
        return

    if status == "done":
        st.success("Ultimo bootstrap finalizado correctamente.")
        with st.expander("Log del ultimo bootstrap", expanded=False):
            st.code("\n".join(log_tail) or "(vacio)")
    elif status == "error":
        st.error(f"Bootstrap fallido: {error or 'error desconocido'}")
        with st.expander("Log del bootstrap fallido", expanded=True):
            st.code("\n".join(log_tail) or "(vacio)")

    st.divider()
    st.subheader("Acciones")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Inicializar sistema**")
        st.caption(
            "Ejecuta la pipeline completa: crawl (si no hay raw) -> "
            "ingest -> index -> popularity -> Qdrant -> embeddings."
        )
        if st.button("Inicializar sistema", type="primary", use_container_width=True):
            ok, payload = _api_post(api_url, "/bootstrap/start")
            if ok:
                st.success(f"Lanzado: {payload}")
                st.rerun()
            else:
                st.error(f"No se pudo arrancar: {payload}")

    with col2:
        st.markdown("**Limpiar indices**")
        st.caption(
            "Borra colecciones Qdrant + index.pkl. Mantiene el corpus raw "
            "y el JSONL, por lo que el bootstrap solo reindexa (rapido)."
        )
        confirm_indexes = st.checkbox(
            "Confirmo que quiero borrar indices", key="confirm_indexes"
        )
        if st.button(
            "Limpiar indices",
            disabled=not confirm_indexes,
            use_container_width=True,
        ):
            ok, payload = _api_post(api_url, "/bootstrap/reset/indexes")
            if ok:
                st.success(
                    "Indices borrados: "
                    + ", ".join(payload.get("collections_dropped", []) or ["(ninguno)"])
                )
                st.session_state["confirm_indexes"] = False
                st.rerun()
            else:
                st.error(f"Error: {payload}")

    with col3:
        st.markdown("**Limpiar TODO**")
        st.caption(
            "Borra colecciones Qdrant + index + JSONL + SQLite + raw. "
            "El siguiente bootstrap crawlea desde cero (~20-30 min)."
        )
        confirm_token = st.text_input(
            "Escribe BORRAR para confirmar",
            key="confirm_token",
            placeholder="BORRAR",
        )
        if st.button(
            "Limpiar todo",
            disabled=confirm_token != "BORRAR",
            use_container_width=True,
        ):
            ok, payload = _api_post(api_url, "/bootstrap/reset/all")
            if ok:
                st.success(
                    "Todo limpio. Colecciones: "
                    + ", ".join(payload.get("collections_dropped", []) or ["(ninguna)"])
                    + ". Archivos: "
                    + str(len(payload.get("files_removed", [])))
                    + ". Directorios vaciados: "
                    + ", ".join(payload.get("directories_emptied", []) or ["(ninguno)"])
                )
                st.session_state["confirm_token"] = ""
                st.rerun()
            else:
                st.error(f"Error: {payload}")
