from fastapi import FastAPI, Path, Body
import contextlib
import io
import sys
from typing import List, Annotated
from fastapi.responses import JSONResponse
import zipfile
from utils import (
    ControlInfo,
    GetListControlsOutput,
    RequestResult,
    DefaultRequestResult,
    LLMTask,
    PromptRequestModel,
    UnzipRequest,
    read_all_controls_info,
    read_single_control_info,
    read_single_request_result,
    generate_llm_prompt,
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
    task: Annotated[LLMTask, Path()], prompt_request: Annotated[PromptRequestModel, Body()]
) -> str:
    control_info: ControlInfo = read_single_control_info(control_title=prompt_request.control_title)
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
        destination_folder=prompt_request.destination_folder
    )
    return prompt


@app.post("/llm/code/execute")
async def execute_code(code: Annotated[str, Body()]):
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    result = {
        "stdout": "",
        "stderr": "",
        "exception": ""
    }

    # Redirige stdout et stderr
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout_buffer, stderr_buffer

    try:
        exec(code, {})  # environnement isolé
    except Exception:
        result["exception"] = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        result["stdout"] = stdout_buffer.getvalue()
        result["stderr"] = stderr_buffer.getvalue()

    return result

@app.post("/folders/unzip")
async def unzip_folders(payload: UnzipRequest):
    source_folder = payload.source_folder
    destination_folder = payload.destination_folder

    try:
        print(f"Reçu : source_folder={source_folder}, destination_folder={destination_folder}")

        # Vérifier que les dossiers existent
        if not os.path.exists(source_folder):
            raise Exception(f"Le dossier source {source_folder} n'existe pas.")
        if not os.path.exists(destination_folder):
            raise Exception(f"Le dossier destination {destination_folder} n'existe pas.")

        # Fonction utilitaire pour dézipper dans son propre dossier
        def unzip_all(zip_dir: Path) -> int:
            zip_files = list(zip_dir.glob("*.zip"))
            for zip_path in zip_files:
                print(f"Dézippage de : {zip_path} dans {zip_dir}")
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(zip_dir)
            return len(zip_files)

        count_source = unzip_all(pathlib.Path(source_folder))
        count_dest = unzip_all(pathlib.Path(destination_folder))

        if count_source == 0 and count_dest == 0:
            return JSONResponse(
                status_code=404,
                content={"message": "Aucune archive .zip trouvée dans les deux dossiers."},
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