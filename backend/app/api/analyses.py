from hashlib import sha256
from datetime import timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlmodel import Session, func, select

from app.core.config import get_settings
from app.db.session import get_session
from app.models.analysis import Analysis, AnalysisOwner, ExtractionRecord, OcrRecord, ProviderEvent, utc_now
from app.core.visitor import visitor_id
from app.models.evidence import ComparisonRecord, Evidence, RetrievalRun, VerificationRecord
from app.models.dataset import DatasetMatch
from app.schemas.analysis import AnalysisPage, AnalysisRead, LayerRead, OcrCorrection, OcrRead, RunRequest, UploadResponse, VerificationRead
from app.services.image_service import find_image, store_image
from app.services import comparison_service, evidence_fusion, gemini_service, ocr_service, tavily_service, vision_ocr_service
from app.schemas.providers import ClaimExtraction, EvidenceRead, RetrievalRead
from app.schemas.dataset import DatasetMatchRead
from app.services import dataset_service

router = APIRouter(prefix="/analyses", tags=["analyses"])


def owned_analysis(analysis_id: str, owner_id: str, session: Session) -> Analysis:
    owner = session.get(AnalysisOwner, analysis_id)
    if owner is None or owner.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return analysis


@router.post("", response_model=UploadResponse, status_code=201)
async def upload_analysis(
    file: UploadFile = File(...),
    caption: str | None = Form(None, max_length=500),
    owner_id: str = Depends(visitor_id),
    session: Session = Depends(get_session),
) -> UploadResponse:
    settings = get_settings()
    analysis_id, path = await store_image(file, settings)
    analysis = Analysis(
        id=analysis_id,
        status="processing",
        image_path=str(path),
        image_sha256=sha256(path.read_bytes()).hexdigest(),
        caption=caption or None,
    )
    try:
        session.add(analysis)
        session.add(AnalysisOwner(analysis_id=analysis_id, owner_id=owner_id))
        session.commit()
    except Exception:
        session.rollback()
        path.unlink(missing_ok=True)
        raise
    result = await run_in_threadpool(ocr_service.extract_text, path, settings.min_ocr_confidence)
    record = OcrRecord(
        analysis_id=analysis_id,
        text=result.text,
        confidence=result.confidence,
        raw_result_json=result.raw_result_json,
        needs_confirmation=True,
        error_code=result.error_code,
    )
    session.add(record)
    analysis.status = "awaiting_confirmation"
    session.add(analysis)
    session.commit()
    return UploadResponse(
        analysis_id=analysis_id,
        status="awaiting_confirmation",
        image_url=f"/api/v1/analyses/{analysis_id}/image",
        caption=caption or None,
        ocr=to_ocr_read(record),
    )


def to_ocr_read(record: OcrRecord | None) -> OcrRead | None:
    if record is None:
        return None
    return OcrRead(
        text=record.text,
        confidence=record.confidence,
        needs_confirmation=record.needs_confirmation,
        error_code=record.error_code,
    )


def to_read(analysis: Analysis, session: Session) -> AnalysisRead:
    extraction = session.get(ExtractionRecord, analysis.id)
    retrieval = session.get(RetrievalRun, analysis.id)
    verification = session.get(VerificationRecord, analysis.id)
    extraction_value = ClaimExtraction.model_validate_json(extraction.data_json) if extraction else None
    verification_value = VerificationRead.model_validate_json(verification.data_json) if verification else None
    stale_report = verification_value is not None and verification_value.decision_method != "python_evidence_fusion_v3"
    if stale_report:
        verification_value = None
    comparison_rows = {} if stale_report else {row.evidence_id: row for row in session.exec(select(ComparisonRecord).where(ComparisonRecord.analysis_id == analysis.id)).all()}
    evidence = session.exec(select(Evidence).where(Evidence.analysis_id == analysis.id).order_by(Evidence.source_rank, Evidence.domain, Evidence.canonical_url)).all()
    unfiltered_count = len(evidence)
    if extraction_value and extraction_value.claim:
        evidence = [item for item in evidence if tavily_service.is_relevant_result(item.title, item.snippet, extraction_value)]
    irrelevant_note = ["Unrelated search results were excluded; no claim-specific source was found. Correct the claim if needed, then search again."] if unfiltered_count and not evidence else (["Some unrelated search results were excluded."] if len(evidence) < unfiltered_count else [])
    dataset_matches = session.exec(select(DatasetMatch).where(DatasetMatch.analysis_id == analysis.id).order_by(DatasetMatch.similarity.desc())).all()
    documented_image = next((item for item in dataset_matches if item.match_type == "exact_image" and item.provenance_url), None)
    if verification_value and documented_image:
        verification_value.layers["context"] = LayerRead(
            status="documented_match",
            summary="Exact image bytes match a reviewed archival record; see its cited date and location below. This does not establish media authenticity.",
        )
    if extraction_value:
        evidence.sort(key=lambda item: (tavily_service._source_type(item.domain, extraction_value.claimed_source, extraction_value.claim or "")[1], item.domain, item.canonical_url))
    return AnalysisRead(
        analysis_id=analysis.id,
        created_at=analysis.created_at.replace(tzinfo=timezone.utc) if analysis.created_at.tzinfo is None else analysis.created_at,
        status="partial" if stale_report else analysis.status,
        image_url=f"/api/v1/analyses/{analysis.id}/image",
        caption=analysis.caption,
        ocr=to_ocr_read(session.get(OcrRecord, analysis.id)),
        extraction=extraction_value,
        extraction_method=extraction.method if extraction else None,
        retrieval=RetrievalRead(
            status=retrieval.status,
            query_count=retrieval.query_count,
            successful_queries=retrieval.successful_queries,
            retrieved_at=retrieval.retrieved_at.replace(tzinfo=timezone.utc) if retrieval.retrieved_at.tzinfo is None else retrieval.retrieved_at,
            limitation=retrieval.limitation,
        ) if retrieval else None,
        evidence=[EvidenceRead(
            evidence_id=item.id,
            url=item.url,
            canonical_url=item.canonical_url,
            title=item.title,
            domain=item.domain,
            source_type=tavily_service._source_type(item.domain, extraction_value.claimed_source, extraction_value.claim or "")[0] if extraction_value else item.source_type,
            snippet=item.snippet,
            published_at=item.published_at.replace(tzinfo=timezone.utc) if item.published_at and item.published_at.tzinfo is None else item.published_at,
            retrieved_at=item.retrieved_at.replace(tzinfo=timezone.utc) if item.retrieved_at.tzinfo is None else item.retrieved_at,
            query=item.query,
            stance=comparison_rows[item.id].stance if item.id in comparison_rows else None,
            relevance=comparison_rows[item.id].relevance if item.id in comparison_rows else None,
            reason=comparison_rows[item.id].reason if item.id in comparison_rows else None,
            quote=comparison_rows[item.id].quote if item.id in comparison_rows else None,
        ) for item in evidence],
        limitations=(["This saved report predates current evidence checks. Rerun verification."] if stale_report else (verification_value.limitations if verification_value else (([retrieval.limitation] if retrieval and retrieval.limitation else []) + (["Evidence has not yet been compared or scored."] if retrieval else [])))) + irrelevant_note,
        verification=verification_value,
        dataset_matches=[DatasetMatchRead.model_validate(item, from_attributes=True) for item in dataset_matches],
    )


def clear_retrieval(analysis_id: str, session: Session) -> None:
    clear_verification(analysis_id, session)
    for item in session.exec(select(Evidence).where(Evidence.analysis_id == analysis_id)).all():
        session.delete(item)
    retrieval = session.get(RetrievalRun, analysis_id)
    if retrieval is not None:
        session.delete(retrieval)
    session.flush()


def clear_verification(analysis_id: str, session: Session) -> None:
    for row in session.exec(select(ComparisonRecord).where(ComparisonRecord.analysis_id == analysis_id)).all():
        session.delete(row)
    record = session.get(VerificationRecord, analysis_id)
    if record is not None:
        session.delete(record)
    session.flush()


def mark_failed(analysis_id: str, session: Session, *, clear_search: bool = False, clear_claim: bool = False) -> None:
    session.rollback()
    analysis = session.get(Analysis, analysis_id)
    if clear_search:
        clear_retrieval(analysis_id, session)
    else:
        clear_verification(analysis_id, session)
    if clear_claim:
        clear_dataset_matches(analysis_id, session)
        extraction = session.get(ExtractionRecord, analysis_id)
        if extraction is not None:
            session.delete(extraction)
    if analysis is not None:
        analysis.status = "failed"
        session.add(analysis)
    session.commit()


def clear_dataset_matches(analysis_id: str, session: Session) -> None:
    for item in session.exec(select(DatasetMatch).where(DatasetMatch.analysis_id == analysis_id)).all():
        session.delete(item)
    session.flush()


@router.get("", response_model=AnalysisPage)
def list_analyses(limit: int = 20, offset: int = 0, owner_id: str = Depends(visitor_id), session: Session = Depends(get_session)) -> AnalysisPage:
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail="Invalid pagination parameters.")
    total = session.exec(select(func.count()).select_from(Analysis).join(AnalysisOwner).where(AnalysisOwner.owner_id == owner_id)).one()
    analyses = session.exec(select(Analysis).join(AnalysisOwner).where(AnalysisOwner.owner_id == owner_id).order_by(Analysis.created_at.desc(), Analysis.id.desc()).offset(offset).limit(limit)).all()
    return AnalysisPage(items=[to_read(item, session) for item in analyses], total=total, limit=limit, offset=offset)


@router.get("/{analysis_id}", response_model=AnalysisRead)
def get_analysis(analysis_id: str, owner_id: str = Depends(visitor_id), session: Session = Depends(get_session)) -> AnalysisRead:
    analysis = owned_analysis(analysis_id, owner_id, session)
    return to_read(analysis, session)


@router.patch("/{analysis_id}/ocr", response_model=AnalysisRead)
def correct_ocr(analysis_id: str, correction: OcrCorrection, owner_id: str = Depends(visitor_id), session: Session = Depends(get_session)) -> AnalysisRead:
    analysis = owned_analysis(analysis_id, owner_id, session)
    text = ocr_service.normalize_text(correction.text)
    if not text:
        raise HTTPException(status_code=422, detail="OCR text cannot be empty.")
    record = session.get(OcrRecord, analysis_id)
    if record is None:
        record = OcrRecord(analysis_id=analysis_id)
    record.text = text
    record.needs_confirmation = False
    record.confirmed_at = utc_now()
    session.add(record)
    clear_retrieval(analysis_id, session)
    clear_dataset_matches(analysis_id, session)
    extraction = session.get(ExtractionRecord, analysis_id)
    if extraction is not None:
        session.delete(extraction)
    session.commit()
    return to_read(analysis, session)


@router.post("/{analysis_id}/ocr/vision-retry", response_model=AnalysisRead)
async def retry_ocr_with_vision(analysis_id: str, owner_id: str = Depends(visitor_id), session: Session = Depends(get_session)) -> AnalysisRead:
    analysis = owned_analysis(analysis_id, owner_id, session)
    settings = get_settings()
    if not settings.gemini_enabled or not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="AI image reading is not configured.")
    path = find_image(analysis_id, settings)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    text, attempts = await run_in_threadpool(vision_ocr_service.transcribe, path, settings)
    for attempt in attempts:
        session.add(ProviderEvent(analysis_id=analysis_id, provider=attempt.provider, operation=attempt.operation, success=attempt.success, status_code=attempt.status_code, latency_ms=attempt.latency_ms, error_code=attempt.error_code))
    if text is None:
        session.commit()
        raise HTTPException(status_code=503, detail="AI could not read this image. Please enter the text yourself.")
    record = session.get(OcrRecord, analysis_id)
    if record is None:
        record = OcrRecord(analysis_id=analysis_id)
    record.text = ocr_service.normalize_text(text)
    record.confidence = None  # Model output has no calibrated OCR confidence.
    record.needs_confirmation = True
    record.confirmed_at = None
    record.error_code = None
    record.raw_result_json = "[]"
    session.add(record)
    clear_retrieval(analysis_id, session)
    clear_dataset_matches(analysis_id, session)
    extraction = session.get(ExtractionRecord, analysis_id)
    if extraction:
        session.delete(extraction)
    analysis.status = "awaiting_confirmation"
    session.add(analysis)
    session.commit()
    return to_read(analysis, session)


@router.post("/{analysis_id}/run", response_model=AnalysisRead)
async def run_extraction(analysis_id: str, request: RunRequest, owner_id: str = Depends(visitor_id), session: Session = Depends(get_session)) -> AnalysisRead:
    analysis = owned_analysis(analysis_id, owner_id, session)
    ocr_record = session.get(OcrRecord, analysis_id)
    if ocr_record is None or ocr_record.needs_confirmation or not ocr_record.text.strip():
        raise HTTPException(status_code=409, detail="Confirm OCR text before claim extraction.")
    if request.claim is not None and not request.claim.strip():
        raise HTTPException(status_code=422, detail="Claim cannot be empty.")
    # Invalidate the previous report before the provider call so a refresh during
    # a slow rerun cannot expose evidence or a verdict for the old claim.
    clear_retrieval(analysis_id, session)
    clear_dataset_matches(analysis_id, session)
    previous_extraction = session.get(ExtractionRecord, analysis_id)
    if previous_extraction is not None:
        session.delete(previous_extraction)
    analysis.status = "processing"
    session.add(analysis)
    session.commit()
    try:
        outcome = await run_in_threadpool(gemini_service.extract_claim, ocr_record.text, analysis.caption, get_settings(), request.claim)
    except Exception:
        mark_failed(analysis_id, session, clear_search=True, clear_claim=True)
        raise
    record = session.get(ExtractionRecord, analysis_id)
    if record is None:
        record = ExtractionRecord(analysis_id=analysis_id, data_json="{}", method=outcome.method)
    record.data_json = outcome.extraction.model_dump_json()
    record.method = outcome.method
    clear_retrieval(analysis_id, session)
    clear_dataset_matches(analysis_id, session)
    session.add(record)
    for attempt in outcome.attempts:
        session.add(ProviderEvent(
            analysis_id=analysis_id,
            provider=attempt.provider,
            operation=attempt.operation,
            success=attempt.success,
            status_code=attempt.status_code,
            latency_ms=attempt.latency_ms,
            error_code=attempt.error_code,
        ))
    analysis.status = "awaiting_confirmation"
    session.add(analysis)
    session.commit()
    return to_read(analysis, session)


@router.post("/{analysis_id}/retrieve", response_model=AnalysisRead)
async def retrieve_evidence(analysis_id: str, owner_id: str = Depends(visitor_id), session: Session = Depends(get_session)) -> AnalysisRead:
    analysis = owned_analysis(analysis_id, owner_id, session)
    ocr_record = session.get(OcrRecord, analysis_id)
    extraction_record = session.get(ExtractionRecord, analysis_id)
    if ocr_record is None or ocr_record.needs_confirmation or extraction_record is None:
        raise HTTPException(status_code=409, detail="Confirm OCR text and the claim before search.")
    extraction = ClaimExtraction.model_validate_json(extraction_record.data_json)
    if extraction.needs_user_confirmation or not extraction.claim:
        raise HTTPException(status_code=409, detail="Confirm the main claim before search.")
    analysis.status = "processing"
    session.add(analysis)
    session.commit()
    try:
        outcome = await run_in_threadpool(tavily_service.retrieve, extraction, analysis_id, get_settings())
    except Exception:
        mark_failed(analysis_id, session, clear_search=True)
        raise
    clear_retrieval(analysis_id, session)
    session.add(RetrievalRun(
        analysis_id=analysis_id,
        status=outcome.status,
        query_count=outcome.query_count,
        successful_queries=outcome.successful_queries,
        retrieved_at=outcome.retrieved_at,
        limitation=outcome.limitation,
    ))
    for item in outcome.items:
        session.add(Evidence(
            id=item.evidence_id,
            analysis_id=analysis_id,
            url=item.url,
            canonical_url=item.canonical_url,
            title=item.title,
            domain=item.domain,
            source_type=item.source_type,
            source_rank=item.source_rank,
            snippet=item.snippet,
            published_at=item.published_at,
            retrieved_at=item.retrieved_at,
            query=item.query,
        ))
    for attempt in outcome.attempts:
        session.add(ProviderEvent(
            analysis_id=analysis_id,
            provider=attempt.provider,
            operation=attempt.operation,
            success=attempt.success,
            status_code=attempt.status_code,
            latency_ms=attempt.latency_ms,
            error_code=attempt.error_code,
        ))
    analysis.status = "partial"
    session.add(analysis)
    session.commit()
    return to_read(analysis, session)


@router.post("/{analysis_id}/match", response_model=AnalysisRead)
async def match_dataset(analysis_id: str, owner_id: str = Depends(visitor_id), session: Session = Depends(get_session)) -> AnalysisRead:
    analysis = owned_analysis(analysis_id, owner_id, session)
    extraction_record = session.get(ExtractionRecord, analysis_id)
    claim = ClaimExtraction.model_validate_json(extraction_record.data_json) if extraction_record else None
    confirmed_claim = claim.claim if claim and not claim.needs_user_confirmation else None
    matches = await run_in_threadpool(
        dataset_service.find_matches, analysis_id, confirmed_claim,
        analysis.image_sha256, get_settings().offline_dataset_dir,
    )
    clear_dataset_matches(analysis_id, session)
    for match in matches:
        session.add(match)
    session.commit()
    return to_read(analysis, session)


@router.post("/{analysis_id}/verify", response_model=AnalysisRead)
async def verify_evidence(analysis_id: str, owner_id: str = Depends(visitor_id), session: Session = Depends(get_session)) -> AnalysisRead:
    analysis = owned_analysis(analysis_id, owner_id, session)
    retrieval = session.get(RetrievalRun, analysis_id)
    extraction = session.get(ExtractionRecord, analysis_id)
    if retrieval is None or extraction is None:
        raise HTTPException(status_code=409, detail="Retrieve evidence for a confirmed claim before verification.")
    claim = ClaimExtraction.model_validate_json(extraction.data_json)
    if claim.needs_user_confirmation or not claim.claim:
        raise HTTPException(status_code=409, detail="Confirm the main claim before verification.")
    items = [item for item in session.exec(select(Evidence).where(Evidence.analysis_id == analysis_id).order_by(Evidence.source_rank, Evidence.domain)).all() if tavily_service.is_relevant_result(item.title, item.snippet, claim)]
    for item in items:
        item.source_type, item.source_rank = tavily_service._source_type(item.domain, claim.claimed_source, claim.claim)
        session.add(item)
    analysis.status = "processing"
    session.add(analysis)
    session.commit()
    try:
        outcome = await run_in_threadpool(comparison_service.compare, claim.claim, items, get_settings())
    except Exception:
        mark_failed(analysis_id, session)
        raise
    verdict = evidence_fusion.fuse(items, outcome, retrieval, claim)
    for row in session.exec(select(ComparisonRecord).where(ComparisonRecord.analysis_id == analysis_id)).all():
        session.delete(row)
    session.flush()
    for row in outcome.comparisons:
        session.add(ComparisonRecord(analysis_id=analysis_id, evidence_id=row.evidence_id, stance=row.stance, relevance=row.relevance, reason=row.reason, quote=row.quote, method=row.method))
    record = session.get(VerificationRecord, analysis_id)
    if record is None:
        record = VerificationRecord(analysis_id=analysis_id, data_json=verdict.model_dump_json())
    record.data_json = verdict.model_dump_json()
    session.add(record)
    for attempt in outcome.attempts:
        session.add(ProviderEvent(analysis_id=analysis_id, provider=attempt.provider, operation=attempt.operation, success=attempt.success, status_code=attempt.status_code, latency_ms=attempt.latency_ms, error_code=attempt.error_code))
    analysis.status = "completed" if retrieval.status in {"completed", "no_results"} and outcome.method in {"gemini", "none"} else "partial"
    session.add(analysis)
    session.commit()
    return to_read(analysis, session)


@router.get("/{analysis_id}/image")
def get_image(analysis_id: str, owner_id: str = Depends(visitor_id), session: Session = Depends(get_session)) -> FileResponse:
    owned_analysis(analysis_id, owner_id, session)
    path = find_image(analysis_id, get_settings())
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    media_type = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[path.suffix]
    return FileResponse(path, media_type=media_type)


@router.delete("/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: str, owner_id: str = Depends(visitor_id), session: Session = Depends(get_session)) -> None:
    analysis = owned_analysis(analysis_id, owner_id, session)
    events = session.exec(select(ProviderEvent).where(ProviderEvent.analysis_id == analysis_id)).all()
    for event in events:
        session.delete(event)
    session.flush()
    clear_retrieval(analysis_id, session)
    clear_dataset_matches(analysis_id, session)
    ocr_record = session.get(OcrRecord, analysis_id)
    if ocr_record is not None:
        session.delete(ocr_record)
        session.flush()
    extraction_record = session.get(ExtractionRecord, analysis_id)
    if extraction_record is not None:
        session.delete(extraction_record)
        session.flush()
    image_path = Path(analysis.image_path)
    session.delete(session.get(AnalysisOwner, analysis_id))
    session.flush()
    session.delete(analysis)
    session.commit()
    image_path.unlink(missing_ok=True)
