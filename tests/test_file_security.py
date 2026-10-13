import pytest

from app.services.file_service import FileService, InvalidStoragePathError, sanitize_filename


@pytest.fixture
def fs(tmp_path):
    return FileService(tmp_path / "storage", 1024, 1024)


@pytest.mark.parametrize(
    "bad",
    ["../secret", "documents/../../secret", "/etc/passwd", "documents\\..\\x", "", "other/x.pdf", "documents/./x", "documents/a\x00b"],
)
def test_resolve_rejects_traversal(fs, bad):
    with pytest.raises(InvalidStoragePathError):
        fs.resolve(bad)


def test_resolve_accepts_normal_path(fs):
    assert fs.resolve("documents/abc/def.pdf").is_relative_to(fs.root)


def test_resolve_rejects_symlink_escape(fs, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (fs.root / "documents" / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(InvalidStoragePathError):
        fs.resolve("documents/link/x.pdf")


def test_delete_never_leaves_storage(fs, tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("x")
    fs.delete("../victim.txt")
    assert victim.exists()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("C:\\Users\\x\\bericht.pdf", "bericht.pdf"),
        ("a<b>|c?.pdf", "a_b__c_.pdf"),
        ("..", "datei"),
        (None, "datei"),
        ("Größe.pdf", "Größe.pdf"),
        ("evil\x00.pdf", "evil.pdf"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


@pytest.mark.parametrize("name", ["..%2f..%2fetc%2fpasswd", "..", "x.png", "%2e%2e%2fsecret.png", "A" * 32 + ".png", "a" * 32 + ".svg"])
def test_media_route_rejects_unexpected_names(anon, name):
    assert anon.get(f"/media/images/{name}").status_code == 404


def test_documents_are_not_served_via_media(anon, document):
    assert anon.get("/media/documents/x.pdf").status_code == 404


def test_no_traceback_leak(anon):
    r = anon.get("/api/admin/does-not-exist")
    assert r.status_code in (401, 404) and "Traceback" not in r.text
