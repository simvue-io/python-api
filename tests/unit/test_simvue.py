import os
from simvue import Run
import pytest

import numpy as np
import simvue.run as simvue_run
import pickle



def test_suppress_errors():
    """
    Check that errors are surpressed
    """
    run = Run()

    with pytest.raises(RuntimeError, match="suppress_errors must be boolean"):
        run.config(suppress_errors=200)

def test_save_input_pickle_file():
    """
    Pass a pickleable object e.g. nparray and check that a file is created which matches the nparray
    """
    arr = np.array([1,2,3,4,5])
    
    temp_filename = simvue_run.get_filename_input(arr, 'name_tag')
    filehandle = open(temp_filename, 'rb')
    assert np.array_equal(arr, pickle.load(filehandle))
    filehandle.close()

    # Delete the temp file
    os.remove(temp_filename)  

def test_save_input_file():
    """
    Pass a filename and check that if the file is invalid and exception is raised
    """
    with pytest.raises(Exception) as exc_info:
        temp_filename = simvue_run.get_filename_input('nonexistant_file.doc', 'name_tag')

    assert str(exc_info.value) == "File nonexistant_file.doc does not exist"
