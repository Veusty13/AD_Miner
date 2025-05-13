from pydantic import BaseModel
from typing import List, Dict, Mapping, Sequence, Any, Pattern
from enum import Enum
import json
import math
import re
from fastapi import HTTPException
from typing import Optional

ALL_CONTROLS_INFO_JSON = "agent/llm_assets/all_controls_info.json"
ALL_REQUESTS_RESULTS_JSON = "agent/llm_assets/requests_results.json"


class Dependency(BaseModel):
    imported_elements: List[str]
    code_map: Dict[str, str]


class ControlCategory(str, Enum):
    Kerberos = "Kerberos"
    Passwords = "Passwords"
    Misc = "Misc"
    Permissions = "Permissions"


class ControlInfo(BaseModel):
    title: str
    file_name: str
    control_category: ControlCategory
    code: str
    dependencies: Dict[str, Dependency]
    requests_keys: List[str]


class GetListControlsOutput(BaseModel):
    control_category: ControlCategory
    title: str


class RequestResult(BaseModel):
    name: str
    request: str
    request_key: str
    result: List[Any]
    is_a_write_request: str | None = None
    scope_query: str | None = None
    is_a_gds_request: str | None = None
    create_gds_graph: str | None = None
    gds_request: str | None = None
    drop_gds_graph: str | None = None
    reverse_path: bool | None = None
    _comment: str | None = None
    _comment_2: str | None = None
    _comment_3: str | None = None


class DefaultRequestResult(BaseModel):
    request_key: str
    result: Any


class LLMTask(Enum):
    methodology = "methodology"
    diagnose = "diagnose"
    remediation = "remediation"
    sanitize = "sanitize"


class PromptRequestModel(BaseModel):
    control_title: str
    source_folder: Optional[str] = None
    destination_folder: Optional[str] = None


class FolderRequest(BaseModel):
    source_folder: str
    destination_folder: str


PROMPT_TEMPLATES = {
    LLMTask.methodology: """
Tu es un expert en cybersécurité spécialisé en Active Directory. Explique de manière claire la **méthodologie** utilisée dans le contrôle suivant, issu du projet AD MINER.

Les informations du contrôle sont :

{control_info}

Voici également les résultats des requêtes Cypher associées :

{requests_results}

Détaille :
- Quel est le but du contrôle ?
- Quelles entités Active Directory sont impliquées ?
- Comment les requêtes Cypher analysent-elles le graphe ?
- Quelle logique de détection est utilisée ?
Utilise un vocabulaire simple mais précis, adapté à un analyste sécurité.
""",
    LLMTask.diagnose: """
Tu es un analyste cybersécurité chargé de diagnostiquer une infrastructure Active Directory à partir des résultats d'un contrôle automatisé AD MINER.

Les informations du contrôle sont :

{control_info}

Voici également les résultats des requêtes Cypher associées :

{requests_results}

À partir de ces éléments, produis un **diagnostic clair** :
- Y a-t-il des failles ou mauvaises configurations détectées ?
- Quels objets ou relations Active Directory sont concernés ?
- Quelle est la gravité potentielle ?
- Quelles sont les conséquences possibles pour la sécurité ?
Sois rigoureux et précis, comme si tu rédigeais un rapport d'audit professionnel.
""",
    LLMTask.remediation: """
Tu es consultant en cybersécurité. Propose une **remédiation concrète** suite à l'exécution du contrôle suivant sur une infrastructure Active Directory.

Les informations du contrôle sont :

{control_info}

Voici également les résultats des requêtes Cypher associées :

{requests_results}

Ta tâche :
- Identifier les faiblesses ou problèmes mis en évidence.
- Proposer une ou plusieurs actions correctives précises.
- Donner des exemples de commandes PowerShell ou de bonnes pratiques de configuration si pertinent.
- Ajouter des recommandations pour la prévention à long terme.

Le style doit être clair, pragmatique, et directement applicable en entreprise.
""",
    LLMTask.sanitize: """
Tu trouveras en pièces jointes des extractions SharpHound d’une infrastructure Active Directory.

📄 Informations disponibles :
- Le code source d’un contrôle de sécurité Active Directory
- Les résultats Cypher associés à ce contrôle :

{control_info}

{requests_results}

🎯 Objectif :
Analyser les fichiers situés dans `{source_folder}` pour identifier et corriger les vulnérabilités décrites dans le contrôle. Ces vulnérabilités sont mises en évidence dans les résultats Cypher.

⚠️ Contraintes strictes :
- Ne modifie **que** les fichiers contenant des données vulnérables.
- Conserve strictement les noms de fichiers d’origine.
- N’utilise **que** les répertoires `{source_folder}` pour la lecture et `{destination_folder}` pour l’écriture.
- Ne pose **aucune question**.
- Analyse directement le contenu des fichiers `.zip` ou JSON dans `{source_folder}` pour détecter les données à corriger.
- Implémente les remédiations **en Python**, sous forme de transformations de données.

📦 Sortie attendue :
Un **script Python autonome**, prêt à être exécuté via `exec()`, qui :
1. Charge tous les fichiers du dossier `{source_folder}`.
2. Modifie uniquement ceux contenant des données vulnérables identifiées à partir des résultats Cypher.
3. Copie tous les autres fichiers sans modification.
4. Sauvegarde l’ensemble (modifié ou non) dans `{destination_folder}`, en conservant exactement les noms de fichiers d’origine.
5. Ne contient **pas** de bloc `if __name__ == "__main__"`.

🛑 La seule sortie que tu dois produire est ce script Python, sans commentaire ni texte supplémentaire.
""",
}


def read_all_controls_info() -> List[ControlInfo]:
    try:
        with open(ALL_CONTROLS_INFO_JSON, "r") as file:
            data = json.load(file)
            all_controls_info = [ControlInfo(**item) for item in data]
    except FileNotFoundError as e:
        print(f"Could not find {ALL_CONTROLS_INFO_JSON}")
        raise e
    return all_controls_info


def read_all_requests_results() -> List[RequestResult | DefaultRequestResult]:
    try:
        with open(ALL_REQUESTS_RESULTS_JSON, "r") as file:
            data = json.load(file)
            all_requests_results = []
            for k, v in data.items():
                try:
                    item = v
                    item["request_key"] = k
                    all_requests_results.append(RequestResult(**item))
                except Exception:
                    item = {"request_key": k, "result": v}
                    all_requests_results.append(DefaultRequestResult(**item))
    except FileNotFoundError as e:
        print(f"Could not find {ALL_REQUESTS_RESULTS_JSON}")
        raise e
    return all_requests_results


def read_single_control_info(control_title: str) -> ControlInfo:
    all_controls_info: List[ControlInfo] = read_all_controls_info()
    try:
        single_control_info: ControlInfo = [
            control_info
            for control_info in all_controls_info
            if control_info.title == control_title
        ][0]
    except IndexError:
        raise HTTPException(status_code=404, detail="Control information not found")
    return single_control_info


def read_single_request_result(
    request_key: str,
) -> RequestResult | DefaultRequestResult:
    all_requests_results: List[RequestResult | DefaultRequestResult] = (
        read_all_requests_results()
    )
    try:
        output = [
            request_result
            for request_result in all_requests_results
            if request_result.request_key == request_key
        ][0]
    except IndexError:
        raise HTTPException(status_code=404, detail="Request result not found")
    normalized_output = normalize_path(output)
    return normalized_output


def normalize_path(
    request_result: RequestResult | DefaultRequestResult,
) -> RequestResult | DefaultRequestResult:
    rr_processed = request_result.model_copy(deep=True)

    def _transform(obj: Any) -> Any:
        if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
            try:
                is_list_of_path = math.prod(
                    [element["__class__"] == "Path" for element in obj]
                )
            except Exception:
                is_list_of_path = 0
            if is_list_of_path:
                keys_node = {"id", "labels", "name", "domain", "tenant_id"}
                keys_edge = {"id", "relation_type"}
                all_nodes: list[dict[str, Any]] = []
                all_edges: list[list[dict[str, Any]]] = []
                for path in obj:
                    raw_nodes = path["nodes"]
                    edges_in_path: list[dict[str, Any]] = []
                    for node in raw_nodes:
                        node_view = {k: v for k, v in node.items() if k in keys_node}
                        if node_view not in all_nodes:
                            all_nodes.append(node_view)
                        edges_in_path.append(
                            {k: v for k, v in node.items() if k in keys_edge}
                        )
                    all_edges.append(edges_in_path)
                return {"nodes": all_nodes, "edges": all_edges}
            return [_transform(el) for el in obj]
        if isinstance(obj, Mapping):
            return {k: _transform(v) for k, v in obj.items()}
        return obj

    rr_processed.result = _transform(rr_processed.result)
    return rr_processed


_CLEAN_PATTERNS: dict[Pattern, str] = {
    re.compile(r"\\n"): "",
    re.compile(r"\r\n?"): "",
    re.compile(r"\n"): "",
    re.compile(r"\\t"): "    ",
    re.compile(r'\\+"'): r'"',
    re.compile(r"\\\\"): r"\\",
    re.compile(r"\""): r"'",
}

_SPACE_COLLAPSE: Pattern = re.compile(r" {2,}")


def clean(text: str) -> str:
    for pattern, repl in _CLEAN_PATTERNS.items():
        text = pattern.sub(repl, text)
    text = _SPACE_COLLAPSE.sub(" ", text)
    return text


def generate_llm_prompt(
    task: LLMTask,
    control_info: dict,
    requests_results: List[dict[str, Any]],
    source_folder: Optional[str] = None,
    destination_folder: Optional[str] = None,
) -> str:
    template = PROMPT_TEMPLATES[task]

    ctrl_txt = clean(json.dumps(control_info, ensure_ascii=False, indent=2))
    reqs_txt = clean(json.dumps(requests_results, ensure_ascii=False, indent=2))

    prompt = template.format(
        control_info=ctrl_txt,
        requests_results=reqs_txt,
        source_folder=source_folder or "{source_folder}",
        destination_folder=destination_folder or "{destination_folder}",
    )
    prompt = clean(re.sub(r"<[^>]+>", "", prompt))

    return prompt.strip()
