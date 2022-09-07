from simtrack import client
import pytest
 
def test_supress_errors():
    """
    Check that errors are surpressed
    """
    
    simt = client.Simtrack()

    with pytest.raises(RuntimeError, match="value must be boolean") as exc_info:
        simt.suppress_errors(200)

 
