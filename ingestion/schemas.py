from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime
class Chunk(BaseModel):
    chunk_id: str
    source_doc: str
    doc_type: Literal["procedure", "report", "worklog", "drawing", "inspection"]
    content: str
    row_index: Optional[int] = None      # for table chunks
    bbox: Optional[list[float]] = None   # for drawing regions [x0,y0,x1,y1]
    page_number: Optional[int] = None
class ExtractedEntity(BaseModel):
    entity_type: Literal["Equipment", "Permit", "Person", "Regulation", "Incident", "Parameter", "Date"]
    value: str
    normalized_value: str   # e.g. "P-04A" -> "PUMP-04A"
    chunk_id: str
    confidence: float
class ExtractionResult(BaseModel):
    chunk_id: str
    entities: list[ExtractedEntity]
    relationships: list[dict]  # {"from": ..., "to": ..., "type": "MAINTAINED_BY"} this fine