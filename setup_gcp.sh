#!/bin/bash
# Google Cloud Project Setup Script for PDF Processing Pipeline
# This script sets up a complete Google Cloud environment for the PDF processing application

# Exit on error
set -e

# --- BEGIN USER CONFIGURATION ---
# PLEASE REVIEW AND UPDATE THESE VARIABLES BEFORE RUNNING THE SCRIPT:

# 1. PROJECT_ID: Choose a globally unique ID for your new project.
#    If the default ID below is already taken, the script will fail.
#    You can change it here or the script will guide you if creation fails.
PROJECT_ID="qwiklabs-gcp-02-064a3eec3a9c"  # Appends a random number to increase uniqueness

# 2. PROJECT_NAME: A user-friendly name for your project.
PROJECT_NAME="PDF Processing Pipeline"

# 3. BILLING_ACCOUNT: Your Google Cloud Billing Account ID.
#    This is REQUIRED. The script will prompt you if it's not set.
#    Find your Billing Account ID by running: gcloud billing accounts list
BILLING_ACCOUNT="014F8D-C0020C-E4D2D3"

# 4. REGION: The default region for your resources.
REGION="us-west1"

# --- END USER CONFIGURATION ---

# Derived variables (usually no need to change these)
ZONE="${REGION}-a"
BQ_DATASET="pdf_processing"
BQ_TABLE="pdf_chunks"
GCS_BUCKET="${PROJECT_ID}-chunks"
SERVICE_ACCOUNT_NAME="pdf-processor"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print with color
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# --- SCRIPT EXECUTION STARTS HERE ---

print_info "Starting Google Cloud Project Setup..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI is not installed. Please visit https://cloud.google.com/sdk/docs/install to install it."
    exit 1
fi

# Check if user is logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q @; then
    print_error "You are not logged into gcloud. Please run 'gcloud auth login' and follow the prompts."
    exit 1
fi
print_success "gcloud CLI is installed and user is logged in."

# Validate Billing Account ID
if [ -z "$BILLING_ACCOUNT" ]; then
    print_error "BILLING_ACCOUNT variable is not set in the script."
    print_info "Please edit the script and set the BILLING_ACCOUNT variable."
    print_info "You can list your available billing accounts using: gcloud billing accounts list"
    exit 1
fi
print_info "Using Billing Account ID: $BILLING_ACCOUNT"

# Create new project
print_info "Attempting to create new Google Cloud project: ${PROJECT_NAME} (ID: ${PROJECT_ID})..."
if gcloud projects describe ${PROJECT_ID} &>/dev/null; then
    print_warning "Project ${PROJECT_ID} already exists. Skipping creation."
else
    if gcloud projects create ${PROJECT_ID} --name="${PROJECT_NAME}"; then
        print_success "Project ${PROJECT_ID} created successfully."
    else
        print_error "Failed to create project ${PROJECT_ID}. It might be taken or there could be other issues."
        print_info "Please try a different PROJECT_ID in the script or create the project manually via the Google Cloud Console."
        exit 1
    fi
fi

# Set as default project
print_info "Setting ${PROJECT_ID} as the default project for gcloud commands..."
gcloud config set project ${PROJECT_ID}

# Link billing account to project
print_info "Linking Billing Account ${BILLING_ACCOUNT} to project ${PROJECT_ID}..."
if gcloud billing projects describe ${PROJECT_ID} | grep -q "billingAccountName: billingAccounts/${BILLING_ACCOUNT}"; then
    print_warning "Project ${PROJECT_ID} is already linked to Billing Account ${BILLING_ACCOUNT}."
else
    if gcloud billing projects link ${PROJECT_ID} --billing-account=${BILLING_ACCOUNT}; then
        print_success "Billing Account linked successfully to project ${PROJECT_ID}."
    else
        print_error "Failed to link Billing Account ${BILLING_ACCOUNT} to project ${PROJECT_ID}."
        print_info "Please ensure the billing account ID is correct and you have permissions to link it."
        print_info "You can try linking it manually in the Google Cloud Console."
        exit 1
    fi
fi

# Enable required APIs
APIS_TO_ENABLE=(
    storage-api.googleapis.com
    bigquery.googleapis.com
    bigquerystorage.googleapis.com
    cloudresourcemanager.googleapis.com
    iam.googleapis.com
    aiplatform.googleapis.com  # For Vertex AI embeddings
)
print_info "Enabling required APIs for project ${PROJECT_ID}..."
ENABLED_APIS=$(gcloud services list --enabled --project=${PROJECT_ID} --format="value(config.name)")

for API in "${APIS_TO_ENABLE[@]}"; do
    if echo "${ENABLED_APIS}" | grep -qw "${API}"; then
        print_warning "API [${API}] is already enabled."
    else
        print_info "Enabling API [${API}]..."
        if gcloud services enable ${API} --project=${PROJECT_ID}; then
            print_success "API [${API}] enabled successfully."
        else
            print_error "Failed to enable API [${API}]. Please try enabling it manually in the Google Cloud Console."
            exit 1
        fi
    fi
done
print_success "All required APIs are enabled."

# Create GCS bucket
print_info "Creating GCS bucket for chunks: gs://${GCS_BUCKET}..."
if gcloud storage buckets describe gs://${GCS_BUCKET} --project=${PROJECT_ID} &>/dev/null; then
    print_warning "GCS bucket gs://${GCS_BUCKET} already exists. Skipping creation."
else
    if gcloud storage buckets create gs://${GCS_BUCKET} --project=${PROJECT_ID} --location=${REGION} --uniform-bucket-level-access; then
        print_success "GCS bucket gs://${GCS_BUCKET} created successfully."
    else
        print_error "Failed to create GCS bucket gs://${GCS_BUCKET}."
        exit 1
    fi
fi

# Create BigQuery dataset
print_info "Creating BigQuery dataset: ${BQ_DATASET}..."
if bq --project_id=${PROJECT_ID} ls --datasets | grep -qw ${BQ_DATASET}; then
    print_warning "BigQuery dataset ${BQ_DATASET} already exists. Skipping creation."
else
    if bq --location=${REGION} --project_id=${PROJECT_ID} mk --dataset --description "Dataset for PDF processing and RAG" ${PROJECT_ID}:${BQ_DATASET}; then
        print_success "BigQuery dataset ${BQ_DATASET} created successfully."
    else 
        print_error "Failed to create BigQuery dataset ${BQ_DATASET}."
        exit 1
    fi
fi

# Create BigQuery table schema file (temporary)
BQ_SCHEMA_FILE="bq_schema_temp.json"
print_info "Defining BigQuery table schema in ${BQ_SCHEMA_FILE}..."
cat > ${BQ_SCHEMA_FILE} << EOL
[
  {"name": "chunk_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique identifier for the chunk"},
  {"name": "doc_id", "type": "STRING", "mode": "REQUIRED", "description": "Document ID the chunk belongs to"},
  {"name": "filename", "type": "STRING", "mode": "REQUIRED", "description": "Original PDF filename"},
  {"name": "gcs_path", "type": "STRING", "mode": "REQUIRED", "description": "GCS path to the chunk data"},
  {"name": "original_pdf_ipfs_path", "type": "STRING", "mode": "REQUIRED", "description": "IPFS path to the original PDF"},
  {"name": "text", "type": "STRING", "mode": "REQUIRED", "description": "Text content of the chunk for search"},
  {"name": "embedding", "type": "ARRAY<FLOAT>", "mode": "NULLABLE", "description": "Vector embedding for semantic search"},
  {"name": "pdf_metadata", "type": "STRING", "mode": "NULLABLE", "description": "JSON-encoded PDF metadata"}
]
EOL

# Create BigQuery table
print_info "Creating BigQuery table: ${PROJECT_ID}:${BQ_DATASET}.${BQ_TABLE}..."
if bq --project_id=${PROJECT_ID} show ${PROJECT_ID}:${BQ_DATASET}.${BQ_TABLE} &>/dev/null; then
    print_warning "BigQuery table ${BQ_TABLE} already exists in dataset ${BQ_DATASET}. Skipping creation."
else
    if bq mk --table --project_id=${PROJECT_ID} --description "PDF chunks for processing and search" --schema ${BQ_SCHEMA_FILE} ${PROJECT_ID}:${BQ_DATASET}.${BQ_TABLE}; then
        print_success "BigQuery table ${BQ_TABLE} created successfully."
    else
        print_error "Failed to create BigQuery table ${BQ_TABLE}."
        rm -f ${BQ_SCHEMA_FILE}
        exit 1
    fi
fi
rm -f ${BQ_SCHEMA_FILE} # Clean up temporary schema file

# Create a search index on the text field
SEARCH_INDEX_NAME="${BQ_TABLE}_text_index"
print_info "Checking for existing search index ${SEARCH_INDEX_NAME}..."
# Note: Checking for existing search indexes via bq command is not straightforward.
# We will attempt to create it; if it exists, the command might fail gracefully or do nothing.
print_info "Attempting to create search index ${SEARCH_INDEX_NAME} on the text field (this may take a few minutes)..."
SQL_CREATE_INDEX="CREATE SEARCH INDEX IF NOT EXISTS ${SEARCH_INDEX_NAME} ON \`${PROJECT_ID}.${BQ_DATASET}.${BQ_TABLE}\`(text)"
if bq query --project_id=${PROJECT_ID} --nouse_legacy_sql "${SQL_CREATE_INDEX}"; then
    print_success "Search index ${SEARCH_INDEX_NAME} creation command executed successfully (or index already exists)."
else
    print_warning "Failed to execute search index creation for ${SEARCH_INDEX_NAME}. It might already exist or there could be an issue. Manual check might be needed."
fi

# Create a vector search index for semantic search
VECTOR_INDEX_NAME="${BQ_TABLE}_vector_index"
print_info "Creating vector search index ${VECTOR_INDEX_NAME} for semantic search..."
print_info "Checking if vector search is supported in your BigQuery region..."

# Try different approaches for vector search setup
# Option 1: Attempt with standard syntax
SQL_CREATE_VECTOR_INDEX="CREATE OR REPLACE VECTOR INDEX ${VECTOR_INDEX_NAME} ON \`${PROJECT_ID}.${BQ_DATASET}.${BQ_TABLE}\`(embedding) OPTIONS(distance_type='COSINE')"
if bq query --project_id=${PROJECT_ID} --nouse_legacy_sql "${SQL_CREATE_VECTOR_INDEX}" 2>/dev/null; then
    print_success "Vector index ${VECTOR_INDEX_NAME} creation command executed successfully."
else
    print_warning "Standard vector index creation failed. Trying alternative approach..."
    
    # Option 2: Try without specifying dimensions (let BigQuery infer it)
    SQL_CREATE_VECTOR_INDEX_ALT="CREATE OR REPLACE VECTOR INDEX ${VECTOR_INDEX_NAME} ON \`${PROJECT_ID}.${BQ_DATASET}.${BQ_TABLE}\`(embedding)"
    if bq query --project_id=${PROJECT_ID} --nouse_legacy_sql "${SQL_CREATE_VECTOR_INDEX_ALT}" 2>/dev/null; then
        print_success "Vector index ${VECTOR_INDEX_NAME} created with alternative syntax."
    else
        print_warning "Vector index creation failed. This might be because:"
        print_warning "  1. Vector search may not be available in your current BigQuery region"
        print_warning "  2. Your account may not have sufficient permissions"
        print_warning "  3. Vector search is in preview and syntax may have changed"
        print_info "\nTo use semantic search without vector indexes, you can:"
        print_info "  1. Use the built-in text search functionality which is still powerful"
        print_info "  2. Store embeddings in your BigQuery table and perform cosine similarity in queries"
        print_info "  3. Try creating the vector index manually later with:"
        print_info "     ${SQL_CREATE_VECTOR_INDEX_ALT}"
        print_info "\nThis won't block the rest of your setup - the application can fall back to keyword search."
    fi
fi

# Create service account
SERVICE_ACCOUNT_NAME="pdf-processor"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
print_info "Creating service account: ${SERVICE_ACCOUNT_NAME} (${SERVICE_ACCOUNT_EMAIL})..."
if gcloud iam service-accounts describe ${SERVICE_ACCOUNT_EMAIL} --project=${PROJECT_ID} &>/dev/null; then
    print_warning "Service account ${SERVICE_ACCOUNT_EMAIL} already exists. Skipping creation."
else
    if gcloud iam service-accounts create ${SERVICE_ACCOUNT_NAME} --project=${PROJECT_ID} --display-name="PDF Processing Service Account"; then 
        print_success "Service account ${SERVICE_ACCOUNT_EMAIL} created successfully."
    else
        print_warning "Failed to create service account ${SERVICE_ACCOUNT_NAME}. Using default Qwiklabs account instead."
        SERVICE_ACCOUNT_EMAIL="$(gcloud config get account)"
        print_info "Using default Qwiklabs service account: ${SERVICE_ACCOUNT_EMAIL}"
    fi
fi

# Grant roles to service account
print_info "Granting necessary permissions..."

# GCS Storage Admin for bucket access
print_info "Granting roles/storage.admin on bucket gs://${GCS_BUCKET}..."
if [[ $SERVICE_ACCOUNT_EMAIL == *"@"* ]]; then
    if [[ $SERVICE_ACCOUNT_EMAIL == *"iam.gserviceaccount.com" ]]; then
        # It's a service account
        gcloud storage buckets add-iam-policy-binding gs://${GCS_BUCKET} --project=${PROJECT_ID} \
            --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
            --role="roles/storage.admin" --condition=None >/dev/null # Suppress verbose output
    else
        # It's a user account
        gcloud storage buckets add-iam-policy-binding gs://${GCS_BUCKET} --project=${PROJECT_ID} \
            --member="user:${SERVICE_ACCOUNT_EMAIL}" \
            --role="roles/storage.admin" --condition=None >/dev/null # Suppress verbose output
    fi
    print_success "Role roles/storage.admin granted on GCS bucket."
else
    print_warning "Invalid service account email. Skipping permission assignment."
fi

# Try to grant BigQuery permissions if possible
print_info "Attempting to grant BigQuery permissions..."
if [[ $SERVICE_ACCOUNT_EMAIL == *"iam.gserviceaccount.com" ]]; then
    # Only try this for service accounts, not user accounts
    if gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
        --role="roles/bigquery.dataEditor" --condition=None >/dev/null 2>&1; then
        print_success "Role roles/bigquery.dataEditor granted on project."
        
        gcloud projects add-iam-policy-binding ${PROJECT_ID} \
            --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
            --role="roles/bigquery.jobUser" --condition=None >/dev/null 2>&1
        print_success "Role roles/bigquery.jobUser granted on project."
        
        # Grant Vertex AI access for embedding generation
        print_info "Attempting to grant Vertex AI permissions..."
        if gcloud projects add-iam-policy-binding ${PROJECT_ID} \
            --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
            --role="roles/aiplatform.user" --condition=None >/dev/null 2>&1; then
            print_success "Role roles/aiplatform.user granted on project for embedding generation."
        else
            print_warning "Could not grant Vertex AI permissions. This might be expected in Qwiklabs environment."
        fi
    else
        print_warning "Could not grant BigQuery permissions. This is expected in Qwiklabs environment."
    fi
fi

print_info "Note: In Qwiklabs environment, you already have necessary BigQuery permissions through your student account."
print_success "All available permissions assigned."

# Create service account key if it's a service account
SERVICE_ACCOUNT_KEY_FILE="${PROJECT_ID}-${SERVICE_ACCOUNT_NAME}-key.json"
if [[ $SERVICE_ACCOUNT_EMAIL == *"iam.gserviceaccount.com" ]]; then
    print_info "Creating service account key file: ${SERVICE_ACCOUNT_KEY_FILE}..."
    if gcloud iam service-accounts keys create ${SERVICE_ACCOUNT_KEY_FILE} --project=${PROJECT_ID} --iam-account=${SERVICE_ACCOUNT_EMAIL}; then
        print_success "Service account key created: ${SERVICE_ACCOUNT_KEY_FILE}"
        print_info "You can use this key file with your application by specifying it in the Streamlit sidebar."
    else
        print_warning "Failed to create service account key. This is expected in Qwiklabs environment."
    fi
else
    print_warning "Not creating a key file for user account ${SERVICE_ACCOUNT_EMAIL}."
    print_info "For Qwiklabs, you should already be authenticated with your student account."
    
    # Create a dummy credentials file with instructions
    cat > "qwiklabs-credentials-info.txt" << EOL
This file was created by the setup script to help you use Google Cloud in Qwiklabs.

In Qwiklabs, you are already authenticated with your student account:
${SERVICE_ACCOUNT_EMAIL}

To use your application:
1. Make sure you're logged into the Google Cloud Console with this account
2. Your application should automatically use your Qwiklabs credentials
3. If prompted for a credentials file, leave the field blank to use your current authentication

Project ID: ${PROJECT_ID}
GCS Bucket: ${GCS_BUCKET}
BigQuery Dataset: ${BQ_DATASET}
BigQuery Table: ${BQ_TABLE}
EOL
    print_info "Created a helper file with authentication information: qwiklabs-credentials-info.txt"
fi

# Final Summary
print_info "\n---------------------------------------------------"
print_success " Google Cloud Setup Completed!"
print_info "---------------------------------------------------"
echo -e " Project ID:            ${GREEN}${PROJECT_ID}${NC}"
echo -e " Project Name:          ${GREEN}${PROJECT_NAME}${NC}"
echo -e " GCS Bucket for Chunks: ${GREEN}gs://${GCS_BUCKET}${NC}"
echo -e " BigQuery Dataset:      ${GREEN}${BQ_DATASET}${NC}"
echo -e " BigQuery Table:        ${GREEN}${BQ_TABLE}${NC}"
echo -e " Text Search Index:     ${GREEN}${SEARCH_INDEX_NAME}${NC}"
echo -e " Vector Search Index:   ${GREEN}${VECTOR_INDEX_NAME}${NC}"
echo -e " Using Account:         ${GREEN}${SERVICE_ACCOUNT_EMAIL}${NC}"
if [ -f "${SERVICE_ACCOUNT_KEY_FILE}" ]; then
    echo -e " Service Account Key:   ${GREEN}${PWD}/${SERVICE_ACCOUNT_KEY_FILE}${NC}"
fi
print_info "---------------------------------------------------
"
print_info "You are already authenticated with your Qwiklabs account."
print_info "Your Qwiklabs student account should have the necessary BigQuery permissions by default."
print_info "Update your application's settings (e.g., in Streamlit sidebar) with these resource names."

# Create environment variables file
print_info "Creating environment variables file (.env) for your application..."
cat > ".env" << EOL
# Google Cloud Settings
BQ_PROJECT_ID=${PROJECT_ID}
BQ_DATASET=${BQ_DATASET}
BQ_TABLE=${BQ_TABLE}
GCS_BUCKET_NAME=${GCS_BUCKET}
GOOGLE_APPLICATION_CREDENTIALS=$([ -f "${SERVICE_ACCOUNT_KEY_FILE}" ] && echo "${PWD}/${SERVICE_ACCOUNT_KEY_FILE}" || echo "")

# NOTE: You need to set your GEMINI_API_KEY for the LLM functionality
# GEMINI_API_KEY=your-gemini-api-key

# For semantic search using Vertex AI embeddings
USE_VECTOR_SEARCH=true
EMBEDDING_MODEL="textembedding-gecko@latest"
EOL

print_success "Environment file created: .env"
print_info "To enable full semantic search with embeddings, please add your GEMINI_API_KEY to the .env file." 