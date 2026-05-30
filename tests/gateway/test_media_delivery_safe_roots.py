"""Regression tests for gateway MEDIA delivery safe roots."""

from pathlib import Path


def test_reports_cache_is_allowed_for_media_delivery(tmp_path, monkeypatch):
    """HTML reports created under ~/.hermes/cache/reports should attach natively.

    Harvey often generates standalone HTML reports under cache/reports. If that
    directory is not in the safe roots, final responses containing MEDIA:<path>
    are stripped and Telegram users receive no attachment.
    """
    from gateway.platforms import base

    reports_dir = tmp_path / "cache" / "reports"
    reports_dir.mkdir(parents=True)
    report = reports_dir / "report.html"
    report.write_text("<!doctype html><title>report</title>", encoding="utf-8")

    # Preserve the module's default roots but point the report root at this temp
    # directory so the test does not touch the real Hermes home.
    patched_roots = tuple(base.MEDIA_DELIVERY_SAFE_ROOTS) + (reports_dir,)
    monkeypatch.setattr(base, "MEDIA_DELIVERY_SAFE_ROOTS", patched_roots)

    assert base.validate_media_delivery_path(str(report)) == str(report.resolve())


def test_default_safe_roots_include_reports_cache():
    from gateway.platforms import base

    suffixes = {Path(root).as_posix().split("/.hermes/", 1)[-1] for root in base.MEDIA_DELIVERY_SAFE_ROOTS}
    assert any(s.endswith("cache/reports") for s in suffixes)
