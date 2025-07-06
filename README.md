# BlockPatrol 🚓 + Aptos PDF Storage API with BigQuery and RAG

**Secure & Intelligent Criminal Investigations powered by Aptos, IPFS, Vertex AI, Gemini, and BigQuery.**

**Project for the [HackerEarth Thunderdome Hackathon](https://thunderdome.hackerearth.com/)**

This application provides a secure way to store PDF files on IPFS, extract meaningful data from them, and store both metadata on the Aptos blockchain and text chunks in BigQuery for efficient searching and RAG-based chatting. At its core, **BlockPatrol** is a revolutionary platform designed to empower police officers and investigators with decentralized storage, AI-driven semantic search, immutable logging, and intelligent pattern recognition.

---

## 🎯 The Problem We Solve

Traditional methods of storing and analyzing criminal case files are often:

- **Insecure:** Prone to tampering, data loss, or unauthorized access when stored in physical archives or basic web portals.
- **Inefficient:** Requiring officers to manually sift through mountains of paperwork or disparate digital files, consuming valuable time.
- **Siloed:** Making it difficult to identify patterns, connect related cases, or share information effectively.

BlockPatrol addresses these challenges head-on.

---

## ✨ Our Solution

BlockPatrol offers a comprehensive suite of features:

1. **PDF Storage**: Upload PDF files to IPFS for decentralized storage.
2. **Data Extraction**: Extract structured data from PDFs using FastAPI.
3. **Immutable Evidence Logging on Aptos Blockchain**: Crucial metadata such as key evidence, file hash, and officer details are recorded immutably on Aptos.
4. **Text Chunk Storage & Embeddings**: Store chunks of PDF text in BigQuery; generate embeddings using Gemini or Vertex AI for efficient semantic search.
5. **AI-Powered Semantic Search & RAG-Based Chat**: Retrieve semantically similar cases and chat with documents using LLMs.
6. **Secure Authentication**: JWT-based FastAPI authentication ensures only authorized personnel access sensitive data.

---

## 🚀 Features

- **Decentralized File Storage (IPFS)**
- **Immutable Metadata (Aptos Blockchain)**
- **Semantic Search (BigQuery + Vertex AI/Gemini Embeddings)**
- **RAG-Based Chat with Documents**
- **Cross-Case Pattern Matching**
- **Secure Authentication with JWT**
- **Investigation Dashboard and Case Linking**

---

## ⚙️ Workflow Overview


\[User: Officer/Investigator]
|
\|--- Upload PDF ---> \[IPFS (Decentralized Storage)]
\|       |--- Returns IPFS Hash
|
\|--- Extract Metadata + Store IPFS Hash ---> \[Aptos Blockchain]
|
\|--- Chunk File + Generate Embeddings ---> \[Gemini / Vertex AI]
\|       |--- Store in ---> \[Google BigQuery]
|
\|--- Officer Search Query ---> \[FastAPI Endpoint]
\|--- Semantic Match ---> \[BigQuery Embeddings]
\|--- Display Relevant Cases + Chat + Links


---

## 🧱 Technology Stack

| Layer             | Technology                             |
| ----------------- | -------------------------------------- |
| Backend Framework | FastAPI (Python)                       |
| Authentication    | JWT                                    |
| Storage           | IPFS                                   |
| Blockchain        | Aptos                                  |
| Embeddings        | Google Vertex AI or Gemini API         |
| Data Store        | Google BigQuery                        |
| Frontend          | (Specify: React, Vue, Streamlit, etc.) |

---

## 🛠️ Requirements

- Python 3.8+
- FastAPI
- Google Cloud account (BigQuery)
- Aptos account and private key
- Gemini API key (for LLM chat)
- IPFS Node (local or remote)

---

## 📦 Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your-org/blockpatrol.git
   cd blockpatrol
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file:

   ```env
   # BigQuery
   BQ_PROJECT_ID=your-google-cloud-project-id
   BQ_DATASET=your-bigquery-dataset
   BQ_TABLE=your-bigquery-table
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

   # Gemini API
   GEMINI_API_KEY=your-gemini-api-key

   # Aptos
   APTOS_NODE_URL=https://fullnode.devnet.aptoslabs.com/v1
   ADMIN_PRIVATE_KEY=your-admin-private-key
   ```

4. Create the BigQuery table:

   ```sql
   CREATE TABLE `your-project-id.your-dataset.your-table` (
     chunk_id STRING,
     doc_id STRING,
     filename STRING,
     text STRING,
     original_pdf_ipfs_path STRING,
     pdf_metadata STRING
   );
   ```

---

## ▶️ Running the Application

```bash
uvicorn app.main:app --reload
```

Access API docs at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🔐 API Endpoints

### Authentication

* `POST /auth/register`: Register a new user
* `POST /auth/token`: Login and get access token

### Documents

* `POST /documents/upload`: Upload a PDF file
* `GET /documents/my-documents`: Get your uploaded documents
* `GET /documents/documents/{document_id}`: Retrieve specific document
* `POST /documents/search`: Search by transaction hash or Aptos address
* `GET /documents/ipfs/{ipfs_hash}`: Retrieve file from IPFS

### Text Chunks & RAG

* `POST /documents/search-chunks`

  ```json
  {
    "query": "your search term",
    "limit": 10
  }
  ```

* `POST /documents/chat`

  ```json
  {
    "query": "your question about the documents",
    "history": [
      {"role": "user", "content": "previous question"},
      {"role": "assistant", "content": "previous answer"}
    ]
  }
  ```

---

## 📖 Usage

1. Log in using your officer credentials.
2. Upload a new case file (PDF).
3. The file is stored on IPFS; metadata is logged on Aptos.
4. Chunks of text and embeddings are generated and stored in BigQuery.
5. Use search or chat to interact with case files, uncover similar crimes, or identify patterns.

---

## 🔮 Future Enhancements

* **Predictive AI Analytics**
* **Real-time Officer Collaboration**
* **GeoCrime Mapping (GIS)**
* **Per-Evidence Upload and Blockchain Anchoring**
* **Mobile App for Investigators**

---

## 🔐 Environment Setup

### BigQuery Setup

1. Create a GCP Project
2. Enable BigQuery API
3. Create Service Account with permissions
4. Download JSON Key
5. Set `GOOGLE_APPLICATION_CREDENTIALS` in `.env`
6. Create dataset and table as described

### Gemini API Setup

1. Sign up at [https://ai.google.dev](https://ai.google.dev)
2. Get an API Key
3. Set `GEMINI_API_KEY` in `.env`

---

## 🌟 Benefits

* **Saves Investigators Time**
* **Enhances Evidence Security**
* **Uncovers Hidden Crime Patterns**
* **Tamper-Proof Audit Trails**
* **Empowers Law Enforcement with AI**

---

## 📄 License

MIT License

Built for the **[HackerEarth Thunderdome Hackathon](https://thunderdome.hackerearth.com/)**.

---
