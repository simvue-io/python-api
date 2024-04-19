import pytest
import tempfile

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
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_f:
            with open(temp_f.name, "w") as out_f:
                out_f.write("This is a test")
            assert sv_util.calculate_sha256(filename=temp_f.name, is_file=is_file) == hash
    else:
        assert sv_util.calculate_sha256(filename="temp.txt", is_file=is_file) == hash
