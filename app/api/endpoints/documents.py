import json
import os
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.crud.document import (
    create_document, 
    get_document, 
    get_document_by_tx_hash,
    get_documents_by_user, 
    get_documents_by_aptos_address
)
from app.db.database import get_db
from app.schemas.document import (
    DocumentResponse, 
    DocumentSearch, 
    ChunkSearchRequest, 
    ChunkSearchResponse, 
    TextChunk,
    ChatRequest,
    ChatResponse
)
from app.core.deps import get_current_active_user
from app.models.user import User
from app.utils.ipfs import IPFSClient
from app.utils.bigquery_storage import BigQueryPDFChunkStorage
from app.utils.llm import LLMService

# Set up logging
logger = logging.getLogger(__name__)

# Initialize BigQuery client if environment variables are set
BQ_PROJECT_ID = os.getenv("BQ_PROJECT_ID", "")
BQ_DATASET = os.getenv("BQ_DATASET", "")
BQ_TABLE = os.getenv("BQ_TABLE", "")
BQ_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials/key.json")

router = APIRouter()

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a PDF document, store it in IPFS, extract data, and store on Aptos blockchain.
    """
    # Check if the file is a PDF
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    # Read the file content
    content = await file.read()
    
    # Process the document
    result = create_document(
        db=db,
        user_id=current_user.id,
        filename=file.filename,
        file_content=content,
        user=current_user
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Error processing document")
        )
    
    # Prepare the response
    document = result["document"]
    document_response = DocumentResponse(
        id=document.id,
        filename=document.filename,
        ipfs_hash=document.ipfs_hash,
        transaction_hash=document.transaction_hash,
        aptos_address=document.aptos_address,
        extracted_data=json.loads(document.extracted_data),
        created_at=document.created_at
    )
    
    return document_response

@router.get("/my-documents", response_model=List[DocumentResponse])
def get_my_documents(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve all documents uploaded by the current user.
    """
    documents = get_documents_by_user(db, current_user.id, skip, limit)
    
    # Convert the extracted_data from JSON string to dict
    documents_response = []
    for doc in documents:
        doc_response = DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            ipfs_hash=doc.ipfs_hash,
            transaction_hash=doc.transaction_hash,
            aptos_address=doc.aptos_address,
            extracted_data=json.loads(doc.extracted_data),
            created_at=doc.created_at
        )
        documents_response.append(doc_response)
    
    return documents_response

@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document_by_id(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve a document by ID.
    """
    document = get_document(db, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check if the user has access to this document
    if document.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        ipfs_hash=document.ipfs_hash,
        transaction_hash=document.transaction_hash,
        aptos_address=document.aptos_address,
        extracted_data=json.loads(document.extracted_data),
        created_at=document.created_at
    )

@router.post("/search", response_model=List[DocumentResponse])
def search_documents(
    search: DocumentSearch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Search for documents by transaction hash or Aptos address.
    """
    documents = []
    
    if search.transaction_hash:
        doc = get_document_by_tx_hash(db, search.transaction_hash)
        if doc:
            documents = [doc]
    elif search.aptos_address:
        documents = get_documents_by_aptos_address(db, search.aptos_address)
    
    # Convert the extracted_data from JSON string to dict
    documents_response = []
    for doc in documents:
        doc_response = DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            ipfs_hash=doc.ipfs_hash,
            transaction_hash=doc.transaction_hash,
            aptos_address=doc.aptos_address,
            extracted_data=json.loads(doc.extracted_data),
            created_at=doc.created_at
        )
        documents_response.append(doc_response)
    
    return documents_response

@router.get("/ipfs/{ipfs_hash}")
def get_ipfs_content(
    ipfs_hash: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve content from IPFS by hash.
    """
    try:
        client = IPFSClient()
        content = client.cat(ipfs_hash)
        
        # Return the IPFS links since we can't directly return binary data
        return {
            "success": True,
            "ipfs_hash": ipfs_hash,
            "local_gateway_url": f"http://localhost:8080/ipfs/{ipfs_hash}",
            "public_gateway_url": f"https://ipfs.io/ipfs/{ipfs_hash}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving content from IPFS: {str(e)}"
        )

@router.post("/search-chunks", response_model=ChunkSearchResponse)
def search_document_chunks(
    search_request: ChunkSearchRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Search for text chunks in case files using advanced semantic search.
    """
    # Check if BigQuery configuration is available
    if not all([BQ_PROJECT_ID, BQ_DATASET, BQ_TABLE]):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BigQuery configuration not set. Please set BQ_PROJECT_ID, BQ_DATASET, and BQ_TABLE environment variables."
        )
    
    try:
        # Initialize LLM service for advanced query analysis
        llm_service = LLMService()
        if not llm_service.is_available():
            # Fall back to basic search if LLM is not available
            enhanced_query = search_request.query
            logger.warning("LLM service not available. Using original query for search.")
        else:
            # Analyze the intent of the search to determine best approach
            intent = llm_service.analyze_query_intent(search_request.query)
            logger.info(f"Search query intent detected: {intent['type']}")
            
            # For complex search queries, use multi-query approach
            if intent["type"] in ["comparison", "pattern", "relationship"]:
                search_queries = llm_service.generate_multi_query(search_request.query)
            else:
                # For simpler queries, use enhanced single query
                enhanced_query = llm_service.enhance_search_query(search_request.query)
                search_queries = [enhanced_query]
        
        # Create BigQuery client
        bq_storage = BigQueryPDFChunkStorage(
            project_id=BQ_PROJECT_ID,
            bq_dataset=BQ_DATASET,
            bq_table=BQ_TABLE,
            credentials_path=BQ_CREDENTIALS_PATH
        )
        
        # Execute search with all queries
        all_chunks = []
        seen_chunk_ids = set()
        
        # Use multiple queries if available, otherwise use the single enhanced query
        if 'search_queries' in locals():
            for query in search_queries:
                chunks = bq_storage.search_chunks(query, search_request.limit // len(search_queries) + 1)
                # Deduplicate chunks
                for chunk in chunks:
                    if chunk["chunk_id"] not in seen_chunk_ids:
                        all_chunks.append(chunk)
                        seen_chunk_ids.add(chunk["chunk_id"])
        else:
            # Fallback to single query
            all_chunks = bq_storage.search_chunks(enhanced_query, search_request.limit)
        
        # Convert to TextChunk model
        text_chunks = [
            TextChunk(
                chunk_id=chunk["chunk_id"],
                doc_id=chunk["doc_id"],
                filename=chunk["filename"],
                original_pdf_ipfs_path=chunk["original_pdf_ipfs_path"],
                text=chunk["text"]
            ) for chunk in all_chunks
        ]
        
        # Limit results to the requested amount
        text_chunks = text_chunks[:search_request.limit]
        
        return ChunkSearchResponse(results=text_chunks)
        
    except Exception as e:
        logger.error(f"Error searching case file chunks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching case file chunks: {str(e)}"
        )

@router.post("/chat", response_model=ChatResponse)
def chat_with_documents(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Chat with documents using RAG approach with advanced case file analysis.
    """
    # First search for relevant chunks
    if not all([BQ_PROJECT_ID, BQ_DATASET, BQ_TABLE]):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BigQuery configuration not set. Please set BQ_PROJECT_ID, BQ_DATASET, and BQ_TABLE environment variables."
        )
    
    try:
        # Initialize LLM service early for the entire pipeline
        llm_service = LLMService()
        if not llm_service.is_available():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LLM service not available. Please set the GEMINI_API_KEY environment variable."
            )
        
        # Analyze the query intent to determine approach
        intent = llm_service.analyze_query_intent(chat_request.query)
        logger.info(f"Query intent detected: {intent['type']}")
        
        # Use multi-query strategy for complex analysis to improve recall
        search_queries = []
        if intent["type"] in ["comparison", "pattern", "relationship"]:
            # For these complex query types, generate multiple search queries
            search_queries = llm_service.generate_multi_query(chat_request.query)
        else:
            # For simpler queries, use the enhanced query approach
            enhanced_query = llm_service.enhance_search_query(chat_request.query)
            search_queries = [enhanced_query]
            
        # Create BigQuery client
        bq_storage = BigQueryPDFChunkStorage(
            project_id=BQ_PROJECT_ID,
            bq_dataset=BQ_DATASET,
            bq_table=BQ_TABLE,
            credentials_path=BQ_CREDENTIALS_PATH
        )
        
        # Retrieve chunks using all generated queries (up to 3 per query)
        all_chunks = []
        seen_chunk_ids = set()
        
        for query in search_queries:
            chunks = bq_storage.search_chunks(query, 3)
            # Deduplicate chunks
            for chunk in chunks:
                if chunk["chunk_id"] not in seen_chunk_ids:
                    all_chunks.append(chunk)
                    seen_chunk_ids.add(chunk["chunk_id"])
        
        # Convert to TextChunk model
        text_chunks = [
            TextChunk(
                chunk_id=chunk["chunk_id"],
                doc_id=chunk["doc_id"],
                filename=chunk["filename"],
                original_pdf_ipfs_path=chunk["original_pdf_ipfs_path"],
                text=chunk["text"]
            ) for chunk in all_chunks
        ]
        
        # If no chunks found, return early
        if not text_chunks:
            return ChatResponse(
                answer="I couldn't find any relevant information in the case files to answer your question. Please try rephrasing your question or provide more specific details.",
                chunks=[]
            )
        
        # Generate response using the original query
        answer = llm_service.generate_response(
            query=chat_request.query,
            chunks=text_chunks,
            history=chat_request.history
        )
        
        return ChatResponse(answer=answer, chunks=text_chunks)
        
    except Exception as e:
        logger.error(f"Error in case file analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in case file analysis: {str(e)}"
        ) 