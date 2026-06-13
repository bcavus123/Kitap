"""Aşama 8: citation_service (CrossRef, mock) + media_service (Matplotlib) testleri."""
from app.services import citation_service, media_service


class _FakeResp:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_verify_doi_verified(monkeypatch):
    payload = {"message": {"title": ["Yapay Zeka ve Toplum"]}}
    monkeypatch.setattr(citation_service.httpx, "get", lambda *a, **k: _FakeResp(200, payload))
    status, data = citation_service.verify_doi("10.1234/x", "Yapay Zeka ve Toplum")
    assert status == "verified"
    assert data is not None


def test_verify_doi_not_found(monkeypatch):
    monkeypatch.setattr(citation_service.httpx, "get", lambda *a, **k: _FakeResp(404))
    status, _ = citation_service.verify_doi("10.1234/yok", "Bir Başlık")
    assert status == "not_found"


def test_verify_doi_mismatch(monkeypatch):
    payload = {"message": {"title": ["Tamamen Alakasiz Bir Calisma"]}}
    monkeypatch.setattr(citation_service.httpx, "get", lambda *a, **k: _FakeResp(200, payload))
    status, _ = citation_service.verify_doi("10.1234/x", "Yapay Zeka ve Toplum")
    assert status == "mismatch"


def test_verify_doi_network_error(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("ağ hatası")

    monkeypatch.setattr(citation_service.httpx, "get", _boom)
    status, _ = citation_service.verify_doi("10.1234/x", "X")
    assert status == "not_found"


def test_media_bar_chart_png():
    png = media_service.generate_bar_chart("Test Grafiği", ["A", "B", "C"], [3, 5, 2])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG imzası
    assert len(png) > 200
