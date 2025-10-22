import time
import contextlib
import pytest
import uuid
import json
import pydantic.color
from simvue.api.objects.tag import Tag
from simvue.sender import Sender

@pytest.mark.api
@pytest.mark.online
def test_tag_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tag = Tag.new(name=f"test_tag_{_uuid}")
    _tag.commit()
    assert _tag.name == f"test_tag_{_uuid}"
    assert _tag.colour
    assert not _tag.description
    _tag.delete()


@pytest.mark.api
@pytest.mark.offline
def test_tag_creation_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tag = Tag.new(name=f"test_tag_{_uuid}", offline=True)
    _tag.commit()
    assert _tag.name == f"test_tag_{_uuid}"

    with pytest.raises(AttributeError):
        _tag.colour

    with _tag._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
        
    assert _local_data.get("name") == f"test_tag_{_uuid}"
    
    _sender = Sender(_tag._local_staging_file.parents[1], 1, 10, throw_exceptions=True)
    _sender.upload(["tags"])
    time.sleep(1)
    
    _online_id = _sender.id_mapping.get(_tag.id)
    
    _online_tag = Tag(_online_id)
    assert _online_tag.name == f"test_tag_{_uuid}"
    _online_tag.read_only(False)
    _online_tag.delete()
    
    
    

@pytest.mark.api
@pytest.mark.online
def test_tag_modification_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tag = Tag.new(name=f"test_tag_{_uuid}")
    _tag.commit()
    time.sleep(1)
    _new_tag = Tag(_tag.id)
    _new_tag.read_only(False)
    _new_tag.name = _tag.name.replace("test", "test_modified")
    _new_tag.colour = "rgb({r}, {g}, {b})".format(r=250, g=0, b=0)
    _new_tag.description = "modified test tag"
    _new_tag.commit()
    assert _new_tag.name == f"test_modified_tag_{_uuid}"
    assert _new_tag.colour.r == 250 / 255
    assert _new_tag.description == "modified test tag"


@pytest.mark.api
@pytest.mark.offline
def test_tag_modification_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tag = Tag.new(name=f"test_tag_{_uuid}", offline=True)
    _tag.commit()
    
    with _tag._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
        
    assert _local_data.get("name") == f"test_tag_{_uuid}"
    
    _sender = sender(_tag._local_staging_file.parents[1], 1, 10, throw_exceptions=True)
    _sender.upload(["tags"])
    _online_id = _sender.id_mapping.get(_tag.id)
    _online_tag = Tag(_online_id)
    
    assert _online_tag.name == f"test_tag_{_uuid}"
    
    _new_tag = Tag(_tag.id)
    _new_tag.read_only(False)
    _new_tag.name = _tag.name.replace("test", "test_modified")
    _new_tag.colour = "rgb({r}, {g}, {b})".format(r=250, g=0, b=0)
    _new_tag.description = "modified test tag"
    _new_tag.commit()
    
    # Check since not yet sent, online not changed
    _online_tag.refresh()
    assert _online_tag.name == f"test_tag_{_uuid}"
    
    with _tag._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
    assert _local_data.get("name") == f"test_modified_tag_{_uuid}"
    assert pydantic.color.parse_str(_local_data.get("colour")).r == 250 / 255
    assert _local_data.get("description") == "modified test tag"
    
    _sender = Sender(_tag._local_staging_file.parents[1], 1, 10, throw_exceptions=True)
    _sender.upload(["tags"])
    time.sleep(1)
    
    # Check online version is updated
    _online_tag.refresh()
    assert _online_tag.name == f"test_modified_tag_{_uuid}"
    assert _online_tag.colour.r == 250 / 255
    assert _online_tag.description == "modified test tag"
    
    _online_tag.read_only(False)
    _online_tag.delete()


@pytest.mark.api
@pytest.mark.online
def test_tag_get_properties() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tag = Tag.new(name=f"test_tag_{_uuid}")
    _tag.commit()
    _failed = []

    for member in _tag._properties:
        try:
            getattr(_tag, member)
        except Exception as e:
            _failed.append((member, f"{e}"))
    with contextlib.suppress(Exception):
        _tag.delete()

    if _failed:
        raise AssertionError("\n" + "\n\t- ".join(": ".join(i) for i in _failed))
