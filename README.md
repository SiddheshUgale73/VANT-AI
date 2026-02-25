# VANT AI - Private RAG Chatbot

VANT AI is a modern, high-performance Retrieval-Augmented Generation (RAG) application that allows you to chat with your local documents (PDF, DOCX, TXT, CSV, XLSX) privately and securely.

## 🚀 Features

- **Private & Local**: Your data never leaves your machine.
- **Multi-Format Support**: Process PDF, Microsoft Word (`.docx`), Plain Text (`.txt`), CSV (`.csv`), and Excel (`.xlsx`) files.
- **Glassmorphic UI**: A premium, modern interface with a dark tech aesthetic.
- **Fast Indexing**: Uses HuggingFace embeddings for efficient document retrieval.
- **Citations**: Automatically shows sources for every answer.

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **LLM Engine**: Groq (Llama models)
- **RAG Framework**: LangChain
- **Embeddings**: HuggingFace (`sentence-transformers/all-MiniLM-L6-v2`)
- **Vector Store**: ChromaDB
- **Frontend**: Vanilla HTML5, CSS3 (Custom Glassmorphism), JavaScript (ES6)

## 📋 Prerequisites

- Python 3.8+
- A Groq API Key (Get it at [console.groq.com](https://console.groq.com/))

## ⚙️ Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/SiddheshUgale73/VANT-AI.git
   cd VANT-AI
   ```

2. **Set up a Virtual Environment** (Optional but recommended):
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows
   # or source venv/bin/activate  # macOS/Linux
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Create a `.env` file in the root directory and add your Groq API Key:
   ```env
   GROQ_API_KEY=your_api_key_here
   ```

## 🏃 How to Run

1. **Start the server**:
   ```bash
   python main.py
   ```

2. **Access the application**:
   Open your browser and navigate to:
   [http://127.0.0.1:9000](http://127.0.0.1:9000)

## 🐳 Running with Docker

1. **Build the image**:
   ```bash
   docker build -t vant-ai .
   ```

2. **Run the container**:
   ```bash
   docker run -p 8000:8000 --env-file .env vant-ai
   ```

## ☁️ Cloud Deployment

VANT AI can be deployed to any platform that supports Docker.

### 1. Render / Railway
- Connect your GitHub repository.
- **Root Directory**: `./`
- **Runtime**: `Docker`
- **Environment Variables**: Add `GROQ_API_KEY`.
- **Persistence**: Add a "Disk" mount at `/app/vector_db` and `/app/chat_history.db` to keep your documents and chat logs between restarts.

### 2. Hugging Face Spaces
- Create a new Space.
- Select `Docker` as the SDK.
- Upload your files or sync with GitHub.
- Add `GROQ_API_KEY` to the Space's Secrets.

## 📖 Usage

1. **Upload**: Use the sidebar to upload a document.
2. **Wait**: VANT AI will process and index the content.
3. **Chat**: Ask any question about your document in the chat box.
4. **Learn**: Hover over source badges to see where the information came from.

## 🛡️ Privacy

This project is built with privacy in mind. The `.env` file is ignored by Git to prevent API key leaks. Always ensure you do not commit your `.env` file to public repositories.
