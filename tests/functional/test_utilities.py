import pytest
import tempfile
import os.path
import pathlib
import stat

from pytest_mock import MockerFixture

import simvue.utilities as sv_util

@pytest.mark.utilities
@pytest.mark.parametrize(
    "is_file,hash", [
        (True, "c7be1ed902fb8dd4d48997c6452f5d7e509fbcdbe2808b16bcf4edce4c07d14e"),
        (False, "50ea7be4eeb62777c05b06e21e9e5f6e8ce39442e7efbd17da8d57d5b18f5035")
    ]
)
def test_calculate_hash(is_file: bool, hash: str) -> None:
    if is_file:
        with tempfile.TemporaryDirectory() as tempd:
            with open(out_file := os.path.join(tempd, "temp.txt"), "w") as out_f:
                out_f.write("This is a test")
            assert sv_util.calculate_sha256(filename=out_file, is_file=is_file) == hash
    else:
        assert sv_util.calculate_sha256(filename="temp.txt", is_file=is_file) == hash

@pytest.mark.config
@pytest.mark.parametrize(
    "user_area", (True, False),
        ids=("permitted_dir", "out_of_user_area")
)
def test_find_first_file_search(user_area: bool, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    # Deactivate the server checks for this test
    monkeypatch.setenv("SIMVUE_NO_SERVER_CHECK", "True")
    monkeypatch.delenv("SIMVUE_TOKEN", False)
    monkeypatch.delenv("SIMVUE_URL", False)

    with tempfile.TemporaryDirectory() as temp_d:
        _path = pathlib.Path(temp_d)
        _path_sub = _path.joinpath("level_0")
        _path_sub.mkdir()

        for i in range(1, 5):
            _path_sub = _path_sub.joinpath(f"level_{i}")
            _path_sub.mkdir()
        mocker.patch("pathlib.Path.cwd", lambda *_: _path_sub)

        if user_area:
            _path.joinpath("level_0").joinpath("simvue.toml").touch()
            _path.chmod(stat.S_IXUSR)
            _result = sv_util.find_first_instance_of_file("simvue.toml", check_user_space=False)
        else:
            _path.chmod(stat.S_IXUSR)
            _result = sv_util.find_first_instance_of_file("simvue.toml", check_user_space=False) is None

        _path.chmod(stat.S_IRWXU)
        assert _result

@pytest.mark.config
def test_find_first_file_at_root(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    # Deactivate the server checks for this test
    monkeypatch.setenv("SIMVUE_NO_SERVER_CHECK", "True")
    monkeypatch.delenv("SIMVUE_TOKEN", False)
    monkeypatch.delenv("SIMVUE_URL", False)

    @property
    def _returns_self(self):
        return self


    with tempfile.TemporaryDirectory() as temp_d:
        _path = pathlib.Path(temp_d)
        _path_sub = _path.joinpath("level_0")
        _path_sub.mkdir()
        _path.joinpath("level_0").joinpath("simvue.toml").touch()

        for i in range(1, 5):
            _path_sub = _path_sub.joinpath(f"level_{i}")
            _path_sub.mkdir()
        mocker.patch("pathlib.Path.parent", _returns_self)
        mocker.patch("pathlib.Path.cwd", lambda *_: _path_sub)

        assert not sv_util.find_first_instance_of_file("simvue.toml", check_user_space=False)


