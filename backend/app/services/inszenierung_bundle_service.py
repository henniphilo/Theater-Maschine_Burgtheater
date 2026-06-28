"""Export/import Teil-2 Inszenierung (SceneCorpus) as .tmteil2.zip bundles."""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.schemas.inszenierung import SceneCorpus
from app.services.inszenierung_store import InszenierungStore

TEIL2_FORMAT_VERSION = 1
MAX_IMPORT_BYTES = 20 * 1024 * 1024


class InszenierungBundleService:
    def __init__(self, store: InszenierungStore | None = None) -> None:
        self.store = store or InszenierungStore()

    def export_zip(self, corpus_id: str) -> tuple[bytes, str]:
        corpus = self.store.get(corpus_id)
        has_plan = bool(corpus.teil2_plan and corpus.teil2_plan.sentences)
        has_legacy = bool(corpus.composition and corpus.composition.moments)
        if not has_plan and not has_legacy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kein Plan — zuerst vorbereiten",
            )
        moment_count = (
            len(corpus.teil2_plan.sentences)
            if has_plan
            else len(corpus.composition.moments)  # type: ignore[union-attr]
        )
        manifest = {
            "format": "theatermaschine.teil2",
            "version": TEIL2_FORMAT_VERSION,
            "exported_at": datetime.now(UTC).isoformat(),
            "corpus_id": corpus.id,
            "title": corpus.title,
            "moment_count": moment_count,
        }
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            archive.writestr("corpus.json", corpus.model_dump_json(indent=2))
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in corpus.title)[:40]
        filename = f"teil2-{safe_title or corpus_id[:8]}.tmteil2.zip"
        return buffer.getvalue(), filename

    async def import_zip(self, upload: UploadFile) -> SceneCorpus:
        raw = await upload.read()
        if len(raw) > MAX_IMPORT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Datei zu groß",
            )
        try:
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                if "corpus.json" not in archive.namelist():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Ungültiges Teil-2-Archiv (corpus.json fehlt)",
                    )
                payload = json.loads(archive.read("corpus.json").decode("utf-8"))
        except zipfile.BadZipFile as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Keine gültige ZIP-Datei",
            ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="corpus.json ungültig",
            ) from exc

        corpus = SceneCorpus.model_validate(payload)
        corpus.id = str(uuid4())
        return self.store.save(corpus)


_service: InszenierungBundleService | None = None


def get_inszenierung_bundle_service() -> InszenierungBundleService:
    global _service
    if _service is None:
        _service = InszenierungBundleService()
    return _service
