from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union

FOLDER_REGEX: str = r"^/.*"
NAME_REGEX: str = r"^[a-zA-Z0-9\-\_\s\/\.:]+$"

# Pydantic class to validate run.init()
class RunInput(BaseModel):
    name: Optional[str] = Field(
        None,
        pattern=NAME_REGEX
    )
    metadata: Optional[Dict[str, Union[str, int, float, None]]] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    folder: str = Field(pattern=FOLDER_REGEX)
    status: Optional[str] = None
    ttl: int