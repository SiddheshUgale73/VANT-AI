from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from rag_engine import RAGEngine
from langchain_core.messages import HumanMessage, AIMessage
import os
import shutil
import tempfile
from typing import List
from config import HOST, PORT, DEBUG, GROQ_API_KEY, AVAILABLE_MODELS

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not found. Please check your .env file.")

app = FastAPI(debug=DEBUG)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize RAG engine
rag_engine = RAGEngine()
history: List = []

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r") as f:
        return f.read()

@app.get("/models")
async def get_models():
    """List available LLM models."""
    return JSONResponse(content={"models": AVAILABLE_MODELS})

@app.post("/models/change")
async def change_model(model_id: str = Form(...)):
    """Switch the current LLM model."""
    try:
        rag_engine.change_model(model_id)
        return JSONResponse(content={"status": "success", "message": f"Model switched to {model_id}"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/documents")
async def list_docs():
    """List all indexed documents."""
    return JSONResponse(content={"documents": rag_engine.list_documents()})

@app.post("/process")
async def process_document(file: UploadFile = File(...)):
    try:
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = tmp_file.name
        
        try:
            rag_engine.process_document(tmp_path)
            # We don't clear history anymore to allow cross-document conversation
            return JSONResponse(content={
                "status": "success", 
                "message": f"{file.filename} added to VANT AI database."
            })
        except Exception as e:
            print(f"PROCESS ERROR: {e}")
            return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.delete("/documents/{filename}")
async def delete_document(filename: str):
    try:
        rag_engine.delete_document(filename)
        return JSONResponse(content={"status": "success", "message": f"{filename} removed."})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.post("/chat")
async def chat(message: str = Form(...)):
    try:
        global history
        result = rag_engine.query(message, history)
        response = result["answer"]
        sources = result["sources"]
        
        history.append(HumanMessage(content=message))
        history.append(AIMessage(content=response))
        
        # Keep history manageable (last 10 interactions)
        if len(history) > 20: 
            history = history[-20:]
            
        return JSONResponse(content={
            "status": "success", 
            "response": response,
            "sources": sources
        })
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    print(f"Starting VANT AI on http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
