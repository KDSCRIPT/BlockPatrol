# BlockPatrol 🚓

**Secure & Intelligent Criminal Investigations powered by Aptos, IPFS, Vertex AI, and BigQuery.**

**Project for the [HackerEarth Thunderdome Hackathon](https://thunderdome.hackerearth.com/)**

BlockPatrol is a revolutionary platform designed to empower police officers and investigators. It provides a secure, decentralized, and AI-driven solution for managing case files, uncovering critical evidence, and identifying connections between crimes. By leveraging cutting-edge technologies, BlockPatrol aims to transform traditional investigative processes, making them more efficient, secure, and insightful.

## 🎯 The Problem We Solve

Traditional methods of storing and analyzing criminal case files are often:
* **Insecure:** Prone to tampering, data loss, or unauthorized access when stored in physical archives or basic web portals.
* **Inefficient:** Requiring officers to manually sift through mountains of paperwork or disparate digital files, consuming valuable time.
* **Siloed:** Making it difficult to identify patterns, connect related cases, or share information effectively.

BlockPatrol addresses these challenges head-on.

## ✨ Our Solution: BlockPatrol

BlockPatrol offers a comprehensive suite of features:

1.  **Secure & Decentralized File Storage:** When a user (police officer/investigator) uploads a case file, it is securely stored on **IPFS (InterPlanetary File System)**. This ensures that the file is decentralized, resistant to censorship, and highly available.
2.  **Immutable Evidence Logging on Aptos Blockchain:** Crucial metadata from the file (such as key evidence, the unique IPFS file hash, and details of the investigating officer) is extracted and immutably recorded on the **Aptos blockchain**. This creates a transparent and tamper-proof audit trail.
3.  **AI-Powered Semantic Search:** The content of the uploaded file is chunked, and then **embeddings** are generated using **Google Cloud Vertex AI**. These embeddings, along with the text chunks, are stored in **Google BigQuery**. This enables powerful semantic search capabilities.
4.  **Intelligent Crime Pattern Recognition:** When an officer searches for key terms or phrases (e.g., "stab in left arm," "theft with a blue van"), BlockPatrol uses the AI-generated embeddings to find and display all previous cases exhibiting similar crime patterns. It can also highlight suspects involved in those prior related cases.
5.  **Secure Authentication:** User access is managed through a robust authentication system built with **FastAPI** and **JWT (JSON Web Tokens)**, ensuring that only authorized personnel can access sensitive investigative data.

## 🚀 Core Features

* **Decentralized File Storage:** Leveraging IPFS for resilient and secure file persistence.
* **Blockchain-Anchored Metadata:** Using Aptos for immutable and auditable records of case file details and evidence.
* **AI-Driven Semantic Search:** Powered by Vertex AI embeddings and BigQuery for intelligent querying and pattern matching.
* **Cross-Case Analysis:** Identifies similarities and links between different investigations.
* **Secure User Authentication:** FastAPI and JWT for controlled access.
* **Time-Saving Automation:** Reduces manual effort in searching and correlating case information.
* **Enhanced Data Integrity:** Protects files from tampering and accidental loss.

## ⚙️ Workflow Overview


[User: Officer/Investigator] --- (Uploads File via Web Interface) ---> [BlockPatrol Application]

BlockPatrol Application:
|
|--- 1. Authentication (FastAPI + JWT)
|
|--- 2. Store File ---> [IPFS (Decentralized Storage)]
|       |--- Returns IPFS Hash
|
|--- 3. Extract Metadata & IPFS Hash --- (Store on) ---> [Aptos Blockchain]
|
|--- 4. Chunk File Content & Generate Embeddings ---> [Google Cloud Vertex AI]
|       |--- Store Chunks & Embeddings ---> [Google BigQuery]
|
|--- 5. User Search Query (e.g., "stab in left arm")
|--- Query BigQuery (using embeddings for semantic match)
|--- Retrieve Relevant Cases, Patterns, Suspects
|--- Display Results to User

*(A visual diagram in this section would be highly beneficial.)*

## 🛠️ Technology Stack

* **Backend Framework:** Python, FastAPI
* **Authentication:** JWT (JSON Web Tokens)
* **Decentralized File Storage:** IPFS (InterPlanetary File System)
* **Blockchain Platform:** Aptos
* **AI/Machine Learning (Embeddings):** Google Cloud Vertex AI
* **Data Warehouse & Search Index:** Google BigQuery
* **Frontend:** (Specify your frontend technology, e.g., React, Vue, Streamlit, HTML/CSS/JS)

## 🌟 Benefits

* **Saves Time:** Drastically reduces the hours officers spend on manual file searches.
* **Enhances Security:** Protects sensitive case files from tampering, unauthorized access, and data loss.
* **Improves Investigative Outcomes:** Helps uncover hidden connections and identify suspects more effectively.
* **Ensures Data Integrity:** Provides a verifiable and auditable trail for all case file interactions.
* **Modernizes Law Enforcement:** Brings cutting-edge technology to critical investigative processes.


## 📖 Usage

1.  Log in using your officer credentials.
2.  Upload new case files.
3.  Use the search bar to query existing cases using keywords, phrases, or descriptions of crime patterns.
4.  Review the results, which will include related cases, suspect information, and highlighted similarities.

## 🔮 Future Enhancements

* **Advanced AI Analytics:** Implement features like anomaly detection in case data or predictive insights (with ethical considerations).
* **Real-time Collaboration:** Allow multiple officers to work on a case simultaneously with live updates.
* **GIS Integration:** Map crime patterns geographically.
* **Direct Evidence Upload:** Allow officers to upload individual pieces of evidence (photos, notes) directly linked to a case on the blockchain.
* **Mobile Application:** Develop a mobile app for field access.


## 📄 License
MIT License

Built for the **[HackerEarth Thunderdome Hackathon](https://thunderdome.hackerearth.com/)**.
