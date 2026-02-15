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
from langchain_community.retrievers import BM25Retriever
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from typing import List, Optional
from config import GROQ_API_KEY, DEFAULT_MODEL, DB_DIR, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP

class HybridRetriever(BaseRetriever):
    vector_retriever: BaseRetriever
    bm25_retriever: Optional[BaseRetriever]
    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        # Get semantic results
        vector_docs = self.vector_retriever.invoke(query, config={"callbacks": run_manager.get_child()})
        
        if not self.bm25_retriever:
            return vector_docs
            
        # Get keyword results
        bm25_docs = self.bm25_retriever.invoke(query, config={"callbacks": run_manager.get_child()})
        
        # Merge and de-duplicate based on content
        all_docs = vector_docs + bm25_docs
        seen_content = set()
        unique_docs = []
        for doc in all_docs:
            if doc.page_content not in seen_content:
                unique_docs.append(doc)
                seen_content.add(doc.page_content)
        
        return unique_docs

class RAGEngine:
    def __init__(self):
        # Local HuggingFace embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'}
        )
        
        # Load or create persistent vector store
        self.vectorstore = Chr0oma(
            persist_directory=DB_DIR,
            embedding_function=self.embeddings
        )
        
        # Groq-powered Chat model
        self.llm = ChatGroq(
            model_name=DEFAULT_MODEL,
            temperature=0,
            groq_api_key=GROQ_API_KEY
        )
        
        self.vector_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        self.bm25_retriever = None
        self._initialize_bm25()
        self._create_rag_chain()

    def _initialize_bm25(self):
        """Build BM25 retriever from all documents in vectorstore."""
        data = self.vectorstore.get()
        if data and 'documents' in data and data['documents']:
            # LangChain BM25 expects a list of Document objects
            docs = []
            for i in range(len(data['documents'])):
                docs.append(Document(
                    page_content=data['documents'][i],
                    metadata=data['metadatas'][i]
                ))
            self.bm25_retriever = BM25Retriever.from_documents(docs)
            self.bm25_retriever.k = 5

    def change_model(self, model_name: str):
        """Switch the underlying LLM model."""
        self.llm = ChatGroq(
            model_name=model_name,
            temperature=0,
            groq_api_key=GROQ_API_KEY
        )
        self._create_rag_chain()
        return True

    def process_document(self, file_path: str):
        """Load, split, and add document to persistent ChromaDB index."""
        ext = file_path.lower()
        if ext.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
        elif ext.endswith('.docx'):
            loader = Docx2txtLoader(file_path)
        elif ext.endswith('.csv'):
            loader = CSVLoader(file_path)
        elif ext.endswith('.xlsx'):
            # Use pandas directly for better reliability than Unstructured
            loader = None
            try:
                df_dict = pd.read_excel(file_path, sheet_name=None)
                docs = []
                for sheet_name, df in df_dict.items():
                    content = df.to_string(index=False)
                    docs.append(Document(page_content=content, metadata={"source": os.path.basename(file_path), "sheet": sheet_name}))
            except Exception as e:
                raise Exception(f"Excel Load Error: {str(e)}")
        else:
            loader = TextLoader(file_path)
        
        if loader:
            docs = loader.load()
        # Add metadata about the source
        for doc in docs:
            doc.metadata["source"] = os.path.basename(file_path)
            
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, 
            chunk_overlap=CHUNK_OVERLAP
        )
        splits = text_splitter.split_documents(docs)
        
        # Add to existing vectorstore instead of recreating
        self.vectorstore.add_documents(documents=splits)
        
        # Re-initialize retrievers and chain
        self.vector_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        self._initialize_bm25()
        self._create_rag_chain()

    def delete_document(self, filename: str):
        """Remove all embeddings for a specific document from ChromaDB."""
        if not self.vectorstore:
            return
            
        # Find all IDs associated with this source
        data = self.vectorstore.get(where={"source": filename})
        if data and 'ids' in data and data['ids']:
            self.vectorstore.delete(ids=data['ids'])
            
        # Re-initialize retrievers and chain
        self.vector_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        self._initialize_bm25()
        self._create_rag_chain()
        return True

    def list_documents(self):
        """Return a list of unique document names currently in the index."""
        if not self.vectorstore:
            return []
        
        # Get all metadata from the vectorstore
        data = self.vectorstore.get()
        if not data or 'metadatas' not in data:
            return []
            
        sources = set()
        for meta in data['metadatas']:
            if 'source' in meta:
                sources.add(meta['source'])
        return sorted(list(sources))

    def summarize_document(self, filename: str):
        """Generate a 3-bullet summary for a specific document."""
        if not self.vectorstore:
            return "No documents indexed."
            
        # Get chunks for this document
        data = self.vectorstore.get(where={"source": filename})
        if not data or 'documents' not in data or not data['documents']:
            return "Document content not found."
            
        # Combine a reasonable amount of text for summarization (e.g., first 5000 chars)
        content = "\n".join(data['documents'])
        limited_content = content[:10000] # Safe limit for context window
        
        prompt = (
            f"Please provide a concise 3-bullet point summary of the following document content. "
            f"Focus on the main topics and key takeaways.\n\n"
            f"Content:\n{limited_content}"
        )
        
        try:
            response = self.llm.invoke(prompt)
            # Ensure it's in markdown list format
            return response.content
        except Exception as e:
            return f"Summarization Error: {str(e)}"

    def _create_rag_chain(self):
        """Setup conversational RAG flow with Hybrid Search (Manual Merge)."""
        # Initialize our custom hybrid retriever
        retriever = HybridRetriever(
            vector_retriever=self.vector_retriever,
            bm25_retriever=self.bm25_retriever
        )

        contextualize_q_system_prompt = (
            "Given a chat history and the latest user question "
            "which might reference context in the chat history, "
            "formulate a standalone question which can be understood "
            "without the chat history. Do NOT answer the question, "
            "just reformulate it if needed and otherwise return it as is."
        )
        
        contextualize_q_prompt = ChatPromptTemplate.from_messages([
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        
        history_aware_retriever = create_history_aware_retriever(
            self.llm, retriever, contextualize_q_prompt
        )

        system_prompt = (
            "You are a highly precise AI assistant. Answer questions "
            "EXCLUSIVELY based on the provided context. If the answer is "
            "not in the documents, say 'I cannot find this information in "
            "the current knowledge base.' Use clear Markdown formatting.\n\n"
            "Context:\n{context}"
        )
        
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        
        question_answer_chain = create_stuff_documents_chain(self.llm, qa_prompt)
        self.rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    def query(self, question: str, chat_history: list = []):
        """Invoke the full RAG chain and return answer + sources."""
        if not self.rag_chain:
            return {"answer": "Engine not initialized.", "sources": []}
        
        result = self.rag_chain.invoke({
            "input": question,
            "chat_history": chat_history
        })
        
        sources = []
        if "context" in result:
            seen_sources = set()
            for doc in result["context"]:
                source_name = doc.metadata.get("source", "Unknown")
                if source_name not in seen_sources:
                    sources.append(source_name)
                    seen_sources.add(source_name)
        
        return {
            "answer": result["answer"],
            "sources": sources
        }
