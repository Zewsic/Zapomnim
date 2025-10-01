import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Admin Dashboard",
    page_icon="📊",
    layout="wide",
)

from datetime import datetime

import pandas as pd
import requests

"""
Streamlit admin dashboard for the FastAPI backend defined in admin.py.
Fetches data from /admin endpoints and presents them in a friendly UI.
Run with:
    streamlit run streamlit_admin_dashboard.py
"""

# ---------------------------------------------------------------------------
# Sidebar — configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("⚙️ Настройки")
    base_url = st.text_input("Базовый URL API", value="http://localhost:8000")
    auth_token = st.text_input("Bearer-токен (если нужен)", type="password")
    st.markdown("---")
    refresh = st.button("🔄 Обновить данные")
    st.caption("Данные кешируются на 60 секунд для снижения нагрузки на API.")

headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}


# ---------------------------------------------------------------------------
# Helper for GET requests with Streamlit cache
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def fetch_json(base: str, endpoint: str, http_headers: dict[str, str] | None = None):
    """Return parsed JSON data or None on error."""
    try:
        url = f"{base}{endpoint}"
        r = requests.get(url, headers=http_headers or {}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as err:  # noqa: BLE001
        st.error(f"Ошибка запроса {endpoint}: {err}")
        return None


# Manual cache invalidation on button press
if refresh:
    fetch_json.clear()

# ---------------------------------------------------------------------------
# Fetch all datasets in one go so tabs switch instantly
# ---------------------------------------------------------------------------

endpoints = {
    "stats": "/admin/stats",
    "users": "/admin/users",
    "metrics": "/admin/metrics",
    "top": "/admin/top",
}

data = {
    key: fetch_json(base_url, ep, headers)
    for key, ep in endpoints.items()
}

stats = data["stats"]
users = data["users"]
metrics = data["metrics"]
tops = data["top"]

# ---------------------------------------------------------------------------
# Build UI — four logical tabs
# ---------------------------------------------------------------------------

tab_overview, tab_users, tab_metrics, tab_top = st.tabs([
    "📈 Обзор",
    "👥 Пользователи",
    "📊 Метрики",
    "🏆 Топ-лист",
])

# ---------------------------------------------------------------------------
# Overview tab
# ---------------------------------------------------------------------------

with tab_overview:
    if stats:
        st.header("Общая статистика", divider="gray")

        # Users ----------------------------------------------------------------
        st.subheader("Пользователи")
        cols = st.columns(4)
        cols[0].metric("Всего", stats["users"]["total"], border=True)
        cols[1].metric("Активных", stats["users"]["active"], border=True)
        cols[2].metric("Новых сегодня", stats["users"]["new_day"], border=True)
        cols[3].metric("Новых за неделю", stats["users"]["new_week"], border=True)

        # Messages --------------------------------------------------------------
        st.subheader("Сохранённые сообщения")
        sm = stats["saved_messages"]
        cols = st.columns(5)
        cols[0].metric("Всего", sm["total"], border=True)
        cols[1].metric("Сегодня", sm["day"], border=True)
        cols[2].metric("За неделю", sm["week"], border=True)
        cols[3].metric("За месяц", sm["month"], border=True)
        avg_text = f"{sm['avg_per_user_day']:.2f}" if sm["avg_per_user_day"] else "—"
        cols[4].metric("Среднее/польз. (день)", avg_text, border=True)
        st.caption(
            f"Среднее за месяц на пользователя: {sm['avg_per_user_month']:.2f}"
            if sm["avg_per_user_month"]
            else "—",
        )

        # Cost ------------------------------------------------------------------
        st.subheader("Стоимость (USD)")
        cost = stats["cost"]
        cols = st.columns(3)
        cols[0].metric("Всего", f"{cost['total']:.4f}", border=True)
        cols[1].metric("Сегодня", f"{cost['day']:.4f}", border=True)
        cols[2].metric("За месяц", f"{cost['month']:.4f}", border=True)

        st.caption(
            "Последнее обновление: " + datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        )
    else:
        st.info("Нет данных для отображения. Проверьте настройки в сайдбаре.")

# ---------------------------------------------------------------------------
# Users tab
# ---------------------------------------------------------------------------

with tab_users:
    if users:
        st.header("Пользователи", divider="gray")
        df_users = pd.json_normalize(users)

        # Human-friendly datetime columns
        dt_cols = [
            "registered_at",
            "last_active_at",
            "subscription_until",
        ]
        for c in dt_cols:
            if c in df_users.columns:
                df_users[c] = pd.to_datetime(df_users[c]).dt.strftime("%Y-%m-%d %H:%M")

        st.dataframe(df_users, use_container_width=True, height=600)
    else:
        st.info("Нет данных пользователей.")

# ---------------------------------------------------------------------------
# Metrics tab
# ---------------------------------------------------------------------------

with tab_metrics:
    if metrics:
        st.header("Метрики", divider="gray")

        # Flatten nested MetricInfo objects for nicer table
        flat = []
        for name, body in metrics.items():
            for scope in ("day", "month", "total"):
                row = body[scope]
                flat.append(
                    {
                        "metric": name,
                        "scope": scope,
                        "count": row["count"],
                        "users": row["users"],
                        "input_tokens": row["input_tokens"],
                        "output_tokens": row["output_tokens"],
                        "audio_duration": row["audio_duration"],
                        "cost_usd": row["cost_usd"],
                    },
                )
        df_metrics = pd.DataFrame(flat)
        st.dataframe(df_metrics, use_container_width=True, height=600)
    else:
        st.info("Нет данных метрик.")

# ---------------------------------------------------------------------------
# Top tab
# ---------------------------------------------------------------------------

with tab_top:
    if tops:
        st.header("Топ-пользователи", divider="gray")

        col1, col2, col3 = st.columns(3)
        col1.subheader("По сообщениям")
        df_msg = pd.json_normalize(tops["messages"])
        col1.dataframe(df_msg, use_container_width=True, height=350)

        col2.subheader("По метрикам")
        df_met = pd.json_normalize(tops["metrics"])
        col2.dataframe(df_met, use_container_width=True, height=350)

        col3.subheader("По расходам (USD)")
        df_cost = pd.json_normalize(tops["cost"])
        col3.dataframe(df_cost, use_container_width=True, height=350)
    else:
        st.info("Нет данных топ-листов.")
