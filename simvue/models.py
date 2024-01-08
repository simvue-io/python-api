from pydantic import BaseModel, constr
from typing import Optional, List, Dict, Union

FolderStrRegex = constr(regex=r"^/.*")
NameRegex = constr(regex=r"^[a-zA-Z0-9\-\_\s\/\.:]+$")

# Pydantic class to validate run.init()
class RunInput(BaseModel):
    name: Optional[NameRegex]
    metadata: Optional[Dict[str, Union[str, int, float, None]]]
    tags: Optional[List[str]]
    description: Optional[str]
    folder: FolderStrRegex
    status: Optional[str]
    ttl: int
