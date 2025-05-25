from sqlalchemy.orm import Session
import json
import os

from app.models.document import Document
from app.models.user import User
from app.utils.ipfs import store_file_in_ipfs
from app.utils.pdf_extraction import process_pdf, get_raw_text
from app.utils.aptos import store_json_on_chain
from app.utils.bigquery_storage import BigQueryPDFChunkStorage

# Set default values for BigQuery configuration from environment variables
BQ_PROJECT_ID = os.getenv("BQ_PROJECT_ID", "")
BQ_DATASET = os.getenv("BQ_DATASET", "")
BQ_TABLE = os.getenv("BQ_TABLE", "")
BQ_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials/key.json")

def create_document(db: Session, user_id: int, filename: str, file_content, user: User):
    """Create a new document entry."""
    # Store the file in IPFS
    ipfs_result = store_file_in_ipfs(file_content, filename)
    if not ipfs_result["success"]:
        return {
            "success": False,
            "error": ipfs_result["error"]
        }
    
    # Process the PDF to extract data
    pdf_result = process_pdf(file_content)
    if not pdf_result["success"]:
        return {
            "success": False,
            "error": pdf_result["error"]
        }
    
    # Store the JSON data on the Aptos blockchain
    json_data = json.dumps(pdf_result["extracted_data"])
    blockchain_result = store_json_on_chain(
        user.aptos_address, 
        user.aptos_private_key, 
        json_data
    )
    if not blockchain_result["success"]:
        return {
            "success": False,
            "error": blockchain_result["error"]
        }
    
    # Create a document record in the database
    db_document = Document(
        filename=filename,
        ipfs_hash=ipfs_result["ipfs_hash"],
        transaction_hash=blockchain_result["transaction_hash"],
        user_id=user_id,
        aptos_address=user.aptos_address,
        extracted_data=json_data
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    # If BigQuery configuration is available, store chunks in BigQuery
    bigquery_result = {"success": True, "chunks_count": 0}
    if all([BQ_PROJECT_ID, BQ_DATASET, BQ_TABLE]):
        try:
            # Get raw text from PDF
            raw_text_result = get_raw_text(file_content)
            if raw_text_result["success"]:
                # Store chunks in BigQuery
                bq_storage = BigQueryPDFChunkStorage(
                    project_id=BQ_PROJECT_ID,
                    bq_dataset=BQ_DATASET,
                    bq_table=BQ_TABLE,
                    credentials_path=BQ_CREDENTIALS_PATH
                )
                
                bigquery_result = bq_storage.process_pdf_for_bigquery(
                    text=raw_text_result["text"],
                    ipfs_path=ipfs_result["ipfs_hash"],
                    filename=filename,
                    metadata=pdf_result["extracted_data"]
                )
        except Exception as e:
            bigquery_result = {
                "success": False,
                "error": f"BigQuery storage error: {str(e)}"
            }
    
    return {
        "success": True,
        "document": db_document,
        "ipfs_details": ipfs_result,
        "blockchain_details": blockchain_result,
        "extracted_data": pdf_result["extracted_data"],
        "bigquery_details": bigquery_result
    }

def get_document(db: Session, document_id: int):
    """Get a document by ID."""
    return db.query(Document).filter(Document.id == document_id).first()

def get_document_by_tx_hash(db: Session, tx_hash: str):
    """Get a document by transaction hash."""
    return db.query(Document).filter(Document.transaction_hash == tx_hash).first()

def get_documents_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    """Get all documents for a user."""
    return db.query(Document).filter(Document.user_id == user_id).offset(skip).limit(limit).all()

def get_documents_by_aptos_address(db: Session, aptos_address: str, skip: int = 0, limit: int = 100):
    """Get all documents for an Aptos address."""
    return db.query(Document).filter(Document.aptos_address == aptos_address).offset(skip).limit(limit).all()

def get_all_documents(db: Session, skip: int = 0, limit: int = 100):
    """Get all documents."""
    return db.query(Document).offset(skip).limit(limit).all() 