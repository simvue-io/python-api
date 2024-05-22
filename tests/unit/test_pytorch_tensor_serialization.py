import pytest
from simvue.serialization import Serializer, Deserializer

try:
    import torch
except ImportError:
    torch = None

@pytest.mark.skipif(not torch, reason="Torch is not installed")
def test_pytorch_tensor_serialization():
    """
    Check that a PyTorch tensor can be serialized then deserialized successfully
    """
    torch.manual_seed(1724)
    array = torch.rand(2, 3)

    serialized, mime_type = Serializer().serialize(array)
    array_out = Deserializer().deserialize(serialized, mime_type)

    assert (array == array_out).all()
