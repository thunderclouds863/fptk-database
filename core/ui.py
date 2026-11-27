# core/ui.py
"""Shared UI chrome: global style tweaks and the page error boundary.
Colours, fonts and heading sizes live in .streamlit/config.toml ([theme])."""
import logging
import traceback
import uuid

import streamlit as st

log = logging.getLogger("fptk")

_BASE_CSS = """
<style>
/* Tighter top spacing; Streamlit's default leaves ~6rem above the title. */
.block-container { padding-top: 2.5rem; padding-bottom: 3rem; }
@media (max-width: 640px) {
  .block-container { padding-top: 3.5rem; padding-left: 1rem; padding-right: 1rem; }
}
/* Metrics: labels are secondary, values carry the weight. */
[data-testid="stMetricLabel"] p { color: #5b6472; font-size: 0.85rem; }
[data-testid="stMetricValue"] { font-size: 1.75rem; font-weight: 600; }
/* Sidebar account block */
[data-testid="stMarkdownContainer"] p.acct-name { font-weight: 600; color: #1f2430; margin: 0; line-height: 1.3; font-size: 0.95rem; }
[data-testid="stMarkdownContainer"] p.acct-meta { color: #5b6472; font-size: 0.8rem; margin: 0.15rem 0 0.5rem; line-height: 1.4; }
.caps-hint { color: #8a5a00; background: #fff6e0; border: 1px solid #f0d9a8; border-radius: 4px;
             font-size: 0.8rem; padding: 0.2rem 0.5rem; margin-top: 0.35rem; display: inline-block; }
.caps-hint[hidden] { display: none; }
/* Streamlit's "Press Enter to submit" note sits where the hint goes; hide it while the hint shows. */
[data-testid="stTextInput"]:has(.caps-hint:not([hidden])) [data-testid="InputInstructions"] { display: none; }
/* Heading permalink icons add noise in an internal tool. */
[data-testid="stHeaderActionElements"] { display: none; }
/* Phones: keep KPI rows two-up instead of one long column. */
@media (max-width: 640px) {
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) {
    flex-direction: row; flex-wrap: wrap; row-gap: 0.75rem;
  }
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) > [data-testid="stColumn"] {
    flex: 1 1 calc(50% - 1rem); min-width: calc(50% - 1rem); width: calc(50% - 1rem);
  }
  [data-testid="stMetricValue"] { font-size: 1.4rem; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
</style>
"""

_AUTH_CSS = """
<style>
.block-container { max-width: 420px; padding-top: 12vh; }
@media (max-width: 640px) { .block-container { padding-top: 2.5rem; } }
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"] { display: none; }
[data-testid="stMarkdownContainer"] p.auth-sub { color: #5b6472; margin: -0.5rem 0 0.75rem; font-size: 0.95rem; }
[data-testid="stForm"] { background: #ffffff; padding: 1.5rem; }
@media (max-width: 640px) { [data-testid="stForm"] { padding: 1rem; } }
.auth-env { display: inline-block; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.02em;
            color: #5b6472; background: #eef0f3; border-radius: 4px; padding: 0.1rem 0.45rem; }
</style>
"""


def apply_base_styles():
    st.markdown(_BASE_CSS, unsafe_allow_html=True)


def apply_auth_styles():
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)


def run_page(render, is_admin_user=False):
    """Render a page; on an unexpected error, log the traceback server-side and show
    a short message with a reference id. Admins can expand the technical detail."""
    try:
        render()
    except Exception as exc:  # noqa: BLE001 - page boundary
        # Streamlit control-flow exceptions (st.stop/st.rerun/switch_page) must pass through.
        if type(exc).__module__.startswith("streamlit"):
            raise
        ref = uuid.uuid4().hex[:8]
        log.exception("Page error ref=%s", ref)
        from sqlalchemy.exc import OperationalError, InterfaceError
        if isinstance(exc, (OperationalError, InterfaceError)):
            st.error("Database sedang tidak dapat dihubungi, jadi halaman ini belum bisa dimuat. "
                     f"Coba lagi beberapa saat. Kode referensi: **{ref}**.")
            return
        st.error(f"Halaman ini gagal dimuat. Coba muat ulang; jika berulang, laporkan kode **{ref}** ke admin.")
        if is_admin_user:
            with st.expander("Detail teknis (admin)"):
                st.code(traceback.format_exc(), language="python")


_CLIENT_HOOKS_JS = """
<script>
const doc = window.parent.document;
const win = window.parent;
// Listeners belong to this iframe; the browser stops running them once the iframe is
// removed (e.g. the login screen's hooks after signing in). So each hooks iframe
// replaces the previous handlers instead of installing them only once.
const prev = doc.__fptkHooks;
if (prev) prev.forEach(([type, fn]) => doc.removeEventListener(type, fn, true));
const handlers = [];
const on = (type, fn) => { doc.addEventListener(type, fn, true); handlers.push([type, fn]); };

// 1) Phones: the sidebar overlays the page and Streamlit leaves it open after a
//    navigation click, hiding the page that was just opened. Close it.
on("click", (e) => {
  if (!e.target.closest('[data-testid="stSidebarNavLink"]')) return;
  if (win.innerWidth >= 768) return;
  win.setTimeout(() => {
    const btn = doc.querySelector('[data-testid="stSidebarCollapseButton"] button');
    if (btn) btn.click();
  }, 50);
});

// 2) Caps Lock hint under password fields (also when the eye toggle shows the text).
const isPw = (el) => el && el.tagName === "INPUT" &&
  (el.type === "password" || /password/.test(el.getAttribute("autocomplete") || ""));
const hintFor = (input) => {
  const box = input.closest('[data-testid="stTextInput"]');
  if (!box) return null;
  let hint = box.querySelector(".caps-hint");
  if (!hint) {
    hint = doc.createElement("div");
    hint.className = "caps-hint";
    hint.setAttribute("role", "status");
    hint.setAttribute("aria-live", "polite");
    hint.textContent = "Caps Lock aktif";
    hint.hidden = true;
    box.appendChild(hint);
  }
  return hint;
};
const update = (e) => {
  if (!isPw(e.target) || typeof e.getModifierState !== "function") return;
  const hint = hintFor(e.target);
  if (hint) hint.hidden = !e.getModifierState("CapsLock");
};
on("keydown", update);
on("keyup", update);
on("focusout", (e) => {
  if (!isPw(e.target)) return;
  const hint = hintFor(e.target);
  if (hint) hint.hidden = true;
});
doc.__fptkHooks = handlers;
</script>
"""


def install_client_hooks():
    """Small client-side helpers (mobile nav auto-close, Caps Lock hint).
    Runs in a hidden component iframe that reaches the same-origin parent page."""
    import streamlit.components.v1 as components
    with st.container(key="fptk_hooks"):
        st.markdown("<style>.st-key-fptk_hooks{display:none}</style>", unsafe_allow_html=True)
        components.html(_CLIENT_HOOKS_JS, height=0)


def set_flash(key, message, level="success"):
    """Queue a message that survives the st.rerun() that follows a successful save."""
    st.session_state.setdefault("_flash", {}).setdefault(key, []).append((level, message))


def show_flash(key):
    for level, message in st.session_state.get("_flash", {}).pop(key, []):
        getattr(st, level)(message)
