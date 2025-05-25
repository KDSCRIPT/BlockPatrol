from fastapi import APIRouter

from app.api.endpoints import auth, documents, blockchain

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(blockchain.router, prefix="/blockchain", tags=["blockchain"]) 