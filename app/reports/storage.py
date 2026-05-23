"""Filesystem storage for generated website reports and PDFs."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.schemas.website_report import WebsiteReportResponse


def _root() -> Path:
    root = Path(settings.report_storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _report_dir(request_id: str) -> Path:
    return _root() / request_id


def save_report_bundle(response: WebsiteReportResponse, pdf_bytes: bytes) -> None:
    report_dir = _report_dir(response.request_id)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.json").write_text(response.model_dump_json(indent=2), encoding="utf-8")
    (report_dir / "executive.pdf").write_bytes(pdf_bytes)


def load_report(request_id: str) -> WebsiteReportResponse | None:
    path = _report_dir(request_id) / "report.json"
    if not path.exists():
        return None
    return WebsiteReportResponse.model_validate_json(path.read_text(encoding="utf-8"))


def load_pdf(request_id: str) -> bytes | None:
    path = _report_dir(request_id) / "executive.pdf"
    if not path.exists():
        return None
    return path.read_bytes()
