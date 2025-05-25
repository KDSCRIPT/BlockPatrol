# Aptos PDF Storage API with BigQuery and RAG

This application provides a secure way to store PDF files on IPFS, extract meaningful data from them, and store both metadata on the Aptos blockchain and text chunks in BigQuery for efficient searching and RAG-based chatting.

## Features

- **PDF Storage**: Upload PDF files to IPFS for decentralized storage
- **Data Extraction**: Extract structured data from PDFs
- **Blockchain Storage**: Store extracted metadata on Aptos blockchain
- **Text Chunk Storage**: Store chunks of PDF text in BigQuery for efficient search
- **RAG-Based Chat**: Chat with your documents using LLM-powered retrieval augmented generation

## Requirements

- Python 3.8+
- FastAPI
- Google Cloud account (for BigQuery)
- Aptos account
- Gemini API key (for LLM features)
- IPFS node (can use local or remote)

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables in a `.env` file:
   ```env
   # BigQuery Configuration
   BQ_PROJECT_ID=your-google-cloud-project-id
   BQ_DATASET=your-bigquery-dataset
   BQ_TABLE=your-bigquery-table
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
   
   # Gemini API 
   GEMINI_API_KEY=your-gemini-api-key
   
   # Aptos Configuration (existing variables)
   APTOS_NODE_URL=https://fullnode.devnet.aptoslabs.com/v1
   ADMIN_PRIVATE_KEY=your-admin-private-key
   ```
4. Create BigQuery table:
   ```sql
   CREATE TABLE `your-project-id.your-dataset.your-table` (
     chunk_id STRING,
     doc_id STRING,
     filename STRING,
     text STRING,
     original_pdf_ipfs_path STRING,
     pdf_metadata STRING
   ) 
   ```

## Running the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000. You can access the interactive documentation at http://localhost:8000/docs.

## API Endpoints

### Authentication
- `POST /auth/register`: Register a new user
- `POST /auth/token`: Login and get access token

### Documents
- `POST /documents/upload`: Upload a PDF file
- `GET /documents/my-documents`: Get a list of your uploaded documents
- `GET /documents/documents/{document_id}`: Get a specific document
- `POST /documents/search`: Search documents by transaction hash or Aptos address
- `GET /documents/ipfs/{ipfs_hash}`: Retrieve content from IPFS by hash

### Text Chunks and RAG
- `POST /documents/search-chunks`: Search text chunks in BigQuery
  ```json
  {
    "query": "your search term",
    "limit": 10
  }
  ```

- `POST /documents/chat`: Chat with documents using RAG
  ```json
  {
    "query": "your question about the documents",
    "history": [
      {"role": "user", "content": "previous question"},
      {"role": "assistant", "content": "previous answer"}
    ]
  }
  ```

## Environment Setup

### BigQuery Setup

1. Create a Google Cloud Project
2. Enable the BigQuery API
3. Create a service account with BigQuery permissions
4. Download the service account key JSON file
5. Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to this file
6. Create a dataset and table in BigQuery with the proper schema

### Gemini API Setup

1. Sign up for Gemini API at https://ai.google.dev/
2. Create an API key
3. Set the `GEMINI_API_KEY` environment variable

## License

MIT
