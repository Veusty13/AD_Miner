from fastapi import FastAPI, Path, Body
import traceback
import io
import json
import shutil
import sys
from typing import List, Annotated, Dict, Union
from fastapi.responses import JSONResponse
import zipfile
from utils import (
    ControlInfo,
    GetListControlsOutput,
    RequestResult,
    DefaultRequestResult,
    LLMTask,
    PromptRequestModel,
    FolderRequest,
    read_all_controls_info,
    read_single_control_info,
    read_single_request_result,
    generate_llm_prompt,
    extract_parts
)
import os
import pathlib

app = FastAPI()


@app.get("/controls/information/list")
async def get_list_controls() -> List[GetListControlsOutput]:
    all_controls_info: List[ControlInfo] = read_all_controls_info()
    output = [
        GetListControlsOutput(
            control_category=control_info.control_category, title=control_info.title
        )
        for control_info in all_controls_info
    ]
    return output


@app.get("/controls/information/{control_title}")
async def get_control_info(control_title: Annotated[str, Path()]) -> ControlInfo:
    output: ControlInfo = read_single_control_info(control_title=control_title)
    return output


@app.get("/controls/information/requests/{request_key}")
async def get_requests_control(
    request_key: Annotated[str, Path()],
) -> RequestResult | DefaultRequestResult:
    output: RequestResult | DefaultRequestResult = read_single_request_result(
        request_key=request_key
    )
    return output


@app.post("/llm/prompt/{task}")
async def ask_llm(
    task: Annotated[LLMTask, Path()],
    prompt_request: Annotated[PromptRequestModel, Body()],
) -> str:
    control_info: ControlInfo = read_single_control_info(
        control_title=prompt_request.control_title
    )
    request_keys: List[str] = control_info.requests_keys
    requests_results: List[RequestResult | DefaultRequestResult] = [
        read_single_request_result(request_key=request_key)
        for request_key in request_keys
    ]
    prompt = generate_llm_prompt(
        task=task,
        control_info=control_info.model_dump(),
        requests_results=[r.model_dump() for r in requests_results],
        source_folder=prompt_request.source_folder,
        destination_folder=prompt_request.destination_folder,
    )
    return prompt


@app.post("/llm/code/execute")
async def execute_code(code: Annotated[str, Body()]):
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    result = {"stdout": "", "stderr": "", "exception": ""}
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout_buffer, stderr_buffer

    try:
        exec(code, {})
    except Exception:
        result["exception"] = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        result["stdout"] = stdout_buffer.getvalue()
        result["stderr"] = stderr_buffer.getvalue()

    return result


@app.post("/folders/unzip")
async def unzip_folders(payload: FolderRequest):
    source_folder = payload.source_folder
    destination_folder = payload.destination_folder

    try:
        print(
            f"Reçu : source_folder={source_folder}, destination_folder={destination_folder}"
        )

        if not os.path.exists(source_folder):
            raise Exception(f"Le dossier source {source_folder} n'existe pas.")
        if not os.path.exists(destination_folder):
            raise Exception(
                f"Le dossier destination {destination_folder} n'existe pas."
            )

        def beautify_json_file(json_path: pathlib.Path, indent=2):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=indent, ensure_ascii=False)
                print(f"✅ Reformatté : {json_path}")
            except Exception as e:
                print(f"❌ Échec reformatage {json_path} : {e}")

        def parse_and_beautify_jsons(
            zip_ref: zipfile.ZipFile, extract_dir: pathlib.Path, zip_name: str
        ):
            for item in zip_ref.infolist():
                if item.filename.endswith(".json"):
                    try:
                        extracted_path = extract_dir / item.filename
                        if extracted_path.exists():
                            beautify_json_file(extracted_path)
                    except Exception as e:
                        print(f"[{zip_name}] Erreur JSON : {item.filename} — {e}")

        def unzip_all(zip_dir: pathlib.Path) -> int:
            zip_files = list(zip_dir.glob("*.zip"))
            for zip_path in zip_files:
                print(f"Dézippage de : {zip_path} dans {zip_dir}")
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(zip_dir)
                    parse_and_beautify_jsons(zip_ref, zip_dir, zip_path.name)
            return len(zip_files)

        count_source = unzip_all(pathlib.Path(source_folder))
        count_dest = unzip_all(pathlib.Path(destination_folder))

        if count_source == 0 and count_dest == 0:
            return JSONResponse(
                status_code=404,
                content={
                    "message": "Aucune archive .zip trouvée dans les deux dossiers."
                },
            )

        return {
            "message": f"{count_source} archives dézippées dans {source_folder}, "
            f"{count_dest} dans {destination_folder}"
        }

    except Exception as e:
        print(f"Erreur interne : {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Erreur lors du dézippage : {str(e)}"},
        )


@app.post("/folders/clear")
def clear_folders(request: FolderRequest):
    source_folder = request.source_folder
    destination_folder = request.destination_folder

    # Nettoyage du dossier source (sauf .zip)
    for filename in os.listdir(source_folder):
        filepath = os.path.join(source_folder, filename)
        if os.path.isfile(filepath) and not filename.endswith(".zip"):
            os.remove(filepath)
        elif os.path.isdir(filepath):
            shutil.rmtree(filepath)

    # Nettoyage complet du dossier destination
    for filename in os.listdir(destination_folder):
        filepath = os.path.join(destination_folder, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)
        elif os.path.isdir(filepath):
            shutil.rmtree(filepath)

    return {
        "status": "OK",
        "message": "Dossiers nettoyés sauf .zip dans le dossier source",
    }


@app.post("/folders/concat")
def concat_json(request: FolderRequest):
    print("hello")
    folder_path = pathlib.Path(request.source_folder)
    if not folder_path.exists() or not folder_path.is_dir():
        return {"error": "Le dossier n'existe pas"}

    json_files = list(folder_path.glob("*.json"))
    if not json_files:
        return {"error": "Aucun fichier JSON trouvé dans le dossier"}

    combined_data: Dict[str, Union[dict, list]] = {}
    prefixes = set()
    suffixes = set()

    for file in json_files:
        prefix, suffix = extract_parts(file.name)
        if not prefix or not suffix:
            continue

        prefixes.add(prefix)
        suffixes.add(suffix)

        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                file_stem = file.stem
                combined_data[file_stem] = data
        except json.JSONDecodeError:
            continue

    if not combined_data:
        return {"error": "Les fichiers JSON sont vides ou invalides"}

    sorted_prefixes = sorted(prefixes)
    if len(suffixes) == 1:
        suffix = list(suffixes)[0]
    else:
        suffix_parts = [s.split("_") for s in suffixes]
        min_len = min(len(parts) for parts in suffix_parts)
        common_suffix = []
        for i in range(min_len):
            ith_parts = [parts[i] for parts in suffix_parts]
            if all(p == ith_parts[0] for p in ith_parts):
                common_suffix.append(ith_parts[0])
            else:
                break
        suffix = "_".join(common_suffix) if common_suffix else "concat"

    output_filename = f"{'_'.join(sorted_prefixes)}_{suffix}_all_entities.json"
    output_path = folder_path / output_filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=2)

    return {"message": f"Fichier concaténé créé : {output_filename}"}
