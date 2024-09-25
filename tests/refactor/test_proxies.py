import pytest

from simvue.factory.proxy import Simvue

@pytest.mark.proxy
def test_simvue_url_check() -> None:
    """Checks the Token/URL checker"""
    remote = Simvue(
        name="",
        uniq_id="",
        mode="online",
        suppress_errors=False
    )
    assert remote.check_token()

