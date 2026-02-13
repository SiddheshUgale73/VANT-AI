import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# AI Models
DEFAULT_MODEL = "llama-3.3-70b-versatile"
AVAILABLE_MODELS = [
    {"name": "Llama 3.3 70B", "id": "llama-3.3-70b-versatile"},
    {"name": "Llama 3.1 8B", "id": "llama-3.1-8b-instant"},
    {"name": "Mixtral 8x7B", "id": "mixtral-8x7b-32768"},
    {"name": "Gemma 2 9B", "id": "gemma2-9b-it"}
]

# RAG Configuration
DB_DIR = "vector_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Server Configuration
HOST = "127.0.0.1"
PORT = 9000
DEBUG = True
