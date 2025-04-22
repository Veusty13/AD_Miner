from fastapi import FastAPI, Path, HTTPException
from typing import List, Annotated, Any
from utils import (
    ControlInfo,
    GetListControlsOutput,
    RequestResult,
    read_all_controls_info,
    read_all_requests_results,
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
    all_controls_info: List[ControlInfo] = read_all_controls_info()
    try:
        output: ControlInfo = [
            control_info
            for control_info in all_controls_info
            if control_info.title == control_title
        ][0]
    except IndexError:
        raise HTTPException(status_code=404, detail="Control information not found")
    return output


@app.get("/controls/information/requests/{request_key}")
async def get_requests_control(
    request_key: Annotated[str, Path()],
) -> RequestResult | Any:
    all_requests_results: List[RequestResult | Any] = read_all_requests_results()
    try:
        output = [
            request_result
            for request_result in all_requests_results
            if request_result.request_key == request_key
        ][0]
    except IndexError:
        raise HTTPException(status_code=404, detail="Request result not found")
    return output
