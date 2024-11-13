import time
import pytest
import uuid
import json
from simvue.api.objects.tag import Tag

@pytest.mark.api
def test_tag_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tag = Tag.new(name=f"test_tag_{_uuid}")
    _tag.commit()
    assert _tag.name == f"test_tag_{_uuid}"
    assert _tag.color
    assert not _tag.description
    _tag.delete()


@pytest.mark.api
def test_tag_creation_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tag = Tag.new(name=f"test_tag_{_uuid}", offline=True)
    _tag.commit()
    assert _tag.name == f"test_tag_{_uuid}"

    with pytest.raises(AttributeError):
        _tag.color

    _tag.delete()

    with _tag._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)

    assert not _local_data.get(_tag._label, {}).get(_tag.id)

@pytest.mark.api
def test_tag_modification_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tag = Tag.new(name=f"test_tag_{_uuid}")
    _tag.commit()
    time.sleep(1)
    _new_tag = Tag(_tag.id)
    _new_tag.name = _tag.name.replace("test", "test_modified")
    _new_tag.color = "rgb({r}, {g}, {b})".format(r=250, g=0, b=0)
    _new_tag.description = "modified test tag"
    _new_tag.commit()
    assert _new_tag.name == f"test_modified_tag_{_uuid}"
    assert _new_tag.color.r == 250 / 255
    assert _new_tag.description == "modified test tag"


@pytest.mark.api
def test_tag_modification_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tag = Tag.new(name=f"test_tag_{_uuid}", offline=True)
    _tag.commit()
    time.sleep(1)
    _new_tag = Tag(_tag.id)
    _new_tag.name = _tag.name.replace("test", "test_modified")
    _new_tag.color = "rgb({r}, {g}, {b})".format(r=250, g=0, b=0)
    _new_tag.description = "modified test tag"
    _new_tag.commit()
    assert _new_tag.name == f"test_modified_tag_{_uuid}"
    assert _new_tag.color.r == 250 / 255
    assert _new_tag.description == "modified test tag"
    _tag.delete()

