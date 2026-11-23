from soarshelf.build import build


def test_build_fails_on_missing_content_folder(tmp_path):
    assert build(tmp_path / "nope", tmp_path / "out") == 1
