from fastapi import FastAPI, Path, Body
from typing import List, Annotated
from utils import (
    ControlInfo,
    GetListControlsOutput,
    RequestResult,
    DefaultRequestResult,
    LLMTask,
    read_all_controls_info,
    read_single_control_info,
    read_single_request_result,
    generate_llm_prompt,
)

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
    task: Annotated[LLMTask, Path()], control_title: Annotated[str, Body()]
) -> str:
    control_info: ControlInfo = read_single_control_info(control_title=control_title)
    request_keys: List[str] = control_info.requests_keys
    requests_results: List[RequestResult | DefaultRequestResult] = [
        read_single_request_result(request_key=request_key)
        for request_key in request_keys
    ]
    prompt: str = generate_llm_prompt(
        task=task,
        control_info=control_info.model_dump(),
        requests_results=[
            request_result.model_dump() for request_result in requests_results
        ],
    )
    return prompt
