from datetime import datetime

from pydantic import BaseModel
from typing import Optional, List, Dict, Union
from enum import Enum

# Pydantic class to validate run.init()
class RunInput(BaseModel):
    name: Optional[str]
    metadata: Optional[Dict[str, Union[str, int, float, None]]]
    tags: Optional[List[str]]
    description: Optional[str]
    folder: str
    status: Optional[str]
