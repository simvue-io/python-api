from datetime import datetime

from pydantic import BaseModel
from typing import Optional, List, Dict, Union
from enum import Enum

class RunInput(BaseModel):
    name: Optional[str]
    metadata: Optional[Dict[str, Union[str, int, float, None]]]
    tags: Optional[List[str]]
    description: Optional[str]
    system: Dict
    folder: str
    status: Optional[str]
