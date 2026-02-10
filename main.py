from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from rag_engine import RAGEngine
from langchain_core.messages import HumanMessage, AIMessage
import os
import shutil
import tempfile
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    print("WARNING: GROQ_API_KEY not found in environment variables or .env file.")

app = FastAPI()

# Mount static files
static_dir = os.path.join(os.getcwd(), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global state for RAG engine and history
# In a real app, this should be session-based or handled via a database
rag_engine = RAGEngine()
history = []

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r") as f:
        return f.read()

@app.post("/process")
async def process_document(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = tmp_file.name
        
        try:
            rag_engine.process_document(tmp_path)
            # Clear history when a new document is processed
            global history
            history = []
            return JSONResponse(content={"status": "success", "message": f"{file.filename} processed and indexed."})
        except Exception as e:
            return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.post("/chat")
async def chat(message: str = Form(...)):
    try:
        result = rag_engine.query(message, history)
        response = result["answer"]
        sources = result["sources"]
        
        # Update history
        history.append(HumanMessage(content=message))
        history.append(AIMessage(content=response))
        
        return JSONResponse(content={
            "status": "success", 
            "response": response,
            "sources": sources
        })
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9000)
