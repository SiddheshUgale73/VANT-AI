import os
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from dotenv import load_dotenv

load_dotenv()

class RAGEngine:
    def __init__(self, model_name="llama-3.3-70b-versatile"):
        # Groq-powered Chat model
        self.llm = ChatGroq(
            model_name=model_name,
            temperature=0,
            groq_api_key=os.getenv("GROQ_API_KEY")
        )
        
        # Local HuggingFace embeddings (Free & Privacy-focused)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
        
        self.vectorstore = None
        self.retriever = None
        self.rag_chain = None

    def process_document(self, file_path):
        """Load, split, and index a document in ChromaDB."""
        if file_path.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
        elif file_path.endswith('.docx'):
            loader = Docx2txtLoader(file_path)
        else:
            loader = TextLoader(file_path)
        
        docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        splits = text_splitter.split_documents(docs)
        
        self.vectorstore = Chroma.from_documents(documents=splits, embedding=self.embeddings)
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 10})
        self._create_rag_chain()

    def _create_rag_chain(self):
        """Setup the full conversational RAG flow using Groq."""
        
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
            "You are a highly precise AI assistant. Your goal is to answer questions "
            "based EXCLUSIVELY on the provided context. Follow these strict rules:\n"
            "1. Be as literal and exact as possible. Do not generalize or summarize unless asked.\n"
            "2. If the context contains a specific number, name, or date, include it exactly.\n"
            "3. If the answer is not in the context, say 'I cannot find this information in the documents.'\n"
            "4. Use clear Markdown (bolding and bullet points) to highlight specific facts.\n\n"
            "Context:\n{context}"
        )
        
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        
        question_answer_chain = create_stuff_documents_chain(self.llm, qa_prompt)
        self.rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    def query(self, question, chat_history=[]):
        """Invoke the full RAG chain and return answer + sources."""
        if not self.rag_chain:
            return {"answer": "Please upload and process a document first.", "sources": []}
        
        result = self.rag_chain.invoke({
            "input": question,
            "chat_history": chat_history
        })
        
        # Extract unique sources
        sources = []
        if "context" in result:
            seen_sources = set()
            for doc in result["context"]:
                source_name = os.path.basename(doc.metadata.get("source", "Unknown"))
                if source_name not in seen_sources:
                    sources.append(source_name)
                    seen_sources.add(source_name)
        
        return {
            "answer": result["answer"],
            "sources": sources
        }
