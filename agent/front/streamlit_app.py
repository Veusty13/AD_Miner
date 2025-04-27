import os
import json
import streamlit as st
import requests
import openai
import tiktoken
from typing import Dict, List, Any

st.set_page_config(page_title="AD Miner - Interface", page_icon="🔍", layout="wide")

st.title("AD Miner - Catalogue des contrôles")

openai.api_key = os.getenv("OPENAI_API_KEY")
API_BASE = "http://localhost:8000"

MODEL_CONTEXT_LIMITS = {
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4o": 32768,
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384,
}


@st.cache_data(ttl=300)
def fetch_json(url: str):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300)
def get_available_models() -> List[str]:
    allowed = list(MODEL_CONTEXT_LIMITS.keys())
    try:
        models_data = openai.models.list().data
        available = {m.id for m in models_data}
        return [m for m in allowed if m in available]
    except Exception:
        return allowed


def get_model_max_tokens(model_id: str) -> int:
    return MODEL_CONTEXT_LIMITS.get(model_id, 0)


def get_controls_by_category() -> Dict[str, List[Dict[str, str]]]:
    data = fetch_json(f"{API_BASE}/controls/information/list")
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
        f"{API_BASE}/llm/prompt/{enc_task}",
        json=title,
        timeout=60,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.text


if "prompt_generated" not in st.session_state:
    st.session_state.prompt_generated = ""
if "llm_response" not in st.session_state:
    st.session_state.llm_response = ""

models = get_available_models() if openai.api_key else ["gpt-3.5-turbo"]
selected_model = st.sidebar.selectbox("Modèle LLM", models)
model_limit = get_model_max_tokens(selected_model)

prompt_tokens = 0
if st.session_state.prompt_generated:
    try:
        enc = tiktoken.encoding_for_model(selected_model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    prompt_tokens = len(enc.encode(st.session_state.prompt_generated))

st.sidebar.markdown(f"**Limite {selected_model}:** {model_limit} tokens")
st.sidebar.markdown(f"**Prompt actuel:** {prompt_tokens} tokens")

if model_limit > 1:
    default_max = min(1024, model_limit)
    max_tokens = st.sidebar.slider(
        "Max tokens de sortie",
        min_value=1,
        max_value=model_limit,
        value=default_max,
        step=256,
    )
else:
    st.sidebar.info(
        f"Modèle {selected_model} limité à {model_limit} token(s), pas de slider disponible."
    )
    max_tokens = model_limit

st.sidebar.header("Navigation")
controls_by_cat = get_controls_by_category()
selected_category = st.sidebar.selectbox("Catégorie", list(controls_by_cat.keys()))
controls_in_cat = controls_by_cat[selected_category]
selected_control = st.sidebar.selectbox(
    "Contrôle", [c["title"] for c in controls_in_cat]
)

if selected_control:
    try:
        ctrl_info = get_control_info(selected_control)
    except requests.HTTPError as e:
        st.error(f"Erreur API : {e}")
        st.stop()

    st.subheader(f"{ctrl_info['title']} - détails")
    with st.expander("Code source du contrôle"):
        st.code(ctrl_info.get("code", ""), language="python")

    col1, col2 = st.columns(2)
    col1.markdown(f"**Fichier** : `{ctrl_info.get('file_name','')}`")
    col2.markdown(f"**Catégorie** : `{ctrl_info.get('control_category','')}`")

    deps = ctrl_info.get("dependencies", {}) or {}
    if deps:
        st.divider()
        st.subheader("Dépendances")
        for path, data_dep in deps.items():
            with st.expander(os.path.basename(path)):
                st.markdown(f"`{path}`")
                imp = ", ".join(data_dep.get("imported_elements", [])) or "—"
                st.markdown(f"**Éléments importés :** {imp}")
                code_map = data_dep.get("code_map", {})
                if code_map:
                    tabs = st.tabs(list(code_map.keys()))
                    for tab, key in zip(tabs, code_map.keys()):
                        with tab:
                            st.code(code_map[key], language="python")
                else:
                    st.info("Pas de code source capturé.")

    st.divider()
    st.subheader("Résultats des requêtes Cypher")
    for rk in ctrl_info.get("requests_keys", []):
        st.markdown(f"**{rk}**")
        try:
            data = get_request_result(rk)
            st.json(data, expanded=False)
        except requests.HTTPError as e:
            st.error(f"Erreur API : {e}")
    st.divider()
    st.subheader("Interaction LLM - Génération et exécution de prompt")
    task_key = st.radio(
        "Tâche :",
        options=[
            ("methodology", "🛠️ Méthodologie"),
            ("diagnose", "🔎 Diagnostic"),
            ("remediation", "💊 Remédiation"),
        ],
        format_func=lambda o: o[1],
        horizontal=True,
    )[0]

    if st.button("Générer le prompt"):
        with st.spinner("Génération du prompt…"):
            try:
                st.session_state.prompt_generated = generate_prompt(
                    task_key, selected_control
                )
                st.session_state.llm_response = ""
            except requests.HTTPError as e:
                st.error(f"Erreur API : {e}")

    if st.session_state.prompt_generated:
        st.text_area(
            "Prompt généré :", value=st.session_state.prompt_generated, height=200
        )
        if st.button("Envoyer au LLM"):
            with st.spinner("Appel à l'API OpenAI…"):
                try:
                    resp = openai.chat.completions.create(
                        model=selected_model,
                        messages=[
                            {
                                "role": "user",
                                "content": st.session_state.prompt_generated,
                            }
                        ],
                        temperature=0.7,
                        max_tokens=max_tokens,
                    )
                    st.session_state.llm_response = resp.choices[0].message.content
                except Exception as e:
                    st.error(f"Erreur OpenAI : {e}")

    if st.session_state.llm_response:
        st.subheader("Réponse du LLM")
        st.text_area("", value=st.session_state.llm_response, height=300)
