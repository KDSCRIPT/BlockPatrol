import os
import json
import logging
from typing import List, Dict, Optional, Tuple
import google.generativeai as genai
from app.schemas.document import TextChunk, ChatMessage

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Gemini with API key from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini API initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini API: {e}")


class LLMService:
    def __init__(self):
        """Initialize the LLM service."""
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set. LLM functionality will not work.")
            self.model = None
        else:
            try:
                # Use Gemini 1.5 Pro for better reasoning and comparative analysis
                self.model = genai.GenerativeModel('gemini-2.0-flash')
            except Exception as e:
                logger.error(f"Error initializing Gemini model: {e}")
                self.model = None

    def is_available(self) -> bool:
        """Check if the LLM service is available."""
        return self.model is not None
    
    def analyze_query_intent(self, query: str) -> Dict[str, any]:
        """Analyze the user's query to determine intent and appropriate tool to use."""
        if not self.is_available():
            logger.warning("LLM not available for query analysis.")
            return {"type": "general", "search_terms": query}
        
        try:
            intent_prompt = f"""
            Analyze this query about case files and categorize its intent. Output a JSON object with the following structure:
            {{
              "type": "[one of: comparison, pattern, timeline, entity, relationship, general]",
              "search_terms": "extracted keywords for search",
              "cases_to_compare": ["case1", "case2", ...] (only if type is comparison),
              "entities_to_track": ["entity1", "entity2", ...] (only if relevant)
            }}
            
            Only include relevant fields based on the query type.

            Example intents:
            - comparison: Looking for similarities or differences between specific cases
            - pattern: Seeking recurring patterns across cases
            - timeline: Requesting chronological analysis 
            - entity: Asking about specific persons, organizations, etc.
            - relationship: Inquiring about connections between entities
            - general: General case information queries

            User query: "{query}"
            """
            
            response = self.model.generate_content(intent_prompt)
            try:
                intent_data = json.loads(response.text.strip())
                logger.info(f"Query intent analyzed: {intent_data['type']}")
                return intent_data
            except json.JSONDecodeError:
                logger.warning("Failed to parse intent analysis JSON. Using general type.")
                return {"type": "general", "search_terms": query}
        except Exception as e:
            logger.error(f"Error analyzing query intent: {e}")
            return {"type": "general", "search_terms": query}

    def enhance_search_query(self, query: str) -> str:
        """Generate an enhanced search query using Gemini."""
        if not self.is_available():
            logger.warning("LLM not available for query enhancement. Using original query.")
            return query
        
        try:
            # Get the query intent first
            intent = self.analyze_query_intent(query)
            
            # Customize prompt based on the intent type
            if intent["type"] == "comparison":
                prompt = f"""
                Extract the most specific keywords from this case comparison query.
                Focus on case identifiers, unique details, entities mentioned, and key facts.
                Only output the search terms with no explanation.
                
                User query about comparing cases: "{query}"
                """
            elif intent["type"] == "pattern":
                prompt = f"""
                Extract pattern-related keywords from this query about recurring elements across cases.
                Focus on behaviors, methods, sequences, techniques or characteristics mentioned.
                Only output the search terms with no explanation.
                
                User query about patterns: "{query}"
                """
            else:
                prompt = f"""
                Extract the most relevant search keywords from this case file query.
                Focus on entities, actions, dates, locations, and specific case details.
                Return only search terms without explanation or commentary.
                
                User query: "{query}"
                """
            
            response = self.model.generate_content(prompt)
            enhanced_query = response.text.strip()
            logger.info(f"Enhanced original query '{query}' to '{enhanced_query}'")
            return enhanced_query
        except Exception as e:
            logger.error(f"Error enhancing search query: {e}")
            return query  # Fall back to original query

    def generate_rag_prompt(self, query: str, chunks: List[TextChunk], history: Optional[List[ChatMessage]] = None) -> str:
        """Generate a RAG prompt using the query and retrieved chunks."""
        # Analyze query intent to customize the approach
        intent = self.analyze_query_intent(query)
        
        # Group chunks by document/case for better analysis
        cases = {}
        for chunk in chunks:
            if chunk.doc_id not in cases:
                cases[chunk.doc_id] = []
            cases[chunk.doc_id].append(chunk)
        
        # Format chunks for the prompt, grouped by case
        context_sections = []
        for doc_id, doc_chunks in cases.items():
            # Get a representative filename
            filename = doc_chunks[0].filename if doc_chunks else "Unknown"
            
            # Combine text from chunks of the same case
            case_texts = [chunk.text for chunk in doc_chunks]
            combined_text = "\n\n".join(case_texts)
            
            # Add this case to the context
            context_sections.append(f"CASE FILE: {filename}\nCASE ID: {doc_id}\nCONTENT:\n{combined_text}")
        
        context_text = "\n\n============================\n\n".join(context_sections)
        
        # Format conversation history if provided
        conversation_history = ""
        if history and len(history) > 0:
            conversation_history = "\n".join([
                f"{msg.role}: {msg.content}" for msg in history
            ])
            conversation_history = f"\n\nConversation history:\n{conversation_history}\n\n"
        
        # Customize system prompt based on intent
        if intent["type"] == "comparison":
            system_role = """You are an advanced case analysis assistant specialized in comparing legal cases. 
When analyzing similarities and differences between cases, focus on:
- Procedural similarities/differences
- Factual parallels
- Related entities across cases
- Similar legal arguments or precedents
- Timeline alignment or divergence
- Evidence patterns"""
        elif intent["type"] == "pattern":
            system_role = """You are an advanced case analysis assistant specialized in identifying patterns across cases.
Identify recurring elements such as:
- Behavioral patterns of involved parties
- Procedural similarities
- Common tactics or methodologies
- Temporal patterns or sequences
- Geographic connections
- Recurring entities or relationships"""
        elif intent["type"] == "timeline" or intent["type"] == "relationship":
            system_role = """You are an advanced case analysis assistant specialized in analyzing relationships and chronology.
Focus on:
- Chronological sequence of events across cases
- Connections between entities
- Cause-effect relationships
- Network analysis of involved parties
- Temporal proximity of related events"""
        else:
            system_role = """You are an advanced case analysis assistant specialized in extracting insights from legal case files.
Provide accurate, concise answers based solely on the case file content."""
        
        # Construct the full prompt
        prompt = f"""{system_role}

Format your response as a professional report on the case file contents.
Use only the information from the provided case files to answer the question.
If you cannot find the answer in the case files, admit that you don't know rather than making up information.

{conversation_history}
Here are the relevant case file contents:

{context_text}

Question: {query}

Answer:"""
        
        return prompt

    def generate_response(self, query: str, chunks: List[TextChunk], history: Optional[List[ChatMessage]] = None) -> str:
        """Generate a response based on the query and retrieved chunks."""
        if not self.is_available():
            return "LLM service is not available. Please set the GEMINI_API_KEY environment variable."
        
        try:
            # Generate the prompt with RAG context
            prompt = self.generate_rag_prompt(query, chunks, history)
            
            # Generate response from Gemini
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return f"Error generating response: {str(e)}"
            
    def generate_multi_query(self, query: str) -> List[str]:
        """Generate multiple search queries to improve recall for complex questions."""
        if not self.is_available():
            return [query]
            
        try:
            prompt = f"""
            Generate 3 different search queries to find relevant information about this question related to case files.
            Format the output as a JSON array of strings, each representing a different query approach.
            No explanation or commentary, just the JSON array.
            
            User question: "{query}"
            """
            
            response = self.model.generate_content(prompt)
            try:
                queries = json.loads(response.text.strip())
                if isinstance(queries, list) and len(queries) > 0:
                    logger.info(f"Generated multiple search queries for '{query}'")
                    return queries
                return [query]
            except json.JSONDecodeError:
                return [query]
        except Exception as e:
            logger.error(f"Error generating multiple queries: {e}")
            return [query] 