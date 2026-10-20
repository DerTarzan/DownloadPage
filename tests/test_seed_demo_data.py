from types import SimpleNamespace

from scripts import seed_demo_data


def test_seed_demo_data_dry_run_uses_bundled_files(monkeypatch, tmp_path, capsys):
    settings = SimpleNamespace(
        storage_dir=tmp_path / "storage",
        max_image_bytes=1024 * 1024,
        max_pdf_bytes=10 * 1024 * 1024,
    )
    monkeypatch.setitem(seed_demo_data.__dict__, "get_settings", lambda: settings)

    assert seed_demo_data.seed(dry_run=True) == 0

    output = capsys.readouterr().out
    assert "50 Kategorien, 50 Produkte und 50 PDFs" in output
    assert "scripts/data" in output
    assert (seed_demo_data.DATA_DIR / "Med_aire_Flex_Wave.png").is_file()
    assert (seed_demo_data.DATA_DIR / "Bellavita (Drive Medical).pdf").is_file()
    assert not settings.storage_dir.exists()
