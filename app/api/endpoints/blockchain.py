from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.db.database import get_db
from app.models.user import User
from app.core.deps import get_current_user
from app.utils.aptos import retrieve_json_from_chain

router = APIRouter()

@router.get("/resources", response_model=List[Dict[str, Any]])
async def get_blockchain_resources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get resources associated with the user's Aptos account.
    """
    if not current_user.aptos_address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not have an Aptos address."
        )
    
    try:
        # Retrieve JSON resources from the blockchain
        result = retrieve_json_from_chain(current_user.aptos_address)
        
        if not result.get("success", False):
            return []
        
        # Return the resources
        if "json_data" in result:
            # If it's a dict, wrap it in a list
            if isinstance(result["json_data"], dict):
                return [result["json_data"]]
            # If it's already a list
            elif isinstance(result["json_data"], list):
                return result["json_data"]
        
        # Default empty response
        return []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving blockchain resources: {str(e)}"
        )

@router.get("/transactions", response_model=List[Dict[str, Any]])
async def get_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get transactions associated with the user's Aptos account.
    """
    if not current_user.aptos_address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not have an Aptos address."
        )
    
    # Get the user's documents to find transaction hashes
    documents = db.query(current_user.documents).all()
    
    transactions = []
    for doc in documents:
        if doc.transaction_hash:
            # Create a simplified transaction object
            transactions.append({
                "hash": doc.transaction_hash,
                "type": "store_json",
                "success": True,
                "timestamp": doc.created_at.isoformat() if doc.created_at else None,
                "gas_used": "Unknown",  # We don't store this information
                "sender": current_user.aptos_address,
                "document_id": doc.id,
                "filename": doc.filename
            })
    
    return transactions 