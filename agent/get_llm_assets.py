from typing import Dict, List
from collections import defaultdict
import os
import json
import re
from pathlib import Path
import ast


def extract_objects_code(code: str, objects: List[str]) -> Dict[str, str]:
    tree = ast.parse(code)
    lines = code.splitlines()
    object_code = {}

    for node in ast.iter_child_nodes(tree):
        if isinstance(
            node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Assign)
        ):
            name = getattr(node, "name", None)
            if not name and isinstance(node, ast.Assign):
                if isinstance(node.targets[0], ast.Name):
                    name = node.targets[0].id

            if name in objects:
                start_line = node.lineno - 1
                end_line = getattr(node, "end_lineno", None)
                if end_line is None:
                    end_line = start_line + 1
                    while end_line < len(lines) and lines[end_line].startswith(
                        (" ", "\t")
                    ):
                        end_line += 1
                object_code[name] = "\n".join(lines[start_line:end_line])

    return object_code


def get_import_map(
    import_lines: List[str], root_path: Path = Path(".")
) -> Dict[str, Dict[str, object]]:
    temp_map: Dict[Path, List[str]] = defaultdict(list)
    full_map: Dict[str, Dict[str, object]] = {}

    for line in import_lines:
        if not line.strip().startswith("from") or "import" not in line:
            continue

        parts = line.strip().split()
        module = parts[1]
        objects = [o.strip() for o in parts[3].split(",")]

        module_path = module.replace(".", "/")
        py_file = root_path / f"{module_path}.py"
        init_file = root_path / module_path / "__init__.py"

        final_path = py_file if py_file.exists() else init_file.resolve()
        temp_map[final_path].extend(objects)

    for path, imported in temp_map.items():
        try:
            code = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            code = ""
            object_code_map = {}
        else:
            object_code_map = extract_objects_code(code, imported)

        full_map[path.as_posix()] = {
            "imported_elements": imported,
            "code_map": object_code_map,
        }

    return full_map


def get_request_keys(input_string: str) -> List[str]:
    pattern = r'requests_results\[\s*["\']([^"\']+)["\']\s*\]'
    all_occurences = re.findall(pattern, input_string)
    return all_occurences


def load_control_map(implemented_controls_map_path: str):
    try:
        with open(implemented_controls_map_path, "r") as file:
            implemented_controls_map = json.load(file)
        print(
            f"\nLoaded control name -> category mapping from {implemented_controls_map_path}"
        )
        return implemented_controls_map
    except FileNotFoundError as e:
        print(f"File not found: {implemented_controls_map_path}")
        raise e


class ControlInfo:
    def __init__(self, file_name: str, code: str):
        self.title: str = ""
        self.file_name: str = file_name
        self.control_category: str = ""
        self.code: str = code
        self.code_lines: list[str] = []
        self.dependencies: Dict[str, Dict[str, object]] = []
        self.requests_keys: List = []

    def get_code_lines(self) -> None:
        self.code_lines = self.code.split("\n")

    def get_control_dependencies(self) -> None:
        import_lines: List[str] = [
            line
            for line in self.code_lines
            if line.startswith("from") or line.startswith("import")
        ]
        self.dependencies = get_import_map(import_lines=import_lines)

    def get_title(self) -> None:
        title_line = [line for line in self.code_lines if "self.title" in line][0]
        title = re.search(r'self\.title\s*=\s*([\'"])(.*?)\1', title_line).group(2)
        self.title = title

    def get_control_category(self, implemented_controls_map) -> None:
        self.control_category = implemented_controls_map[self.title]

    def get_requests_results(self) -> None:
        request_keys_code = get_request_keys(input_string=self.code)
        self.requests_keys += request_keys_code
        for _, value in self.dependencies.items():
            code_map = value["code_map"]
            for _, code in code_map.items():
                request_keys_code_imported_element = get_request_keys(input_string=code)
                self.requests_keys += request_keys_code_imported_element
        self.requests_keys = list(set(self.requests_keys))


class ControlInfoGatherer:
    def __init__(
        self, output_folder: str, implemented_controls_map: Dict[str, str]
    ) -> None:
        self.ouput_folder = output_folder
        self.implemented_controls_map = implemented_controls_map
        self.controls_folder: str = "ad_miner/sources/modules/controls"
        self.list_control_info: List[ControlInfo] = []

    def get_controls(self) -> None:
        control_file_names = [
            file_name
            for file_name in os.listdir(self.controls_folder)
            if (
                file_name.endswith(".py")
                and not file_name.startswith("azure")
                and not file_name
                in ["__init__.py", "smolcard_class.py", "control_template.py"]
            )
        ]
        control_file_names_print = "\n    ->  " + "\n    ->  ".join(control_file_names)
        print(f"\nAbout to parse the following controls : {control_file_names_print}")
        for file_name in control_file_names:
            try:
                with open(
                    os.path.join(self.controls_folder, file_name), "r", encoding="utf-8"
                ) as f:
                    control_code: str = f.read()
            except FileNotFoundError as e:
                print(f"File not found: {file_name}")
                raise e
            control_info = ControlInfo(file_name=file_name, code=control_code)
            control_info.get_code_lines()
            control_info.get_control_dependencies()
            control_info.get_title()
            control_info.get_control_category(self.implemented_controls_map)
            control_info.get_requests_results()
            self.list_control_info.append(control_info)
        print("\nDone extracting controls data from the list of files above")

    def save_controls_as_json(self) -> None:
        output_path = os.path.join(self.ouput_folder, "all_controls_info.json")
        os.makedirs(self.ouput_folder, exist_ok=True)

        parsed_controls = []
        for control_info in self.list_control_info:
            parsed_controls.append(
                {
                    "title": control_info.title,
                    "file_name": control_info.file_name,
                    "control_category": control_info.control_category,
                    "code": control_info.code,
                    "dependencies": control_info.dependencies,
                    "requests_keys": control_info.requests_keys,
                }
            )
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(parsed_controls, f, ensure_ascii=False, indent=2)
            print(f"\nDone saving controls data at {output_path}")
        except TypeError as e:
            print(
                "\nThere was an error saving the file, one of the elements might not be json serializable"
            )
            raise e


if __name__ == "__main__":

    implemented_control_path = "agent/llm_assets/implemented_controls_map.json"
    output_folder = "agent/llm_assets"
    implemented_controls_map = load_control_map(
        implemented_controls_map_path=implemented_control_path
    )
    control_gatherer = ControlInfoGatherer(
        output_folder=output_folder, implemented_controls_map=implemented_controls_map
    )
    control_gatherer.get_controls()
    control_gatherer.save_controls_as_json()
