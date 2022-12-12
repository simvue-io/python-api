from datetime import datetime

import re
from pydantic import BaseModel, constr
from typing import Optional, List, Dict, Union
from enum import Enum

FolderStrRegex = constr(regex=r"^/.*")

# Pydantic class to validate run.init()
class RunInput(BaseModel):
    name: Optional[str]
    metadata: Optional[Dict[str, Union[str, int, float, None]]]
    tags: Optional[List[str]]
    description: Optional[str]
    folder: FolderStrRegex
    status: Optional[str]
