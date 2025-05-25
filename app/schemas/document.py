from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, Optional, List

class DocumentBase(BaseModel):
    filename: str
    
class DocumentCreate(DocumentBase):
    pass

class DocumentInDB(DocumentBase):
    id: int
    ipfs_hash: str
    transaction_hash: str
    user_id: int
    aptos_address: str
    extracted_data: str
    created_at: datetime
    
    class Config:
        orm_mode = True

class DocumentResponse(DocumentBase):
    id: int
    ipfs_hash: str
    transaction_hash: str
    aptos_address: str
    extracted_data: Dict[str, Any]
    created_at: datetime
    
    class Config:
        orm_mode = True

class DocumentSearch(BaseModel):
    transaction_hash: Optional[str] = None
    aptos_address: Optional[str] = None 

class TextChunk(BaseModel):
    chunk_id: str
    doc_id: str
    filename: str
    original_pdf_ipfs_path: str
    text: str

class ChunkSearchRequest(BaseModel):
    query: str
    limit: int = 10

class ChunkSearchResponse(BaseModel):
    results: List[TextChunk]

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    query: str
    history: Optional[List[ChatMessage]] = None

class ChatResponse(BaseModel):
    answer: str
    chunks: List[TextChunk] 