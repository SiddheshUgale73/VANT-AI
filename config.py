"""
VANT AI: Global Configuration File
Centralizes all settings for API keys, security, RAG parameters, and server info.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- 1. AI SERVICE CONFIGURATION ---
# We use Groq for high-speed LLM inference.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- 2. SECURITY & AUTHENTICATION ---
# Used for JWT token signing and session security.
SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_vant_ai_key_change_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # Tokens last for 24 hours

# --- 3. LLM MODEL SELECTION ---
# Users can switch between these models in the UI dashboard.
DEFAULT_MODEL = "llama-3.1-8b-instant"
AVAILABLE_MODELS = [
    {"name": "Llama 3.3 70B (High Precision)", "id": "llama-3.3-70b-versatile"},
    {"name": "Llama 3.1 8B (High Speed)", "id": "llama-3.1-8b-instant"},
    {"name": "Mixtral 8x7B (Balanced)", "id": "mixtral-8x7b-32768"},
    {"name": "Llama 3.2 3B (Ultra Lightweight)", "id": "llama-3.2-3b-preview"}
]

# --- 4. RAG (Retrieval Augmented Generation) SETTINGS ---
# Controls how documents are indexed and stored.
DB_DIR = "vector_db"              # Directory for persistent ChromaDB storage
EMBEDDING_MODEL = "all-MiniLM-L6-v2" # Sentence-transformers model for vectors
CHUNK_SIZE = 1000                  # Character count per document chunk
CHUNK_OVERLAP = 200                # Overlap between chunks for context continuity

# --- 5. SERVER INFRASTRUCTURE ---
# Host and Port settings for the FastAPI server.
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 9005))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

