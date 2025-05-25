# PDF Processing Pipeline with GCP and Streamlit

This guide provides detailed instructions on how to set up and run the PDF Processing Pipeline application, which allows uploading PDF files, storing them on IPFS, extracting data, and analyzing them using Google Cloud services and Gemini AI.

## Prerequisites

- Python 3.8+
- Google Cloud Platform account
- Gemini API key (for LLM features)
- IPFS node

## Installation Steps

### 1. Clone and Install Dependencies

```bash
# Clone the repository (if applicable)
git clone <repository-url>
cd <repository-directory>

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install NLTK data (required for text processing)
python -c "import nltk; nltk.download('punkt')"
```

### 2. Set Up Google Cloud Platform

The application uses Google Cloud Storage for storing text chunks and BigQuery for efficient search. You need to set up these services in your GCP project.

#### Automated Setup (Using Google Cloud Shell):

The `setup_gcp.sh` script can be run in the Google Cloud Shell to automate the setup process:

1. Open [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the Cloud Shell icon (>_) in the top right corner
3. Upload the `setup_gcp.sh` script to Cloud Shell
4. Make it executable and run it:

```bash
# Make the script executable
chmod +x setup_gcp.sh

# Review and edit the script variables at the top before running
# Specifically, set your PROJECT_ID and BILLING_ACCOUNT and REGION

# Run the setup script
./setup_gcp.sh
```

#### Manual Setup (Step by Step):

Follow these steps in the Google Cloud Console (https://console.cloud.google.com/):

1. **Create a new Google Cloud Project**:
   - Go to the [Manage Resources page](https://console.cloud.google.com/cloud-resource-manager)
   - Click "CREATE PROJECT"
   - Enter a project name and select a billing account
   - Click "CREATE"

2. **Enable Required APIs**:
   - Navigate to [API Library](https://console.cloud.google.com/apis/library)
   - Search for and enable each of these APIs:
     - Cloud Storage API
     - BigQuery API
     - BigQuery Storage API
     - Cloud Resource Manager API
     - IAM API
     - AI Platform API (for Vertex AI embeddings)

3. **Create a Cloud Storage bucket**:
   - Go to [Cloud Storage browser](https://console.cloud.google.com/storage/browser)
   - Click "CREATE BUCKET"
   - Name your bucket (must be globally unique)
   - Choose Region (e.g., us-central1)
   - Leave other settings as default
   - Click "CREATE"

4. **Create a BigQuery dataset**:
   - Go to [BigQuery Console](https://console.cloud.google.com/bigquery)
   - In your project, click "CREATE DATASET"
   - Enter Dataset ID (e.g., pdf_processing)
   - Choose location (match your GCS bucket region for best performance)
   - Click "CREATE DATASET"

5. **Create a BigQuery table**:
   - In your new dataset, click "CREATE TABLE"
   - Source: Empty table
   - Destination: 
     - Table name: pdf_chunks
     - Schema: Click "EDIT AS TEXT" and paste this schema:
     ```
     chunk_id:STRING,doc_id:STRING,filename:STRING,gcs_path:STRING,original_pdf_ipfs_path:STRING,text:STRING,embedding:FLOAT64[],pdf_metadata:STRING
     ```
   - Click "CREATE TABLE"

6. **Create a Service Account**:
   - Go to [IAM & Admin > Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
   - Click "CREATE SERVICE ACCOUNT"
   - Name: pdf-processor
   - Grant required roles:
     - Storage Admin
     - BigQuery Admin
     - Service Account User
   - Click "DONE"

7. **Create and download a key**:
   - Find your service account in the list
   - Click the three dots menu > "Manage keys"
   - Click "ADD KEY" > "Create new key"
   - Choose JSON format
   - Click "CREATE" (This downloads a JSON key file)
   - Store this file securely - you'll need it for your application

8. **Create a search index for your BigQuery table** (Optional - for better search performance):
   - Go to the BigQuery console
   - Navigate to your table
   - Click "CREATE SEARCH INDEX"
   - Name your index (e.g., pdf_chunks_text_index)
   - Select the "text" column
   - Click "CREATE"

### 3. Environment Configuration

Create a `.env` file in the root directory based on the `env.example` file:

```bash
# Copy the example file
cp env.example .env

# Edit the .env file with your own values
```

Key environment variables to configure:

```
# Google Cloud Settings
PROJECT_ID=your-google-cloud-project-id
REGION=us-central1
GCS_BUCKET_NAME=your-gcs-bucket-name
BQ_DATASET=your-bigquery-dataset
BQ_TABLE=your-bigquery-table
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json

# Gemini API for LLM features
GEMINI_API_KEY=your-gemini-api-key

# IPFS Settings
IPFS_API_URL=http://127.0.0.1:5001

# JWT Authentication Settings
SECRET_KEY=your_super_secure_secret_key_change_this_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Admin User Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=strong-password
ADMIN_EMAIL=admin@example.com

# Aptos Blockchain Settings (if using blockchain features)
APTOS_NODE_URL=https://fullnode.testnet.aptoslabs.com/v1
```

### 4. Running the Application

You have two options for running the application:

#### Option 1: FastAPI Backend with Streamlit Frontend (Recommended)

This runs both the backend API server and the Streamlit frontend:

```bash
# Start the FastAPI backend server
python run.py

# In a new terminal window, start the Streamlit frontend
streamlit run streamlit_app.py
```

The FastAPI server will run at http://localhost:8000 (API documentation available at http://localhost:8000/docs)
The Streamlit frontend will run at http://localhost:8501

#### Option 2: Standalone Streamlit App

This runs a simplified version focused on PDF processing without the authentication/blockchain features:

```bash
streamlit run app.py
```

The Streamlit app will run at http://localhost:8501

## Usage Guide

### Using the Streamlit Web Interface

1. When using the streamlit_app.py version:
   - Sign up for an account
   - Log in with your credentials
   - Navigate through the sidebar to access different features:
     - Dashboard: View system status and your account information
     - Upload Document: Upload PDF files to the system
     - My Documents: View your uploaded documents
     - Chat with Documents: Ask questions about your documents using Gemini AI
     - Blockchain Explorer: View metadata stored on the blockchain

2. When using the app.py version:
   - Configure the pipeline using the sidebar settings (IPFS API URL, Service Account, Gemini API Key)
   - Click "Initialize Pipeline" 
   - Upload PDF files using the file uploader
   - Search document chunks directly or using the Gemini-powered natural language search

### Using the API Directly

API endpoints from the FastAPI backend (available at http://localhost:8000):

- Authentication:
  - `POST /auth/signup`: Create a new user account
  - `POST /auth/login`: Log in and get an access token

- Documents:
  - `POST /documents/upload`: Upload a PDF file
  - `GET /documents/my-documents`: List your uploaded documents
  - `GET /documents/documents/{document_id}`: Get a specific document
  - `POST /documents/search`: Search documents
  - `GET /documents/ipfs/{ipfs_hash}`: Retrieve content from IPFS

- Text Chunks and RAG:
  - `POST /documents/search-chunks`: Search text chunks in BigQuery
  - `POST /documents/chat`: Chat with documents using RAG

## Troubleshooting

### Google Cloud Issues

- Verify your service account key is correct and has the necessary permissions
- Ensure the `GOOGLE_APPLICATION_CREDENTIALS` environment variable points to your service account key file
- Check that all required APIs are enabled in your Google Cloud project
- Verify bucket and dataset/table exist and have the correct schemas
- Ensure you have sufficient permissions and quota in your GCP project

### Streamlit Connection Issues

- Ensure the FastAPI backend is running when using the streamlit_app.py frontend
- Check the API_URL constant in streamlit_app.py matches your backend URL (default: http://localhost:8000)

## Additional Information

For more details on specific components:
- Review the README.md file for an overview of the application architecture
- Check streamlit_readme.md for Streamlit-specific documentation 