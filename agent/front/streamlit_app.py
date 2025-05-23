import os
import streamlit as st
import requests
import tiktoken
from typing import Dict, List, Any
import difflib
import pathlib
from streamlit_ace import st_ace  # ✅ Nouvel import pour l'éditeur enrichi

st.set_page_config(page_title="AD Miner - Interface", page_icon="🔍", layout="wide")

st.title("AD Miner - Catalogue des contrôles")

if "prompt_generated" not in st.session_state:
    st.session_state.prompt_generated = ""

API_BASE = "http://localhost:8000"
SOURCE_DIR = "../bloodhound-automation/data/goadV2/"
MODIFIED_DIR = "../bloodhound-automation/data/goadV2_1/"


@st.cache_data(ttl=300)
def fetch_json(url: str):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


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


def generate_prompt(
    task: str, title: str, source_folder: str, destination_folder: str
) -> str:
    enc_task = requests.utils.quote(task, safe="")
    resp = requests.post(
        f"{API_BASE}/llm/prompt/{enc_task}",
        json={
            "control_title": title,
            "source_folder": source_folder,
            "destination_folder": destination_folder,
        },
        timeout=60,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.text


def get_file_diff(file1_path: pathlib.Path, file2_path: pathlib.Path) -> str:
    with open(file1_path, "r", encoding="utf-8", errors="ignore") as f1, open(
        file2_path, "r", encoding="utf-8", errors="ignore"
    ) as f2:
        f1_lines = f1.readlines()
        f2_lines = f2.readlines()

    diff = difflib.unified_diff(
        f1_lines,
        f2_lines,
        fromfile=str(file1_path.name),
        tofile=str(file2_path.name),
        lineterm="",
    )
    return "".join(diff)


def display_diffs(source_folder, destination_folder):
    st.markdown("## 📝 Comparaison des fichiers `.json` contenant `concat`")

    def get_concat_json_files(folder_path):
        return {
            f.name: f
            for f in pathlib.Path(folder_path).glob("*.json")
            if f.is_file() and "concat" in f.name.lower()
        }

    source_files = get_concat_json_files(source_folder)
    dest_files = get_concat_json_files(destination_folder)

    all_files = sorted(set(source_files) | set(dest_files))
    modified_files = []
    identical_files = []
    missing_in_dest = []
    missing_in_source = []

    for file_name in all_files:
        f1 = source_files.get(file_name)
        f2 = dest_files.get(file_name)

        if not f1:
            missing_in_source.append(file_name)
        elif not f2:
            missing_in_dest.append(file_name)
        else:
            diff = get_file_diff(f1, f2)
            if diff:
                modified_files.append((file_name, diff))
            else:
                identical_files.append(file_name)

    st.markdown("### 📊 Résumé")
    st.write(f"✅ Identiques : {len(identical_files)}")
    st.write(f"⚠️ Modifiés : {len(modified_files)}")
    st.write(f"❌ Absents du dossier destination : {len(missing_in_dest)}")
    st.write(f"❌ Absents du dossier source : {len(missing_in_source)}")

    if modified_files:
        st.markdown("### 🔍 Fichiers modifiés")
        tabs = st.tabs([f for f, _ in modified_files])
        for tab, (file_name, diff_text) in zip(tabs, modified_files):
            with tab:
                st.code(diff_text, language="diff")
    else:
        st.success("✅ Aucun fichier modifié.")

    if missing_in_dest:
        with st.expander("❌ Fichiers manquants dans le dossier destination"):
            st.write(missing_in_dest)

    if missing_in_source:
        with st.expander("❌ Fichiers manquants dans le dossier source"):
            st.write(missing_in_source)


controls_by_cat = get_controls_by_category()
selected_category = st.sidebar.selectbox("Catégorie", list(controls_by_cat.keys()))
controls_in_cat = controls_by_cat[selected_category]
selected_control = st.sidebar.selectbox(
    "Contrôle", [c["title"] for c in controls_in_cat]
)

st.sidebar.markdown("### 📂 Dossiers à utiliser")

source_folder = st.sidebar.text_input(
    "Chemin du dossier source", value="../bloodhound-automation/data/goadV2/"
)
destination_folder = st.sidebar.text_input(
    "Chemin du dossier destination", value="../bloodhound-automation/data/goadV2_1/"
)

if st.sidebar.button("📦 Dézipper les archives ZIP"):
    try:
        resp = requests.post(
            f"{API_BASE}/folders/unzip",
            json={
                "source_folder": source_folder,
                "destination_folder": destination_folder,
            },
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        st.sidebar.success(result.get("message", "Archives dézippées avec succès."))
    except Exception as e:
        st.sidebar.error(f"Erreur : {e}")

if st.sidebar.button("🧹 Nettoyer les dossiers"):
    try:
        resp = requests.post(
            f"{API_BASE}/folders/clear",
            json={
                "source_folder": source_folder,
                "destination_folder": destination_folder,
            },
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        st.sidebar.success(result.get("message", "Dossiers nettoyés avec succès."))
    except Exception as e:
        st.sidebar.error(f"Erreur : {e}")

if st.sidebar.button("🧬 Concaténer les JSON"):
    try:
        resp = requests.post(
            f"{API_BASE}/folders/concat",
            json={"source_folder": source_folder},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        st.sidebar.success(result.get("message", "Fichiers concaténés avec succès."))
    except Exception as e:
        st.sidebar.error(f"Erreur lors de la concaténation : {e}")


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
    st.subheader("Interaction LLM - Génération de prompt")
    task_key = st.radio(
        "Tâche :",
        options=[
            ("methodology", "🛠️ Méthodologie"),
            ("diagnose", "🔎 Diagnostic"),
            ("remediation", "💊 Remédiation"),
            ("sanitize", "🧼 Assainir"),
            ("free", "🕊️ Mode Libre"),
        ],
        format_func=lambda o: o[1],
        horizontal=True,
    )[0]

    if selected_control and task_key:
        try:
            with st.spinner("Génération du prompt…"):
                st.session_state.prompt_generated = generate_prompt(
                    task_key, selected_control, source_folder, destination_folder
                )
        except requests.HTTPError as e:
            st.error(f"Erreur API : {e}")

if st.session_state.prompt_generated:
    st.text_area("Prompt généré :", value=st.session_state.prompt_generated, height=200)
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        prompt_tokens = len(enc.encode(st.session_state.prompt_generated))
        st.sidebar.markdown(f"**Prompt actuel :** {prompt_tokens} tokens")
    except Exception:
        st.sidebar.warning("Erreur lors du calcul des tokens.")

    st.markdown(
        "👉 Copier le prompt généré et le coller [ChatGPT](https://chat.openai.com/) ou un autre outil."
    )

code = st_ace(
    placeholder="Colle ici ton code Python...",
    language="python",
    theme="monokai",
    keybinding="vscode",
    font_size=14,
    height=300,
    show_gutter=True,
    show_print_margin=False,
    wrap=True,
    auto_update=True,
)

if st.button("Exécuter le code"):
    with st.expander("Résultat de l'exécution"):
        try:
            resp = requests.post(f"{API_BASE}/llm/code/execute", json=code, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            st.code(data.get("stdout", ""), language="text")
            if data.get("stderr"):
                st.error(f"stderr: {data['stderr']}")
            if data.get("exception"):
                st.error(f"Exception: {data['exception']}")
        except Exception as e:
            st.error(f"Erreur lors de l'appel API : {e}")

if st.sidebar.button("🧾 Comparer les fichiers (diff)"):
    display_diffs(source_folder, destination_folder)
