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
        st.error(f"Halaman ini gagal dimuat. Coba muat ulang; jika berulang, laporkan kode **{ref}** ke admin.")
        if is_admin_user:
            with st.expander("Detail teknis (admin)"):
                st.code(traceback.format_exc(), language="python")


_NAV_HOOK_JS = """
<script>
// On phones the sidebar overlays the page and Streamlit leaves it open after a
// navigation click, hiding the page that was just opened. Close it for the user.
const doc = window.parent.document;
if (!doc.__fptkNavHook) {
  doc.__fptkNavHook = true;
  doc.addEventListener("click", (e) => {
    if (!e.target.closest('[data-testid="stSidebarNavLink"]')) return;
    if (window.parent.innerWidth >= 768) return;
    setTimeout(() => {
      const btn = doc.querySelector('[data-testid="stSidebarCollapseButton"] button');
      if (btn) btn.click();
    }, 50);
  }, true);
}
</script>
"""


def install_mobile_nav_hook():
    import streamlit.components.v1 as components
    with st.container(key="fptk_navhook"):
        st.markdown("<style>.st-key-fptk_navhook{display:none}</style>", unsafe_allow_html=True)
        components.html(_NAV_HOOK_JS, height=0)
