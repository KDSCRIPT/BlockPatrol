import os
import shutil
import sys
import logging
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.api import api_router
from app.core.deps import get_current_admin_user
from app.db.database import engine, Base, get_db
from app.crud.user import create_admin_user
from app.utils.aptos import publish_module
from app.utils.llm import LLMService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Aptos PDF Storage API",
    description="API for storing PDF files on IPFS and their metadata on Aptos blockchain, with text chunk storage in BigQuery and RAG-based chat",
    version="0.1.0",
)

# Include API router
app.include_router(api_router)

# Flag to track if startup was successful
startup_successful = False
startup_error = None
bigquery_configured = False
llm_configured = False

@app.on_event("startup")
async def startup_event():
    """
    Initialize the application on startup.
    """
    global startup_successful, startup_error, bigquery_configured, llm_configured
    
    # Check if BigQuery is configured
    bq_project_id = os.getenv("BQ_PROJECT_ID", "")
    bq_dataset = os.getenv("BQ_DATASET", "")
    bq_table = os.getenv("BQ_TABLE", "")
    if all([bq_project_id, bq_dataset, bq_table]):
        bigquery_configured = True
        logger.info(f"BigQuery configured with project {bq_project_id}, dataset {bq_dataset}, table {bq_table}")
    else:
        logger.warning("BigQuery not fully configured. PDF chunk storage won't be available.")
        logger.warning("Please set BQ_PROJECT_ID, BQ_DATASET, and BQ_TABLE environment variables.")
    
    # Check if LLM is configured
    llm_service = LLMService()
    if llm_service.is_available():
        llm_configured = True
        logger.info("LLM service configured successfully.")
    else:
        logger.warning("LLM service not configured. RAG-based chat won't be available.")
        logger.warning("Please set the GEMINI_API_KEY environment variable.")
    
    # Get a DB session
    db = next(get_db())
    
    try:
        # Check if Aptos CLI is available
        if not shutil.which("aptos"):
            logger.warning("Aptos CLI not found in PATH. Module publishing will fail.")
            logger.warning("Please install the Aptos CLI: https://aptos.dev/cli-tools/aptos-cli-tool/install-aptos-cli")
        else:
            logger.info("Aptos CLI found in PATH.")
        
        # Create or update the admin user
        try:
            logger.info("Creating/getting admin user...")
            admin_user = create_admin_user(db)
            logger.info(f"Admin user created/found: {admin_user.username}")
            logger.info(f"Admin Aptos address: {admin_user.aptos_address}")
            
            # Get the admin's private key for publishing the module
            admin_private_key = admin_user.aptos_private_key
            logger.info(f"Retrieved admin private key (first 4 chars): {admin_private_key[:4]}...")
            
                        # Check for mock admin key
            if admin_private_key.startswith("0000"):
                logger.warning("Admin appears to be using a mock private key. This may cause blockchain operations to fail.")
                startup_error = "Admin using mock private key. Blockchain operations may fail."
            else:
                # Publish the Aptos module if needed
                logger.info("Attempting to compile and publish JSON storage module using admin account...")
                try:
                    # Pass both the private key and address to publish_module
                    publish_result = publish_module(
                        admin_private_key=admin_private_key, 
                        admin_address=admin_user.aptos_address
                    )
                    if publish_result:
                        logger.info("JSON storage module published successfully")
                        startup_successful = True
                    else:
                        logger.warning("Failed to publish JSON storage module")
                        startup_error = "Failed to publish JSON storage module"
                except Exception as e:
                    logger.error(f"Error publishing module: {str(e)}")
                    startup_error = f"Error publishing module: {str(e)}"
            
        except Exception as e:
            error_msg = f"Error with admin account: {str(e)}"
            logger.error(error_msg)
            import traceback
            traceback.print_exc()
            startup_error = error_msg
    except Exception as e:
        error_msg = f"Error during startup: {str(e)}"
        logger.error(error_msg)
        import traceback
        traceback.print_exc()
        startup_error = error_msg

@app.get("/")
async def root():
    """
    Root endpoint for the API.
    """
    return {
        "message": "Aptos PDF Storage API",
        "docs": "/docs",
        "redoc": "/redoc",
        "startup_successful": startup_successful,
        "startup_error": startup_error,
        "features": {
            "blockchain_storage": startup_successful,
            "chunk_storage": bigquery_configured,
            "rag_chat": llm_configured
        }
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    if not startup_successful and startup_error:
        return {
            "status": "warning",
            "blockchain_connected": startup_successful,
            "bigquery_configured": bigquery_configured,
            "llm_configured": llm_configured,
            "error": startup_error
        }
    return {
        "status": "healthy", 
        "blockchain_connected": startup_successful,
        "bigquery_configured": bigquery_configured,
        "llm_configured": llm_configured
    } 