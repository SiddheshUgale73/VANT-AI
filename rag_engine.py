import os
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader, CSVLoader
from langchain_core.documents import Document 
import pandas as pd 
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

# Externalized Configuration & Prompts
from config import GROQ_API_KEY, DEFAULT_MODEL, DB_DIR, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP
from prompts import CONTEXTUALIZE_Q_SYSTEM_PROMPT, RAG_SYSTEM_PROMPT, SUMMARIZATION_PROMPT_TEMPLATE

class RAGEngine:
    """
    The core AI engine of VANT AI. 
    Handles document indexing, hybrid search (Vector + BM25), and RAG chain orchestration.
    """
    def __init__(self):
        """Initialize embeddings, vector store, and the Groq LLM client."""
        # 1. Initialize Local Embeddings (CPU-based)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'}
        )
        
        # 2. Connect to Persistent ChromaDB
        self.vectorstore = Chroma(
            persist_directory=DB_DIR,
            embedding_function=self.embeddings
        )
        
        # 3. Setup Groq LLM
        self.llm = ChatGroq(
            model_name=DEFAULT_MODEL,
            temperature=0,
            groq_api_key=GROQ_API_KEY
        )
        
        # 4. Prepare Search & Retrieval Layers
        self.vector_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        self.bm25_retriever = None
        self._initialize_bm25()
        self._create_rag_chain()

    def _initialize_bm25(self):
        """Prepare the BM25 (Keyword) retriever using current documents in ChromaDB."""
        data = self.vectorstore.get()
        if data and 'documents' in data and data['documents']:
            docs = [
                Document(page_content=data['documents'][i], metadata=data['metadatas'][i])
                for i in range(len(data['documents']))
            ]
            self.bm25_retriever = BM25Retriever.from_documents(docs)
            self.bm25_retriever.k = 5

    def change_model(self, model_name: str):
        """Update the LLM model used for inference (e.g., switching from Llama to Mixtral)."""
        self.llm = ChatGroq(
            model_name=model_name,
            temperature=0,
            groq_api_key=GROQ_API_KEY
        )
        self._create_rag_chain()
        return True

    def process_document(self, file_path: str):
        """
        Load a file (PDF, DOCX, CSV, XLSX, TXT), split it into chunks, 
        and add it to the vector database.
        """
        ext = file_path.lower()
        if ext.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
            docs = loader.load()
        elif ext.endswith('.docx'):
            loader = Docx2txtLoader(file_path)
            docs = loader.load()
        elif ext.endswith('.csv'):
            loader = CSVLoader(file_path)
            docs = loader.load()
        elif ext.endswith('.xlsx'):
            docs = self._load_excel_sheets(file_path)
        else:
            loader = TextLoader(file_path)
            docs = loader.load()

        # Add uniform metadata
        for doc in docs:
            doc.metadata["source"] = os.path.basename(file_path)
            
        # Split documents into manageable chunks
        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        self.vectorstore.add_documents(documents=splitter.split_documents(docs))
        
        # Refresh the search chain with new data
        self._initialize_bm25()
        self._create_rag_chain()

    def _load_excel_sheets(self, file_path: str):
        """Helper to process multi-sheet Excel files into documents."""
        try:
            df_dict = pd.read_excel(file_path, sheet_name=None)
            sheets = []
            for sheet_name, df in df_dict.items():
                sheets.append(Document(
                    page_content=df.to_string(index=False), 
                    metadata={"source": os.path.basename(file_path), "sheet": sheet_name}
                ))
            return sheets
        except Exception as e:
            raise Exception(f"Excel Processing Error: {str(e)}")

    def delete_document(self, filename: str):
        """Remove a document's embeddings from the database by its filename."""
        if not self.vectorstore: return
        
        data = self.vectorstore.get(where={"source": filename})
        if data and 'ids' in data and data['ids']:
            self.vectorstore.delete(ids=data['ids'])
            
        self._initialize_bm25()
        self._create_rag_chain()
        return True

    def list_documents(self):
        """Get the unique names of all indexed documents."""
        data = self.vectorstore.get()
        if not data or 'metadatas' not in data: return []
        return sorted(list(set(m['source'] for m in data['metadatas'] if 'source' in m)))

    def summarize_document(self, filename: str):
        """Generate a 3-bullet summary for a specific document using LLM-based distillation."""
        data = self.vectorstore.get(where={"source": filename})
        if not data or not data['documents']: return "Document not found."
            
        content = "\n".join(data['documents'])[:10000] # Cap content to avoid context limits
        prompt = SUMMARIZATION_PROMPT_TEMPLATE.format(content=content)
        
        try:
            return self.llm.invoke(prompt).content
        except Exception as e:
            return f"Summarization Error: {str(e)}"

    def _create_rag_chain(self):
        """
        Orchestrate the LangChain RAG pipeline.
        Combines history-awareness, hybrid retrieval (Ensemble), and prompt templates.
        """
        # 1. Setup Retrieval Layer (Hybrid Search)
        base_retriever = EnsembleRetriever(
            retrievers=[self.bm25_retriever, self.vector_retriever],
            weights=[0.3, 0.7] # 0.7 weight for semantic, 0.3 for keyword
        ) if self.bm25_retriever else self.vector_retriever

        # 2. History-Aware Retrieval (Re-formulates query based on context)
        context_prompt = ChatPromptTemplate.from_messages([
            ("system", CONTEXTUALIZE_Q_SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        h_retriever = create_history_aware_retriever(self.llm, base_retriever, context_prompt)

        # 3. Dedicated Answer Generation
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        doc_chain = create_stuff_documents_chain(self.llm, qa_prompt)
        
        # 4. Final RAG Chain
        self.rag_chain = create_retrieval_chain(h_retriever, doc_chain)

    def query(self, question: str, chat_history: list = []):
        """Execute a RAG query and return the answer along with unique sources."""
        if not self.rag_chain:
            return {"answer": "AI Engine is initializing...", "sources": []}
        
        raw_result = self.rag_chain.invoke({"input": question, "chat_history": chat_history})
        
        # Extract unique sources from retrieved context chunks
        sources = sorted(list(set(d.metadata.get("source", "Unknown") for d in raw_result.get("context", []))))
        
        return {"answer": raw_result["answer"], "sources": sources}
