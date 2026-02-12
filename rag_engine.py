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
from config import GROQ_API_KEY, DEFAULT_MODEL, DB_DIR, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP

class RAGEngine:
    def __init__(self):
        # Local HuggingFace embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'}
        )
        
        # Load or create persistent vector store
        self.vectorstore = Chroma(
            persist_directory=DB_DIR,
            embedding_function=self.embeddings
        )
        
        # Groq-powered Chat model
        self.llm = ChatGroq(
            model_name=DEFAULT_MODEL,
            temperature=0,
            groq_api_key=GROQ_API_KEY
        )
        
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        self._create_rag_chain()

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
        
        # Re-initialize retriever and chain to include new documents
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        self._create_rag_chain()

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

    def _create_rag_chain(self):
        """Setup conversational RAG flow."""
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
            self.llm, self.retriever, contextualize_q_prompt
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
