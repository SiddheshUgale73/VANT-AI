from fastapi import FastAPI, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from rag_engine import RAGEngine
from langchain_core.messages import HumanMessage, AIMessage
import os
import shutil
import tempfile
from typing import List
from config import HOST, PORT, DEBUG, GROQ_API_KEY, AVAILABLE_MODELS
import session_db
from sqlalchemy.orm import Session

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not found. Please check your .env file.")

# Initialize SQLite DB
session_db.init_db()

app = FastAPI(debug=DEBUG)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize RAG engine
rag_engine = RAGEngine()

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

@app.get("/sessions")
async def list_sessions(db: Session = Depends(session_db.get_db)):
    """List all chat sessions."""
    sessions = db.query(session_db.ChatSession).order_by(session_db.ChatSession.created_at.desc()).all()
    return JSONResponse(content={"sessions": [{"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()} for s in sessions]})

@app.post("/sessions")
async def create_session(db: Session = Depends(session_db.get_db)):
    """Create a new chat session."""
    session = session_db.ChatSession()
    db.add(session)
    db.commit()
    db.refresh(session)
    return JSONResponse(content={"status": "success", "session_id": session.id, "title": session.title})

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: Session = Depends(session_db.get_db)):
    """Delete a chat session and its messages."""
    session = db.query(session_db.ChatSession).filter(session_db.ChatSession.id == session_id).first()
    if session:
        db.delete(session)
        db.commit()
        return JSONResponse(content={"status": "success", "message": "Session deleted."})
    return JSONResponse(content={"status": "error", "message": "Session not found."}, status_code=404)

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

@app.get("/summarize/{filename}")
async def summarize_document(filename: str):
    try:
        summary = rag_engine.summarize_document(filename)
        return JSONResponse(content={"status": "success", "summary": summary})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.delete("/documents/{filename}")
async def delete_document(filename: str):
    try:
        rag_engine.delete_document(filename)
        return JSONResponse(content={"status": "success", "message": f"{filename} removed."})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, db: Session = Depends(session_db.get_db)):
    """Get message history for a session."""
    messages = db.query(session_db.ChatMessage).filter(session_db.ChatMessage.session_id == session_id).order_by(session_db.ChatMessage.created_at.asc()).all()
    return JSONResponse(content={"messages": [{"role": m.role, "content": m.content} for m in messages]})

@app.post("/chat")
async def chat(message: str = Form(...), session_id: str = Form(...), db: Session = Depends(session_db.get_db)):
    try:
        # 1. Load history from DB
        db_messages = db.query(session_db.ChatMessage).filter(session_db.ChatMessage.session_id == session_id).order_by(session_db.ChatMessage.created_at.asc()).all()
        
        langchain_history = []
        for m in db_messages:
            if m.role == 'user':
                langchain_history.append(HumanMessage(content=m.content))
            else:
                langchain_history.append(AIMessage(content=m.content))
        
        # 2. Query RAG Engine
        result = rag_engine.query(message, langchain_history)
        response = result["answer"]
        sources = result["sources"]
        
        # 3. Save to DB
        user_msg = session_db.ChatMessage(session_id=session_id, role='user', content=message)
        ai_msg = session_db.ChatMessage(session_id=session_id, role='assistant', content=response)
        db.add(user_msg)
        db.add(ai_msg)
        
        # 4. Auto-update title if it's the first message
        session = db.query(session_db.ChatSession).filter(session_db.ChatSession.id == session_id).first()
        if session and session.title == "New Chat":
            session.title = message[:30] + ("..." if len(message) > 30 else "")
            
        db.commit()
            
        return JSONResponse(content={
            "status": "success", 
            "response": response,
            "sources": sources
        })
    except Exception as e:
        print(f"CHAT ERROR: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    print(f"Starting VANT AI on http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
