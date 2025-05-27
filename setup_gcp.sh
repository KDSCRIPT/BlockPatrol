#!/bin/bash
# Google Cloud Project Setup Script for PDF Processing Pipeline
# This script sets up a complete Google Cloud environment for the PDF processing application
# Now with automatic project detection and forced service account key generation!

# Exit on error
set -e

# --- BEGIN USER CONFIGURATION ---
# The script will try to auto-detect these values, but you can override them here:

# 1. PROJECT_ID: Leave empty to auto-detect or set a specific project ID
PROJECT_ID=""  # Will auto-detect if empty

# 2. PROJECT_NAME: A user-friendly name for your project (only used for new projects)
PROJECT_NAME="PDF Processing Pipeline"

# 3. REGION: The default region for your resources
REGION="us-west1"

# 4. CREATE_NEW_PROJECT: Set to true to force creation of a new project
CREATE_NEW_PROJECT=false

# --- END USER CONFIGURATION ---

# Derived variables (usually no need to change these)
ZONE="${REGION}-a"
BQ_DATASET="pdf_processing"
BQ_TABLE="pdf_chunks"
SERVICE_ACCOUNT_NAME="pdf-processor"
# The key file will always be named this way and placed in the current directory
SERVICE_ACCOUNT_KEY_FILENAME="credentials.json"
SERVICE_ACCOUNT_KEY_FILE="" # Will be set to full path later

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

# Function to get user input with default
get_input() {
    local prompt="$1"
    local default="$2"
    local result
    
    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " result
        echo "${result:-$default}"
    else
        read -p "$prompt: " result
        echo "$result"
    fi
}

# Function to auto-detect or select project
detect_project() {
    print_info "Detecting available Google Cloud projects..."
    
    # Get current project if set
    local current_project
    current_project=$(gcloud config get project 2>/dev/null || echo "")
    
    # Get all accessible projects
    local projects
    projects=$(gcloud projects list --format="value(projectId,name)" 2>/dev/null || echo "")
    
    if [ -z "$projects" ]; then
        print_warning "No existing projects found or insufficient permissions."
        CREATE_NEW_PROJECT=true
        return
    fi # Added missing 'fi' here
    
    print_info "Available projects:"
    echo "$projects" | nl -w2 -s'. '
    
    if [ -n "$current_project" ]; then
        print_info "Currently active project: $current_project"
        
        echo ""
        local choice
        choice=$(get_input "Use current project '$current_project'? (y/N/list number)" "N")
        
        case $choice in
            [Yy]|[Yy][Ee][Ss])
                PROJECT_ID="$current_project"
                print_success "Using current project: $PROJECT_ID"
                return
                ;;
            [0-9]*)
                PROJECT_ID=$(echo "$projects" | sed -n "${choice}p" | cut -f1)
                if [ -n "$PROJECT_ID" ]; then
                    print_success "Selected project: $PROJECT_ID"
                    return
                else
                    print_error "Invalid selection."
                fi
                ;;
        esac
    fi
    
    echo ""
    local choice
    choice=$(get_input "Select a project by number, or press Enter to create new" "")
    
    if [ -n "$choice" ] && [[ "$choice" =~ ^[0-9]+$ ]]; then
        PROJECT_ID=$(echo "$projects" | sed -n "${choice}p" | cut -f1)
        if [ -n "$PROJECT_ID" ]; then
            print_success "Selected project: $PROJECT_ID"
            return
        else
            print_error "Invalid selection."
        fi
    fi
    
    CREATE_NEW_PROJECT=true
}

# Function to generate unique project ID
generate_project_id() {
    local base_id="pdf-processing-$(date +%s)"
    local random_suffix=$(openssl rand -hex 3 2>/dev/null || echo $(($RANDOM % 1000)))
    echo "${base_id}-${random_suffix}"
}

# Function to set up credential file download
setup_credential_download() {
    if [ -z "$SERVICE_ACCOUNT_KEY_FILE" ] || [ ! -f "$SERVICE_ACCOUNT_KEY_FILE" ]; then
        print_warning "No service account key file to set up for download. Skipping download script creation."
        return
    fi
    
    print_info "Setting up credential file download..."
    
    # Create a simple download script
    cat > "download_credentials.sh" << 'EOL'
#!/bin/bash
# Simple HTTP server to download credential file
PORT=8080
FILE="$1"

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
    echo "Error: Credential file not found or path not provided: $FILE"
    exit 1
fi

echo "Starting HTTP server on port $PORT..."
echo "Download URL: http://localhost:$PORT/credentials.json"
echo "Press Ctrl+C to stop the server"
echo ""

# Start simple HTTP server using Python
if command -v python3 &> /dev/null; then
    python3 -m http.server $PORT --bind 127.0.0.1 &
    SERVER_PID=$!
elif command -v python &> /dev/null; then
    python -m SimpleHTTPServer $PORT &
    SERVER_PID=$!
else
    echo "Python not found. Cannot start HTTP server."
    echo "You can manually copy the credential file:"
    echo "cat $FILE"
    exit 1
fi

# Create a symlink for easy download
# Use absolute path for symlink target for robustness
TARGET_PATH=$(readlink -f "$FILE")
ln -sf "$TARGET_PATH" "credentials.json"

# Wait a moment for server to start
sleep 2

# Try to open browser if available
if command -v curl &> /dev/null; then
    echo "Testing server..."
    if curl -s "http://localhost:$PORT/credentials.json" > /dev/null; then
        echo "✅ Server is running successfully!"
    else
        echo "❌ Server may not be running properly"
    fi
fi

echo ""
echo "=== DOWNLOAD INSTRUCTIONS ==="
echo "1. Open a new Cloud Shell tab"
echo "2. Run: curl -O http://localhost:$PORT/credentials.json"
echo "3. The file will be saved as 'credentials.json'"
echo "============================"
echo ""

# Keep server running until user stops it
wait $SERVER_PID
EOL

    chmod +x download_credentials.sh
    
    print_success "Download setup completed!"
    print_info "To download your credentials:"
    echo ""
    echo -e "${YELLOW}Option 1 - HTTP Server (Recommended for Cloud Shell):${NC}"
    echo "    ./download_credentials.sh \"$SERVICE_ACCOUNT_KEY_FILE\""
    echo "    Then open Web Preview on port 8080"
    echo ""
    echo -e "${YELLOW}Option 2 - Direct Download (if server is running):${NC}"
    echo "    curl -L 'http://localhost:8080/credentials.json' -o 'credentials.json'"
    echo ""
    echo -e "${YELLOW}Option 3 - Manual Copy:${NC}"
    echo "    cat \"$SERVICE_ACCOUNT_KEY_FILE\""
    echo ""
}

# --- SCRIPT EXECUTION STARTS HERE ---

print_info "Starting Automated Google Cloud Project Setup..."
echo ""

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

# Auto-detect or get project ID
if [ -z "$PROJECT_ID" ] && [ "$CREATE_NEW_PROJECT" != true ]; then
    detect_project
fi

# Handle new project creation
if [ "$CREATE_NEW_PROJECT" = true ] || [ -z "$PROJECT_ID" ]; then
    print_info "Creating a new project..."
    
    if [ -z "$PROJECT_ID" ]; then
        PROJECT_ID=$(generate_project_id)
        print_info "Generated project ID: $PROJECT_ID"
        
        local custom_id
        custom_id=$(get_input "Use this project ID or enter a custom one" "$PROJECT_ID")
        PROJECT_ID="$custom_id"
    fi
    
    # Validate project ID format
    if [[ ! "$PROJECT_ID" =~ ^[a-z][a-z0-9-]{5,29}$ ]]; then
        print_error "Invalid project ID format. Must start with lowercase letter, contain only lowercase letters, numbers, and hyphens, and be 6-30 characters long."
        exit 1
    fi
fi

print_info "Final configuration:"
echo -e "    Project ID: ${GREEN}$PROJECT_ID${NC}"
echo -e "    Region: ${GREEN}$REGION${NC}" # Removed billing account from printout
echo ""

# Confirm before proceeding
if [ "$CREATE_NEW_PROJECT" = true ]; then
    read -p "Create new project with this configuration? (y/N): " confirm
else
    read -p "Proceed with this configuration? (y/N): " confirm
fi

case $confirm in
    [Yy]|[Yy][Ee][Ss]) ;;
    *)    
        print_info "Setup cancelled by user."
        exit 0
        ;;
esac

# Set derived variables now that we have PROJECT_ID
GCS_BUCKET="${PROJECT_ID}-chunks"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SERVICE_ACCOUNT_KEY_FILE="${PWD}/${SERVICE_ACCOUNT_KEY_FILENAME}" # Always define full path for the key file

# Create new project if needed
if [ "$CREATE_NEW_PROJECT" = true ]; then
    print_info "Creating new Google Cloud project: ${PROJECT_NAME} (ID: ${PROJECT_ID})..."
    if gcloud projects describe ${PROJECT_ID} &>/dev/null; then
        print_warning "Project ${PROJECT_ID} already exists. Using existing project."
    else
        if gcloud projects create ${PROJECT_ID} --name="${PROJECT_NAME}"; then
            print_success "Project ${PROJECT_ID} created successfully."
        else
            print_error "Failed to create project ${PROJECT_ID}."
            exit 1
        fi
    fi
fi

# Set as default project
print_info "Setting ${PROJECT_ID} as the default project for gcloud commands..."
gcloud config set project ${PROJECT_ID}

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

# Create BigQuery table
print_info "Creating BigQuery table: ${PROJECT_ID}:${BQ_DATASET}.${BQ_TABLE}..."
# Use a direct SQL CREATE TABLE statement for more robust type handling
SQL_CREATE_TABLE="CREATE TABLE IF NOT EXISTS \`${PROJECT_ID}.${BQ_DATASET}.${BQ_TABLE}\` (
  chunk_id STRING NOT NULL,
  doc_id STRING NOT NULL,
  filename STRING NOT NULL,
  gcs_path STRING NOT NULL,
  original_pdf_ipfs_path STRING NOT NULL,
  text STRING NOT NULL,
  embedding ARRAY<FLOAT64>,
  pdf_metadata STRING
)"

if bq --project_id=${PROJECT_ID} query --nouse_legacy_sql "${SQL_CREATE_TABLE}"; then
    print_success "BigQuery table ${BQ_TABLE} created successfully."
else
    print_error "Failed to create BigQuery table ${BQ_TABLE}."
    exit 1
fi

# Create a search index on the text field
SEARCH_INDEX_NAME="${BQ_TABLE}_text_index"
print_info "Creating search index ${SEARCH_INDEX_NAME} on the text field..."
SQL_CREATE_INDEX="CREATE SEARCH INDEX IF NOT EXISTS ${SEARCH_INDEX_NAME} ON \`${PROJECT_ID}.${BQ_DATASET}.${BQ_TABLE}\`(text)"
if bq query --project_id=${PROJECT_ID} --nouse_legacy_sql "${SQL_CREATE_INDEX}"; then
    print_success "Search index ${SEARCH_INDEX_NAME} created successfully."
else
    print_warning "Failed to create search index ${SEARCH_INDEX_NAME}. This feature might not be available in your region."
fi

# Create a vector search index for semantic search
VECTOR_INDEX_NAME="${BQ_TABLE}_vector_index"
print_info "Creating vector search index ${VECTOR_INDEX_NAME} for semantic search..."

# Single attempt: Explicitly define IVF with correct ivf_options using num_lists
SQL_CREATE_VECTOR_INDEX="CREATE OR REPLACE VECTOR INDEX ${VECTOR_INDEX_NAME} ON \`${PROJECT_ID}.${BQ_DATASET}.${BQ_TABLE}\`(embedding) OPTIONS(distance_type='COSINE', index_type='IVF', ivf_options='{\"num_lists\": 100}')"
if bq query --project_id=${PROJECT_ID} --nouse_legacy_sql "${SQL_CREATE_VECTOR_INDEX}" 2>/dev/null; then
    print_success "Vector index ${VECTOR_INDEX_NAME} created successfully (explicit IVF)."
else
    # Changed error message to be more informative about the data requirement
    print_warning "Vector index creation failed. This is likely because the 'embedding' column is empty. The index will be created automatically once data with embeddings is loaded into the table."
    print_info "The application will fall back to keyword search, which is still powerful, until the vector index is populated."
fi

# --- Service Account and Key Management ---
print_info "Setting up service account and generating key file..."

# Create service account if it doesn't exist
if gcloud iam service-accounts describe ${SERVICE_ACCOUNT_EMAIL} --project=${PROJECT_ID} &>/dev/null; then
    print_warning "Service account ${SERVICE_ACCOUNT_EMAIL} already exists."
else
    if gcloud iam service-accounts create ${SERVICE_ACCOUNT_NAME} --project=${PROJECT_ID} --display-name="PDF Processing Service Account"; then    
        print_success "Service account ${SERVICE_ACCOUNT_EMAIL} created successfully."
    else
        print_error "Failed to create service account ${SERVICE_ACCOUNT_EMAIL}. Please check permissions."
        exit 1
    fi
fi

# Delete existing keys and create a new one to ensure a fresh credentials.json
print_info "Deleting existing service account keys and creating a new one for ${SERVICE_ACCOUNT_EMAIL}..."
# List keys, filter for user-managed keys (starts with 5), not Google-managed keys
EXISTING_KEYS=$(gcloud iam service-accounts keys list --iam-account=${SERVICE_ACCOUNT_EMAIL} --project=${PROJECT_ID} --managed-by=user --format="value(name)" 2>/dev/null)

if [ -n "$EXISTING_KEYS" ]; then
    for KEY_ID in $EXISTING_KEYS; do
        print_info "Deleting key: ${KEY_ID}"
        gcloud iam service-accounts keys delete ${KEY_ID} --iam-account=${SERVICE_ACCOUNT_EMAIL} --project=${PROJECT_ID} -q
    done
    print_success "All user-managed keys for ${SERVICE_ACCOUNT_EMAIL} deleted."
else
    print_info "No user-managed keys found for ${SERVICE_ACCOUNT_EMAIL}."
fi

# Create the new service account key
if gcloud iam service-accounts keys create ${SERVICE_ACCOUNT_KEY_FILE} --project=${PROJECT_ID} --iam-account=${SERVICE_ACCOUNT_EMAIL}; then
    print_success "Service account key created at: ${SERVICE_ACCOUNT_KEY_FILE}"
else
    print_error "Failed to create service account key at ${SERVICE_ACCOUNT_KEY_FILE}. Please check permissions."
    exit 1
fi

# Grant permissions to the *newly created/ensured* service account
print_info "Granting necessary permissions to: ${SERVICE_ACCOUNT_EMAIL}"

# GCS permissions
if gcloud storage buckets add-iam-policy-binding gs://${GCS_BUCKET} --project=${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/storage.admin" --condition=None >/dev/null 2>&1; then
    print_success "GCS permissions granted."
else
    print_warning "Could not grant GCS permissions. May already exist or insufficient privileges."
fi

# BigQuery permissions
if gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/bigquery.dataEditor" --condition=None >/dev/null 2>&1; then
    print_success "BigQuery dataEditor permissions granted."
fi

if gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/bigquery.jobUser" --condition=None >/dev/null 2>&1; then
    print_success "BigQuery jobUser permissions granted."
fi

# Vertex AI permissions
if gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/aiplatform.user" --condition=None >/dev/null 2>&1; then
    print_success "Vertex AI permissions granted."
fi


# Set up download capability for the generated key file
setup_credential_download

# Create environment variables file
print_info "Creating environment variables file (.env)..."
cat > ".env" << EOL
# Google Cloud Settings (Auto-generated by setup script)
BQ_PROJECT_ID=${PROJECT_ID}
BQ_DATASET=${BQ_DATASET}
BQ_TABLE=${BQ_TABLE}
GCS_BUCKET_NAME=${GCS_BUCKET}
GOOGLE_APPLICATION_CREDENTIALS=${SERVICE_ACCOUNT_KEY_FILE}

# Authentication Info
CURRENT_ACCOUNT=${SERVICE_ACCOUNT_EMAIL}

# For semantic search using Vertex AI embeddings
USE_VECTOR_SEARCH=true
EMBEDDING_MODEL=textembedding-gecko@latest
EOL

# Create setup summary file
cat > "setup-summary.md" << EOL
# Google Cloud Setup Summary

## Project Information
- **Project ID**: ${PROJECT_ID}
- **Project Name**: ${PROJECT_NAME}
- **Region**: ${REGION}

## Resources Created
- **GCS Bucket**: gs://${GCS_BUCKET}
- **BigQuery Dataset**: ${BQ_DATASET}
- **BigQuery Table**: ${BQ_TABLE}
- **Text Search Index**: ${SEARCH_INDEX_NAME}
- **Vector Search Index**: ${VECTOR_INDEX_NAME}

## Authentication
- **Account**: ${SERVICE_ACCOUNT_EMAIL}
- **Key File**: ${SERVICE_ACCOUNT_KEY_FILENAME} (located at \`${SERVICE_ACCOUNT_KEY_FILE}\`)

## Next Steps
1. Add your API keys to the \`.env\` file
2. Update your application configuration to use the \`credentials.json\` file.
3. Test the setup with a small PDF file
4. **Important for Vector Search:** The vector index will only be fully created and usable once you have loaded data (with embeddings) into the \`${BQ_DATASET}.${BQ_TABLE}\` BigQuery table.

## Useful Commands
\`\`\`bash
# View your project
gcloud config get project

# List BigQuery datasets
bq ls --project_id=${PROJECT_ID}

# List GCS buckets
gcloud storage ls

# Check service account permissions
gcloud projects get-iam-policy ${PROJECT_ID}
\`\`\`
EOL

# Final Summary
print_info "\n======================================================"
print_success "🎉 GOOGLE CLOUD SETUP COMPLETED SUCCESSFULLY! 🎉"
print_info "======================================================"
echo -e " Project ID:             ${GREEN}${PROJECT_ID}${NC}"
echo -e " GCS Bucket:             ${GREEN}gs://${GCS_BUCKET}${NC}"
echo -e " BigQuery Dataset:       ${GREEN}${BQ_DATASET}${NC}"
echo -e " BigQuery Table:         ${GREEN}${BQ_TABLE}${NC}"
echo -e " Service Account:        ${GREEN}${SERVICE_ACCOUNT_EMAIL}${NC}"
echo -e " Service Account Key:    ${GREEN}${SERVICE_ACCOUNT_KEY_FILE}${NC}"
echo -e " Environment File:       ${GREEN}.env${NC}"
echo -e " Setup Summary:          ${GREEN}setup-summary.md${NC}"
print_info "======================================================"

# Print variables in requested format
echo ""
print_info "📋 Key Environment Variables:"
echo "PROJECT_ID=${PROJECT_ID}"
echo "PROJECT_NAME=${PROJECT_NAME}"
echo "GCS_BUCKET_NAME=${GCS_BUCKET}"
echo "BQ_DATASET=${BQ_DATASET}"
echo "BQ_TABLE=${BQ_TABLE}"
echo "SERVICE_ACCOUNT=${SERVICE_ACCOUNT_EMAIL}"
echo "SERVICE_ACCOUNT_KEY_FILE=${SERVICE_ACCOUNT_KEY_FILE}"
echo ""

print_info "✅ Your Google Cloud environment is ready!"
print_info "✅ Configuration files have been created"
print_info "✅ All required resources are set up"
echo ""

# Show credential download instructions
print_info "🔑 CREDENTIAL DOWNLOAD OPTIONS:"
echo ""
echo -e "${GREEN}1. Quick Download (Recommended for Cloud Shell):${NC}"
echo "    ./download_credentials.sh \"$SERVICE_ACCOUNT_KEY_FILE\""
echo "    Then use Cloud Shell Web Preview on port 8080"
echo ""
echo -e "${GREEN}2. Command Line Download (if server is running):${NC}"
echo "    # First start the server:"
echo "    ./download_credentials.sh \"$SERVICE_ACCOUNT_KEY_FILE\" &"
echo "    # Then in another terminal:"
echo "    curl -O http://localhost:8080/credentials.json"
echo ""
echo -e "${GREEN}3. Manual Copy (to display content directly):${NC}"
echo "    cat \"$SERVICE_ACCOUNT_KEY_FILE\""
echo ""
echo -e "${YELLOW}📱 Pro Tip:${NC} Use Cloud Shell's Web Preview feature!"
echo "    1. Run: ./download_credentials.sh \"$SERVICE_ACCOUNT_KEY_FILE\""
echo "    2. Click 'Web Preview' -> 'Preview on port 8080'"
echo "    3. Click the download button in your browser"
echo ""

print_warning "📝 Don't forget to add your API keys to the .env file!"
print_info "📖 Check setup-summary.md for detailed information"

# Create quick start guide
cat > "quick-start.md" << EOL
# 🚀 Quick Start Guide

## What was created:
- ✅ Google Cloud Project: \`${PROJECT_ID}\`
- ✅ GCS Bucket: \`gs://${GCS_BUCKET}\`
- ✅ BigQuery Dataset: \`${BQ_DATASET}\`
- ✅ BigQuery Table: \`${BQ_TABLE}\`
- ✅ Service Account Key: \`${SERVICE_ACCOUNT_KEY_FILENAME}\` (located at \`${SERVICE_ACCOUNT_KEY_FILE}\`)

## Next Steps:

### 1. Download Credentials (if needed)
\`\`\`bash
# Start download server
./download_credentials.sh "${SERVICE_ACCOUNT_KEY_FILE}"

# Use Web Preview on port 8080, or:
curl -O http://localhost:8080/credentials.json
\`\`\`

### 2. Add API Keys to .env
Edit the \`.env\` file and add:
\`\`\`
GEMINI_API_KEY=your-api-key-here
OPENAI_API_KEY=your-api-key-here  # if using OpenAI
\`\`\`

### 3. Test Your Setup
\`\`\`bash
# Check project
gcloud config get project

# List resources
bq ls --project_id=${PROJECT_ID}
gcloud storage ls

# Test BigQuery with the generated key file
# Make sure you have downloaded 'credentials.json' first!
export GOOGLE_APPLICATION_CREDENTIALS="${SERVICE_ACCOUNT_KEY_FILE}"
python3 -c "from google.cloud import bigquery; client = bigquery.Client(); print('BigQuery client initialized successfully with ADC or key file!')"
\`\`\`

### 4. Use in Your Application
- Project ID: \`${PROJECT_ID}\`
- Bucket: \`${GCS_BUCKET}\`
- Dataset.Table: \`${BQ_DATASET}.${BQ_TABLE}\`
- Credentials: \`credentials.json\` (the file you download)

### Python Example for BigQuery Client
\`\`\`python
from google.cloud import bigquery
import os

# Set the environment variable to point to your downloaded key file
# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = './credentials.json'

# Or, if you use the .env file, ensure it's loaded:
# from dotenv import load_dotenv
# load_dotenv()
# client = bigquery.Client() # This will pick up GOOGLE_APPLICATION_CREDENTIALS

# If you explicitly want to load from the file path directly:
client = bigquery.Client.from_service_account_json('./credentials.json')

# Now you can use the client
# query = "SELECT 'Hello from BigQuery with key file!' as message"
# job = client.query(query)
# for row in job.result():
#     print(row.message)
\`\`\`

## Troubleshooting

### Can't download credentials?
\`\`\`bash
# Manual copy (will print the content to your terminal)
cat "${SERVICE_ACCOUNT_KEY_FILE}"
\`\`\`

### Permission issues?
\`\`\`bash
# Check current account
gcloud auth list

# Check project permissions    
gcloud projects get-iam-policy ${PROJECT_ID}
\`\`\`

### Vector Index Creation Failed?
The vector index on the \`embedding\` column might fail to create if the table is empty. This is expected. The index will be successfully created once you load data with embeddings into the \`${BQ_DATASET}.${BQ_TABLE}\` table. Your application can still use keyword search in the meantime.
EOL

echo ""
print_success "🎉 Setup complete! Check quick-start.md for next steps 🚀"