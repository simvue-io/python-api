from typing import Annotated, Dict, List, Optional, Union
from pydantic import BaseModel, Field, StringConstraints, PositiveInt

FOLDER_REGEX: str = r"^/.*"
NAME_REGEX: str = r"^[a-zA-Z0-9\-\_\s\/\.:]+$"
METRIC_KEY_REGEX: str = r"^[a-zA-Z0-9\-\_\s\/\.:=><]+$"

MetadataKeyString = Annotated[str, StringConstraints(pattern=r"^[\w\-\s\.]+$")]
TagString = Annotated[str, StringConstraints(pattern=r"^[\w\-\s\.]+$")]
MetricKeyString = Annotated[str, StringConstraints(pattern=METRIC_KEY_REGEX)]


# Pydantic class to validate run.init()
class RunInput(BaseModel):
    name: Optional[str] = Field(None, pattern=NAME_REGEX)
    metadata: Optional[Dict[MetadataKeyString, Union[str, int, float, None]]] = None
    tags: Optional[List[TagString]] = None
    description: Optional[str] = None
    folder: str = Field(pattern=FOLDER_REGEX)
    status: Optional[str] = None
    ttl: Optional[PositiveInt] = None
