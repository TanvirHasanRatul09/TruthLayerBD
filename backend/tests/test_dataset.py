import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import get_engine
from app.main import app
from app.models.dataset import DatasetMatch
from app.models.evidence import VerificationRecord
from app.schemas.analysis import LayerRead, VerificationRead
from app.services import dataset_service, ocr_service


def record(**changes):
    value = dict(dataset_id="pilot", record_id="1", claim_text="ঢাকায় আজ নতুন সেতু উদ্বোধন হয়েছে",
                 original_label="false", source_url="https://example.org/factcheck/1",
                 license="metadata only; source link", attribution="Pilot fact-check source")
    value.update(changes)
    return value


def test_matching_is_conservative_and_provenance_gated():
    digest = sha256(b"known-image").hexdigest()
    entries = [
        record(),
        record(record_id="2", claim_text="অন্য বিষয় নিয়ে প্রতিবেদন", original_label="true"),
        record(record_id="3", image_sha256=digest, provenance_url="https://example.org/original/3",
               original_event_date="2020-01-01", original_location="ঢাকা", provenance_reviewed=False),
        record(record_id="4", image_sha256=digest, provenance_url="https://example.org/original/4",
               original_event_date="2020-01-01", original_location="ঢাকা", provenance_reviewed=True),
        record(record_id="5", source_url="javascript:bad"),
    ]
    with TemporaryDirectory(dir=".") as test_dir:
        root = Path(test_dir)
        (root / "pilot.jsonl").write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in entries), encoding="utf-8")
        matches = dataset_service.find_matches("an_test", "ঢাকায় আজ নতুন সেতু উদ্বোধন হয়েছে", digest, str(root))
        assert {item.record_id for item in matches} == {"1", "3", "4"}
        assert next(item for item in matches if item.record_id == "1").match_type == "related_claim"
        assert next(item for item in matches if item.record_id == "3").provenance_url is None
        assert next(item for item in matches if item.record_id == "4").original_location == "ঢাকা"
        assert dataset_service.find_matches("an_test", "অন্য দাবি", sha256(b"other").hexdigest(), str(root)) == []


def test_match_endpoint_persists_and_delete_cascades(monkeypatch):
    settings = get_settings()
    old = settings.database_url, settings.upload_dir, settings.offline_dataset_dir
    monkeypatch.setattr(ocr_service, "extract_text", lambda path, threshold: ocr_service.OcrResult("", None, "[]", "OCR_UNAVAILABLE"))
    with TemporaryDirectory(dir=".") as test_dir:
        root = Path(test_dir).resolve()
        settings.database_url = f"sqlite:///{(root / 'test.db').as_posix()}"
        settings.upload_dir = str(root / "uploads")
        settings.offline_dataset_dir = str(root / "datasets")
        Path(settings.offline_dataset_dir).mkdir()
        try:
            output = BytesIO()
            Image.new("RGB", (8, 8), "green").save(output, format="PNG")
            client = TestClient(app)
            created = client.post("/api/v1/analyses", files={"file": ("post.png", output.getvalue(), "image/png")}).json()
            digest = sha256(output.getvalue()).hexdigest()
            (Path(settings.offline_dataset_dir) / "records.jsonl").write_text(json.dumps(record(image_sha256=digest, provenance_url="https://example.org/original", provenance_reviewed=True, original_event_date="2020-01-01", original_location="ঢাকা")), encoding="utf-8")
            analysis_id = created["analysis_id"]
            matched = client.post(f"/api/v1/analyses/{analysis_id}/match")
            assert matched.status_code == 200
            assert matched.json()["dataset_matches"][0]["match_type"] == "exact_image"
            report = VerificationRead(label="insufficient_evidence", evidence_coverage="low", summary="No evidence", comparison_method="none", decision_method="python_evidence_fusion_v3", layers={key: LayerRead(status="inconclusive", summary="Unknown") for key in ("claim", "source", "context", "media")})
            with Session(get_engine(settings.database_url)) as session:
                session.add(VerificationRecord(analysis_id=analysis_id, data_json=report.model_dump_json()))
                session.commit()
            detail = client.get(f"/api/v1/analyses/{analysis_id}").json()
            assert detail["verification"]["layers"]["context"]["status"] == "documented_match"
            assert detail["verification"]["layers"]["media"]["status"] == "inconclusive"
            get_engine(settings.database_url).dispose()
            get_engine.cache_clear()
            assert len(client.get(f"/api/v1/analyses/{analysis_id}").json()["dataset_matches"]) == 1
            assert client.delete(f"/api/v1/analyses/{analysis_id}").status_code == 204
            with Session(get_engine(settings.database_url)) as session:
                assert session.exec(select(DatasetMatch)).all() == []
        finally:
            get_engine(settings.database_url).dispose()
            get_engine.cache_clear()
            settings.database_url, settings.upload_dir, settings.offline_dataset_dir = old
