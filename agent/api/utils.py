from pydantic import BaseModel
from typing import List, Dict, Any
from enum import Enum
import json

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
