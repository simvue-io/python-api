import io

import pytest
from tenacity import wait_none

from simvue.api import request

_PAYLOAD = b"stable-file-contents"


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


@pytest.mark.local
@pytest.mark.parametrize("tuple_form", (False, True), ids=("file-object", "tuple"))
def test_post_retry_rewinds_file_stream(mocker, tuple_form: bool) -> None:
    payloads = []
    stream = io.BytesIO(_PAYLOAD)
    file_value = ("artifact.bin", stream) if tuple_form else stream

    def fake_post(*args, **kwargs):
        file = kwargs["files"]["file"]
        file = file[1] if isinstance(file, tuple) else file
        payloads.append(file.read())
        return _Response(503 if len(payloads) == 1 else 200)

    mocker.patch.object(request.requests, "post", side_effect=fake_post)

    response = request.post.retry_with(wait=wait_none())(
        "https://example.invalid",
        headers={},
        params={},
        data={},
        is_json=False,
        files={"file": file_value},
        timeout=1,
    )

    assert response.status_code == 200
    assert payloads == [_PAYLOAD, _PAYLOAD]


@pytest.mark.local
def test_put_retry_rewinds_data_stream(mocker) -> None:
    payloads = []
    stream = io.BytesIO(_PAYLOAD)

    def fake_put(*args, **kwargs):
        payloads.append(kwargs["data"].read())
        return _Response(503 if len(payloads) == 1 else 200)

    mocker.patch.object(request.requests, "put", side_effect=fake_put)

    response = request.put.retry_with(wait=wait_none())(
        "https://example.invalid",
        headers={},
        data=stream,
        is_json=False,
        timeout=1,
    )

    assert response.status_code == 200
    assert payloads == [_PAYLOAD, _PAYLOAD]
