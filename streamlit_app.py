import streamlit as st
import requests
import json
import os
import pandas as pd
import plotly.express as px
import httpx
from datetime import datetime
import time

# API URL - change if your FastAPI server is running on a different port
API_URL = "http://localhost:8000"

# Set page configuration
st.set_page_config(
    page_title="Aptos PDF Storage App",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create session state for storing login state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None
if "aptos_address" not in st.session_state:
    st.session_state.aptos_address = None
if "view" not in st.session_state:
    st.session_state.view = "login"  # Default view
# Initialize chat history
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# Sidebar navigation
def sidebar():
    st.sidebar.title("Navigation")
    
    if not st.session_state.logged_in:
        if st.sidebar.button("Login"):
            st.session_state.view = "login"
        if st.sidebar.button("Signup"):
            st.session_state.view = "signup"
    else:
        st.sidebar.markdown(f"**Logged in as:** {st.session_state.username}")
        st.sidebar.markdown(f"**Aptos Address:** {st.session_state.aptos_address}")
        
        if st.sidebar.button("Dashboard"):
            st.session_state.view = "dashboard"
        if st.sidebar.button("Upload Document"):
            st.session_state.view = "upload"
        if st.sidebar.button("My Documents"):
            st.session_state.view = "documents"
        if st.sidebar.button("Chat with Documents"):
            st.session_state.view = "chat"
        if st.sidebar.button("Blockchain Explorer"):
            st.session_state.view = "blockchain"
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.token = None
            st.session_state.username = None
            st.session_state.aptos_address = None
            st.session_state.chat_messages = []
            st.session_state.view = "login"
            st.rerun()

    # Display app info
    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.info(
        "This is a demo UI for the Aptos PDF Storage App. "
        "It allows you to upload PDF files, store their data on IPFS, "
        "and record metadata on the Aptos blockchain."
    )

# Authentication functions
def login():
    st.title("Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            try:
                response = requests.post(
                    f"{API_URL}/auth/login",
                    data={"username": username, "password": password}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.aptos_address = data.get("aptos_address")
                    
                    st.session_state.view = "dashboard"
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error(f"Login failed: {response.text}")
            except Exception as e:
                st.error(f"Error: {str(e)}")

def signup():
    st.title("Signup")
    
    with st.form("signup_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        submit_button = st.form_submit_button("Signup")
        
        if submit_button:
            if password != confirm_password:
                st.error("Passwords do not match!")
                return
                
            try:
                response = requests.post(
                    f"{API_URL}/auth/signup",
                    json={"username": username, "email": email, "password": password}
                )
                
                if response.status_code == 201:  # Note OpenAPI says 201, not 200
                    data = response.json()
                    st.success("Signup successful! Please login.")
                    st.session_state.view = "login"
                    st.rerun()
                else:
                    st.error(f"Signup failed: {response.text}")
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Dashboard view
def dashboard():
    st.title("Dashboard")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Your Account")
        st.markdown(f"**Username:** {st.session_state.username}")
        st.markdown(f"**Aptos Address:** {st.session_state.aptos_address}")
        
        # Check server health
        try:
            health_response = requests.get(f"{API_URL}/health")
            if health_response.status_code == 200:
                health_data = health_response.json()
                status = health_data.get("status", "unknown")
                blockchain_connected = health_data.get("blockchain_connected", False)
                bigquery_configured = health_data.get("bigquery_configured", False)
                llm_configured = health_data.get("llm_configured", False)
                
                st.markdown("### Server Status")
                status_color = "green" if status == "healthy" else "orange" if status == "warning" else "red"
                blockchain_color = "green" if blockchain_connected else "red"
                bigquery_color = "green" if bigquery_configured else "red"
                llm_color = "green" if llm_configured else "red"
                
                st.markdown(f"**Status:** :{status_color}[{status}]")
                st.markdown(f"**Blockchain Connected:** :{blockchain_color}[{blockchain_connected}]")
                st.markdown(f"**BigQuery Configured:** :{bigquery_color}[{bigquery_configured}]")
                st.markdown(f"**LLM Service Available:** :{llm_color}[{llm_configured}]")
                
                if "error" in health_data and health_data["error"]:
                    st.error(f"Error: {health_data['error']}")
                
                # Show available features based on configuration
                st.markdown("### Available Features")
                feature_list = [
                    ("✅ Document Upload and Blockchain Storage", True),
                    ("✅ IPFS Storage", True),
                    ("✅ Document Search", True),
                    ("✅ Text Chunk Search", bigquery_configured),
                    ("✅ AI Chat with Documents (RAG)", bigquery_configured and llm_configured)
                ]
                
                for feature, available in feature_list:
                    if available:
                        st.markdown(f"{feature}")
                    else:
                        st.markdown(f"❌ {feature[2:]}")
            else:
                st.error("Could not retrieve server health information")
        except Exception as e:
            st.error(f"Error connecting to server: {str(e)}")
    
    with col2:
        st.subheader("Recent Activity")
        
        # Get user's documents
        try:
            docs_response = requests.get(
                f"{API_URL}/documents/my-documents",
                headers={"Authorization": f"Bearer {st.session_state.token}"}
            )
            
            if docs_response.status_code == 200:
                docs_data = docs_response.json()
                
                if docs_data:
                    # Show summary
                    st.markdown(f"**Total Documents:** {len(docs_data)}")
                    
                    # Create a simple visualization
                    st.markdown("### Document Timeline")
                    
                    # Create dummy dates if created_at is not available
                    for i, doc in enumerate(docs_data):
                        if "created_at" not in doc or not doc["created_at"]:
                            docs_data[i]["created_at"] = datetime.now().isoformat()
                    
                    df = pd.DataFrame(docs_data)
                    if "created_at" in df.columns:
                        df["created_at"] = pd.to_datetime(df["created_at"])
                        df = df.sort_values("created_at")
                        
                        # Create a count by date
                        date_counts = df.groupby(df["created_at"].dt.date).size().reset_index(name="count")
                        date_counts["created_at"] = pd.to_datetime(date_counts["created_at"])
                        
                        # Create plot
                        fig = px.line(
                            date_counts, 
                            x="created_at", 
                            y="count", 
                            title="Documents Uploaded Over Time",
                            labels={"created_at": "Date", "count": "Number of Documents"}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No documents uploaded yet. Go to the Upload section to add documents.")
            else:
                st.error(f"Could not retrieve documents: {docs_response.text}")
        except Exception as e:
            st.error(f"Error: {str(e)}")
            
        # Quick links section
        st.markdown("### Quick Links")
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("Upload New Document", key="dashboard_upload"):
                st.session_state.view = "upload"
                st.rerun()
            
            if st.button("View My Documents", key="dashboard_documents"):
                st.session_state.view = "documents"
                st.rerun()
        
        with col_b:
            if st.button("Chat with Documents", key="dashboard_chat"):
                st.session_state.view = "chat"
                st.rerun()
            
            if st.button("Blockchain Explorer", key="dashboard_blockchain"):
                st.session_state.view = "blockchain"
                st.rerun()

# Upload document
def upload_document():
    st.title("Upload Document")
    
    with st.form("upload_form"):
        uploaded_files = st.file_uploader("Choose PDF files", type="pdf", accept_multiple_files=True)
        submit_button = st.form_submit_button("Upload")
        
        if submit_button and uploaded_files:
            successful_uploads = 0
            failed_uploads = 0
            
            # Add progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.container()
            
            for i, uploaded_file in enumerate(uploaded_files):
                # Update progress
                progress = (i / len(uploaded_files))
                progress_bar.progress(progress)
                status_text.text(f"Processing {uploaded_file.name} ({i+1}/{len(uploaded_files)})")
                
                try:
                    # Create multipart form data
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    
                    response = requests.post(
                        f"{API_URL}/documents/upload",
                        headers={"Authorization": f"Bearer {st.session_state.token}"},
                        files=files
                    )
                
                    if response.status_code == 201:
                        data = response.json()
                        successful_uploads += 1
                        with results_container.expander(f"✅ {uploaded_file.name}", expanded=False):
                            st.json(data)
                    else:
                        failed_uploads += 1
                        with results_container.expander(f"❌ {uploaded_file.name}", expanded=True):
                            st.error(f"Upload failed: {response.text}")
                except Exception as e:
                    failed_uploads += 1
                    with results_container.expander(f"❌ {uploaded_file.name}", expanded=True):
                        st.error(f"Error: {str(e)}")
            
            # Complete progress bar
            progress_bar.progress(1.0)
            status_text.text("Processing complete!")
            
            # Display summary
            if successful_uploads > 0:
                st.success(f"Successfully uploaded {successful_uploads} file(s)!")
            if failed_uploads > 0:
                st.error(f"Failed to upload {failed_uploads} file(s).")
        
        elif submit_button:
            st.warning("Please select at least one PDF file to upload.")

# View documents
def view_documents():
    st.title("My Documents")
    
    try:
        response = requests.get(
            f"{API_URL}/documents/my-documents",
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        
        if response.status_code == 200:
            documents = response.json()
            
            if not documents:
                st.info("You haven't uploaded any documents yet.")
                return
            
            st.subheader(f"{len(documents)} Documents Found")
            
            # Create a table view
            doc_data = []
            for doc in documents:
                doc_data.append({
                    "ID": doc.get("id", "N/A"),
                    "Filename": doc.get("filename", "Unknown"),
                    "IPFS Hash": doc.get("ipfs_hash", "N/A"),
                    "Transaction Hash": doc.get("transaction_hash", "N/A"),
                    "Created At": doc.get("created_at", "Unknown")
                })
            
            doc_df = pd.DataFrame(doc_data)
            st.dataframe(doc_df)
            
            # Document details section
            st.subheader("Document Details")
            selected_doc_id = st.selectbox("Select a document to view details", 
                                         [doc["ID"] for doc in doc_data])
            
            if selected_doc_id:
                # Find the selected document
                selected_doc = next((doc for doc in documents if doc.get("id") == selected_doc_id), None)
                
                if selected_doc:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**Filename:** {selected_doc.get('filename', 'Unknown')}")
                        st.markdown(f"**IPFS Hash:** {selected_doc.get('ipfs_hash', 'N/A')}")
                        
                        # Add IPFS Gateway link if available
                        if selected_doc.get('ipfs_hash'):
                            ipfs_link = f"https://ipfs.io/ipfs/{selected_doc['ipfs_hash']}"
                            st.markdown(f"**IPFS Link:** [View on IPFS Gateway]({ipfs_link})")
                    
                    with col2:
                        st.markdown(f"**Transaction Hash:** {selected_doc.get('transaction_hash', 'N/A')}")
                        st.markdown(f"**Aptos Address:** {selected_doc.get('aptos_address', 'N/A')}")
                        
                        # Add Aptos Explorer link if available
                        if selected_doc.get('transaction_hash'):
                            # Using devnet explorer for this example
                            aptos_link = f"https://explorer.aptoslabs.com/txn/{selected_doc['transaction_hash']}?network=devnet"
                            st.markdown(f"**Aptos Explorer:** [View on Aptos Explorer]({aptos_link})")
        else:
            st.error(f"Failed to retrieve documents: {response.text}")
    except Exception as e:
        st.error(f"Error: {str(e)}")

# Blockchain explorer
def blockchain_explorer():
    st.title("Blockchain Explorer")
    
    st.markdown("""
    This section allows you to explore your data stored on the Aptos blockchain.
    You can view your account resources and modules.
    """)
    
    # Show user's Aptos address
    st.subheader("Your Aptos Account")
    st.markdown(f"**Address:** {st.session_state.aptos_address}")
    
    # Tabs for different views
    tab1, tab2 = st.tabs(["Account Resources", "Transactions"])
    
    with tab1:
        st.subheader("Account Resources")
        if st.button("Refresh Resources"):
            try:
                # Query the API for blockchain resources
                response = requests.get(
                    f"{API_URL}/blockchain/resources",
                    headers={"Authorization": f"Bearer {st.session_state.token}"}
                )
                
                if response.status_code == 200:
                    resources = response.json()
                    
                    if not resources:
                        st.info("No resources found for your account on the blockchain.")
                    else:
                        st.json(resources)
                else:
                    st.error(f"Failed to retrieve blockchain resources: {response.text}")
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    with tab2:
        st.subheader("Recent Transactions")
        if st.button("Refresh Transactions"):
            try:
                # Query the API for transactions
                response = requests.get(
                    f"{API_URL}/blockchain/transactions",
                    headers={"Authorization": f"Bearer {st.session_state.token}"}
                )
                
                if response.status_code == 200:
                    transactions = response.json()
                    
                    if not transactions:
                        st.info("No transactions found for your account.")
                    else:
                        # Create a DataFrame for better display
                        tx_data = []
                        for tx in transactions:
                            tx_data.append({
                                "Hash": tx.get("hash", "N/A"),
                                "Type": tx.get("type", "Unknown"),
                                "Status": tx.get("success", False),
                                "Timestamp": tx.get("timestamp", "Unknown"),
                                "Gas Used": tx.get("gas_used", "N/A")
                            })
                        
                        tx_df = pd.DataFrame(tx_data)
                        st.dataframe(tx_df)
                        
                        # Show transaction details
                        selected_tx = st.selectbox("Select a transaction to view details", 
                                                 [tx["Hash"] for tx in tx_data])
                        
                        if selected_tx:
                            # Find the selected transaction
                            tx_details = next((tx for tx in transactions if tx.get("hash") == selected_tx), None)
                            
                            if tx_details:
                                st.json(tx_details)
                else:
                    st.error(f"Failed to retrieve transactions: {response.text}")
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Chat with documents using RAG
def chat_with_documents():
    st.title("Chat with Documents")
    
    # Intro text
    st.markdown("""
    This feature allows you to chat with your documents using RAG (Retrieval Augmented Generation).
    Ask questions about your documents, and the AI will retrieve relevant information and answer your queries.
    """)
    
    # Check if BigQuery and LLM are configured on the server
    try:
        health_response = requests.get(f"{API_URL}/health")
        if health_response.status_code == 200:
            health_data = health_response.json()
            
            if not health_data.get("bigquery_configured", False):
                st.warning("BigQuery is not configured on the server. Document search functionality may be limited.")
            
            if not health_data.get("llm_configured", False):
                st.error("LLM service is not configured. Chat functionality will not work correctly.")
                st.info("Ask your administrator to set up the GEMINI_API_KEY environment variable.")
                return
    except Exception as e:
        st.error(f"Error connecting to server: {str(e)}")
    
    # Display chat history
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask a question about your documents"):
        # Add user message to chat history
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Prepare the chat request with history
        chat_request = {
            "query": prompt,
            "history": st.session_state.chat_messages[:-1]  # Exclude the most recent message which we just added
        }
        
        # Call the chat API
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = requests.post(
                        f"{API_URL}/documents/chat",
                        headers={"Authorization": f"Bearer {st.session_state.token}"},
                        json=chat_request
                    )
                    
                    if response.status_code == 200:
                        chat_response = response.json()
                        answer = chat_response.get("answer", "No answer received.")
                        chunks = chat_response.get("chunks", [])
                        
                        # Display the answer
                        st.write(answer)
                        
                        # Add assistant response to chat history
                        st.session_state.chat_messages.append({"role": "assistant", "content": answer})
                        
                        # Display source chunks in an expander
                        if chunks:
                            with st.expander("Source Documents"):
                                for i, chunk in enumerate(chunks):
                                    st.markdown(f"**Source {i+1}:** {chunk['filename']}")
                                    st.markdown(f"**Chunk ID:** {chunk['chunk_id']}")
                                    st.text(chunk['text'])
                                    st.markdown("---")
                    else:
                        st.error(f"Error from chat API: {response.text}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    # Add a button to clear chat history
    if st.button("Clear Conversation"):
        st.session_state.chat_messages = []
        st.rerun()

# Main app logic
def main():
    sidebar()
    
    if st.session_state.view == "login":
        login()
    elif st.session_state.view == "signup":
        signup()
    elif st.session_state.view == "dashboard":
        dashboard()
    elif st.session_state.view == "upload":
        upload_document()
    elif st.session_state.view == "documents":
        view_documents()
    elif st.session_state.view == "chat":
        chat_with_documents()
    elif st.session_state.view == "blockchain":
        blockchain_explorer()
    else:
        login()  # Default to login

if __name__ == "__main__":
    main() 