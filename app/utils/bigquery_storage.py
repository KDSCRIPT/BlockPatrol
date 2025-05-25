import uuid
import json
import gzip
import io
import nltk
import nltk.data
from nltk.tokenize import sent_tokenize
import logging
from google.cloud import bigquery
from typing import List, Dict
import os
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Download NLTK data
try:
    nltk.download('punkt', quiet=True)
    # Verify punkt is available
    nltk.data.find('tokenizers/punkt')
except LookupError:
    logger.warning("Initial NLTK download failed, retrying with explicit download...")
    import nltk.downloader
    nltk.downloader.download('punkt')

class BigQueryPDFChunkStorage:
    def __init__(self, project_id: str, bq_dataset: str, bq_table: str, credentials_path: str = None):
        """Initialize BigQuery client for PDF chunk storage."""
        if credentials_path and os.path.exists(credentials_path):
            self.bq_client = bigquery.Client.from_service_account_json(credentials_path)
        else:
            self.bq_client = bigquery.Client(project=project_id)
            
        self.bq_table = f"{project_id}.{bq_dataset}.{bq_table}"
        self.chunk_size = 1000
        self.chunk_overlap = 100
        # Get GCS bucket name from environment
        self.gcs_bucket_name = os.getenv("GCS_BUCKET_NAME", "")

    def chunk_text(self, text: str, doc_id: str) -> List[Dict]:
        """Split text into chunks with overlap."""
        chunks = []
        sentences = sent_tokenize(text)
        current_chunk = ""
        chunk_id = 0

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append({
                        "chunk_id": f"{doc_id}_{chunk_id}",
                        "doc_id": doc_id,
                        "text": current_chunk.strip(),
                    })
                    # Create overlap
                    overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                    current_chunk = overlap_text + sentence + " "
                    chunk_id += 1
                else:
                    current_chunk = sentence + " "

        if current_chunk:
            chunks.append({
                "chunk_id": f"{doc_id}_{chunk_id}",
                "doc_id": doc_id,
                "text": current_chunk.strip(),
            })

        return chunks

    def store_chunks_in_bigquery(self, chunks: List[Dict], metadata: Dict, filename: str, ipfs_path: str) -> Dict:
        """Store PDF chunks in BigQuery for search."""
        try:
            rows = []
            bucket_name = self.gcs_bucket_name if self.gcs_bucket_name else "placeholder-bucket"
            
            for chunk in chunks:
                # Use actual GCS bucket from environment or fall back to placeholder
                gcs_path = f"gs://{bucket_name}/{chunk['doc_id']}/{chunk['chunk_id']}.txt"
                
                rows.append({
                    "chunk_id": chunk['chunk_id'],
                    "doc_id": chunk['doc_id'],
                    "filename": filename,
                    "gcs_path": gcs_path,
                    "text": chunk['text'],
                    "original_pdf_ipfs_path": ipfs_path,
                    "pdf_metadata": json.dumps(metadata)
                })

            errors = self.bq_client.insert_rows_json(self.bq_table, rows)
            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
                return {
                    "success": False,
                    "error": f"BigQuery insert errors: {errors}"
                }
            else:
                logger.info(f"Inserted {len(rows)} chunks into BigQuery")
                return {
                    "success": True,
                    "chunks_count": len(rows)
                }
        except Exception as e:
            logger.error(f"Error storing chunks in BigQuery: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def process_pdf_for_bigquery(self, text: str, ipfs_path: str, filename: str, metadata: Dict) -> Dict:
        """Process PDF text and store chunks in BigQuery."""
        try:
            # Generate a unique document ID
            doc_id = str(uuid.uuid4())
            
            # Chunk the text
            chunks = self.chunk_text(text, doc_id)
            
            # Store chunks in BigQuery
            result = self.store_chunks_in_bigquery(chunks, metadata, filename, ipfs_path)
            
            return {
                "success": result["success"],
                "doc_id": doc_id,
                "chunks_count": len(chunks) if result["success"] else 0,
                "error": result.get("error", None)
            }
        except Exception as e:
            logger.error(f"Error processing PDF for BigQuery: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    def search_chunks(self, query: str, limit: int = 10) -> List[Dict]:
        """Search BigQuery for chunks matching the query."""
        try:
            # Escape special characters in the query that might cause issues with BigQuery SEARCH function
            # Escaping characters like ? ! ' " \ + - = & | > < ( ) { } [ ] ^ ~ * : /
            special_chars = ['\\', '?', '!', '"', "'", '+', '-', '=', '&', '|', '>', '<', '(', ')', '{', '}', '[', ']', '^', '~', '*', ':', '/']
            escaped_query = query
            for char in special_chars:
                escaped_query = escaped_query.replace(char, f"\\{char}")
            
            query_str = f"""
                SELECT chunk_id, doc_id, filename, original_pdf_ipfs_path, text
                FROM `{self.bq_table}`
                WHERE SEARCH(text, @query)
                LIMIT @limit
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("query", "STRING", escaped_query),
                    bigquery.ScalarQueryParameter("limit", "INT64", limit),
                ]
            )
            query_job = self.bq_client.query(query_str, job_config=job_config)
            return [dict(row) for row in query_job]
        except Exception as e:
            logger.error(f"Error searching BigQuery: {e}")
            return [] 