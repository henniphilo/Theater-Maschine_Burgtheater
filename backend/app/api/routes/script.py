import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import ValidationError

from app.director.cues.cue_models import DramaturgyDecision, OscCommand
from app.schemas.script import (
    CreateScriptRequest,
    DiscussionTurn,
    DramaturgyStreamRequest,
    PatchScriptBeatRequest,
    ProductionScript,
)
from app.services.dramaturgy_workshop_service import DramaturgyWorkshopService
from app.services.performance_bundle_service import get_performance_bundle_service
from app.services.script_splitter import build_beats_from_text
from app.services.script_store import get_script_store

router = APIRouter(prefix="/scripts", tags=["scripts"])
_store = get_script_store()
_workshop = DramaturgyWorkshopService()
_performance = get_performance_bundle_service()


@router.post("", response_model=ProductionScript, status_code=status.HTTP_201_CREATED)
def create_script(payload: CreateScriptRequest) -> ProductionScript:
    beats = build_beats_from_text(payload.source_text)
    if not beats:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty script text")
    return _store.create(payload.title, payload.source_text, beats)


@router.get("/{script_id}", response_model=ProductionScript)
def get_script(script_id: str) -> ProductionScript:
    return _store.get(script_id)


@router.patch("/{script_id}/beats/{beat_id}", response_model=ProductionScript)
def patch_beat(script_id: str, beat_id: str, payload: PatchScriptBeatRequest) -> ProductionScript:
    return _store.patch_beat(script_id, beat_id, payload)


def _workshop_payload(event) -> dict:
    data: dict = {"type": event.type}
    if event.beat_id is not None:
        data["beat_id"] = event.beat_id
    if event.beat_order is not None:
        data["beat_order"] = event.beat_order
    if event.speaker is not None:
        data["speaker"] = event.speaker
    if event.content is not None:
        data["content"] = event.content
    if event.dramaturgy is not None:
        data["dramaturgy"] = event.dramaturgy
    if event.planned_commands is not None:
        data["planned_commands"] = event.planned_commands
    if event.discussion_summary is not None:
        data["discussion_summary"] = event.discussion_summary
    if event.discussion_turns is not None:
        data["discussion_turns"] = event.discussion_turns
    if event.detail is not None:
        data["detail"] = event.detail
    return data


async def _dramaturgy_stream(script_id: str, payload: DramaturgyStreamRequest) -> AsyncIterator[str]:
    script = _store.get(script_id)
    try:
        async for event in _workshop.run_stream(
            title=script.title,
            beats=script.beats,
            openai_model=payload.openai_model,
            anthropic_model=payload.anthropic_model,
            discussion_rounds=payload.discussion_rounds,
        ):
            if event.type == "discussion_turn" and event.beat_id and event.discussion_turns:
                beat = next((b for b in script.beats if b.id == event.beat_id), None)
                if beat:
                    beat.discussion_turns = [
                        DiscussionTurn.model_validate(t) for t in event.discussion_turns
                    ]
                    script = _store.update_beat(script_id, beat)

            if event.type == "dramaturgy_decision" and event.beat_id and event.dramaturgy:
                beat = next((b for b in script.beats if b.id == event.beat_id), None)
                if beat:
                    beat.dramaturgy = DramaturgyDecision.model_validate(event.dramaturgy)
                    beat.planned_commands = [
                        OscCommand.model_validate(c) for c in (event.planned_commands or [])
                    ]
                    if event.discussion_turns:
                        beat.discussion_turns = [
                            DiscussionTurn.model_validate(t) for t in event.discussion_turns
                        ]
                    beat.discussion_summary = event.discussion_summary
                    script = _store.update_beat(script_id, beat)

            yield f"data: {json.dumps(_workshop_payload(event))}\n\n"

        script = _store.get(script_id)
        yield f"data: {json.dumps({'type': 'script_updated', 'script': script.model_dump(mode='json')})}\n\n"
    except ValidationError as exc:
        yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"


@router.post("/{script_id}/dramaturgy/stream")
async def stream_dramaturgy(script_id: str, payload: DramaturgyStreamRequest) -> StreamingResponse:
    _store.get(script_id)
    return StreamingResponse(
        _dramaturgy_stream(script_id, payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{script_id}/performance/export")
async def export_performance(script_id: str) -> Response:
    await _performance.render_and_save(script_id)
    data, filename = _performance.build_zip_bytes(script_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{script_id}/performance/download")
def download_performance(script_id: str) -> Response:
    _store.get(script_id)
    data, filename = _performance.build_zip_bytes(script_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/performance/import", response_model=ProductionScript, status_code=status.HTTP_201_CREATED)
async def import_performance(file: UploadFile = File(...)) -> ProductionScript:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file uploaded")
    data = await file.read()
    return _performance.import_zip(data)


@router.get("/{script_id}/performance/audio/{beat_id}/{asset}")
def get_performance_audio(script_id: str, beat_id: str, asset: str) -> FileResponse:
    _store.get(script_id)
    path = _performance.audio_path(script_id, beat_id, asset)
    media = "audio/mpeg" if path.suffix.lower() in {".mp3", ".m4a"} else "audio/aiff"
    return FileResponse(path, media_type=media)
