"""推文生成运行 API：触发工作流、查询详情、SSE 事件流、停止。"""

import json
import threading
import time
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.events import RunEventPublisher
from app.agents.runner import run_workflow
from app.db.session import get_db
from app.models.artifact import TweetArtifact
from app.models.project import Project
from app.models.revision import TweetRevision
from app.models.run import TweetRun
from app.schemas.run import (
    RunCreatedResponse,
    RunCreateRequest,
    RunDetailResponse,
)

router = APIRouter(tags=["runs"])

# SSE 单连接最长挂 10 分钟，避免前端悬挂
_STREAM_MAX_SECONDS = 600
_POLL_INTERVAL_SECONDS = 0.5
_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _get_run_or_404(run_id: str, db: Session) -> TweetRun:
    run = db.get(TweetRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.post(
    "/projects/{project_id}/runs",
    response_model=RunCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_run(
    project_id: str,
    payload: RunCreateRequest | None = None,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    extra_input = payload.input if payload else {}
    input_snapshot = {
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "website_url": project.website_url,
            "github_url": project.github_url,
            "target_audience": project.target_audience,
            "selling_points": project.selling_points,
            "goals": project.goals,
            "tone": project.tone,
            "platforms": project.platforms,
        },
        "extra": extra_input,
    }

    run = TweetRun(project_id=project_id, status="pending", input_snapshot=input_snapshot)
    db.add(run)
    db.commit()
    db.refresh(run)

    thread = threading.Thread(
        target=run_workflow,
        args=(run.id, project_id, input_snapshot),
        daemon=True,
        name=f"tweet-run-{run.id[:8]}",
    )
    thread.start()
    return RunCreatedResponse(id=run.id, project_id=project_id, status=run.status)


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = _get_run_or_404(run_id, db)
    detail = RunDetailResponse.model_validate(run, from_attributes=True)
    artifacts = (
        db.query(TweetArtifact)
        .filter(TweetArtifact.run_id == run_id)
        .order_by(TweetArtifact.created_at.asc())
        .all()
    )
    revisions = (
        db.query(TweetRevision)
        .filter(TweetRevision.run_id == run_id)
        .order_by(TweetRevision.version.asc())
        .all()
    )
    detail.artifacts = artifacts
    detail.revisions = revisions
    return detail


@router.post("/runs/{run_id}/stop", status_code=status.HTTP_202_ACCEPTED)
def stop_run(run_id: str, db: Session = Depends(get_db)):
    _get_run_or_404(run_id, db)
    RunEventPublisher(run_id).request_stop()
    return {"id": run_id, "stopping": True}


@router.get("/runs/{run_id}/events")
def stream_events(run_id: str, db: Session = Depends(get_db)):
    _get_run_or_404(run_id, db)
    publisher = RunEventPublisher(run_id)

    def event_stream() -> Generator[str, None, None]:
        index = 0
        deadline = time.monotonic() + _STREAM_MAX_SECONDS
        yield ": stream connected\n\n"
        while True:
            events = publisher.read_from(index)
            for event in events:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                index += 1

            status_value = publisher.current_status()
            if status_value in _TERMINAL_STATUSES and not events:
                end_event = {"eventType": "stream.end", "status": status_value}
                yield f"data: {json.dumps(end_event, ensure_ascii=False)}\n\n"
                return
            if time.monotonic() > deadline:
                yield 'data: {"eventType": "stream.timeout"}\n\n'
                return
            time.sleep(_POLL_INTERVAL_SECONDS)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )



