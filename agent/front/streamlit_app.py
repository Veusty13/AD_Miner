import os
import streamlit as st
import requests
from typing import Dict, List, Any

API_BASE = "http://localhost:8000"


@st.cache_data(ttl=60)
def fetch_json(url: str):
    """GET -> JSON avec cache 60 s."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_controls_by_category() -> Dict[str, List[Dict[str, str]]]:
    data: List[Dict[str, str]] = fetch_json(f"{API_BASE}/controls/information/list")
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for entry in data:
        grouped.setdefault(entry["control_category"], []).append(entry)
    for cat in grouped:
        grouped[cat].sort(key=lambda x: x["title"].lower())
    return dict(sorted(grouped.items()))


def get_control_info(title: str) -> Dict[str, Any]:
    enc = requests.utils.quote(title, safe="")
    return fetch_json(f"{API_BASE}/controls/information/{enc}")


def get_request_result(request_key: str) -> Dict[str, Any]:
    return fetch_json(f"{API_BASE}/controls/information/requests/{request_key}")


def generate_prompt(task: str, title: str) -> str:
    enc_task = requests.utils.quote(task, safe="")
    resp = requests.post(
        f"{API_BASE}/llm/ask/{enc_task}",
        json=title,
        timeout=60,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.text


st.set_page_config(page_title="AD Miner - Interface", page_icon="🔍", layout="wide")

st.title("AD Miner - Catalogue des contrôles")

controls_by_cat = get_controls_by_category()

st.sidebar.header("Navigation")
selected_category = st.sidebar.selectbox(
    "Catégorie", list(controls_by_cat.keys()), key="category_select"
)

controls_in_cat = controls_by_cat[selected_category]
control_titles = [c["title"] for c in controls_in_cat]
selected_control = st.sidebar.selectbox(
    "Contrôle", control_titles, key="control_select"
)

if selected_control:
    try:
        ctrl_info = get_control_info(selected_control)
    except requests.HTTPError as e:
        st.error(f"Erreur API : {e}")
        st.stop()

    st.subheader(f"{ctrl_info['title']} - détails")

    with st.expander("Code source du contrôle"):
        st.code(ctrl_info["code"], language="python")

    col_meta1, col_meta2 = st.columns(2)
    col_meta1.markdown(f"**Fichier** : `{ctrl_info['file_name']}`")
    col_meta2.markdown(f"**Catégorie** : `{ctrl_info['control_category']}`")

    deps: Dict[str, Any] = ctrl_info.get("dependencies", {})
    if deps:
        st.divider()
        st.subheader("Dépendances")
        for dep_path, dep_data in deps.items():
            short_name = os.path.basename(dep_path)
            with st.expander(short_name, expanded=False):
                st.markdown(f"`{dep_path}`")
                imported = ", ".join(dep_data.get("imported_elements", [])) or "—"
                st.markdown(f"**Éléments importés :** {imported}")

                code_map: Dict[str, str] = dep_data.get("code_map", {})
                if not code_map:
                    st.info("Pas de code source capturé pour cette dépendance.")
                else:
                    tab_names = list(code_map.keys())
                    tabs = st.tabs(tab_names)
                    for tab, elem_name in zip(tabs, tab_names):
                        with tab:
                            st.code(code_map[elem_name], language="python")

    st.divider()
    st.subheader("Résultats des requêtes Cypher")
    for req_key in ctrl_info.get("requests_keys", []):
        with st.expander(req_key):
            try:
                data = get_request_result(req_key)
                st.json(data, expanded=False)
            except requests.HTTPError as e:
                st.error(f"Erreur API : {e}")

    st.divider()
    st.subheader("Interaction LLM - Génération de prompt")

    task_key = st.radio(
        "Tâche :",
        options=[
            ("methodology", "🛠️ Méthodologie"),
            ("diagnose", "🔎 Diagnostic"),
            ("remediation", "💊 Remédiation"),
        ],
        format_func=lambda o: o[1],
        horizontal=True,
        key="llm_task_radio",
    )[0]

    if st.button("Générer le prompt", type="primary"):
        with st.spinner("Génération du prompt…"):
            try:
                prompt = generate_prompt(task_key, selected_control)
                st.text_area(
                    "Prompt généré :", prompt, height=350, label_visibility="collapsed"
                )
            except requests.HTTPError as e:
                st.error(f"Erreur API : {e}")
