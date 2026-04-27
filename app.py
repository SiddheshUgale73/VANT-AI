# --- VANT AI: Backend API Layer ---
# This file handles HTTP requests, authentication, and orchestrates the AI engine.

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from rag_engine import RAGEngine
from langchain_core.messages import HumanMessage, AIMessage
import os  
import shutil
import logging
from typing import Optional
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

# Local Modules
import session_db
import auth
from config import HOST, PORT, DEBUG, AVAILABLE_MODELS

# ---------------------------------------------------------
# 1. SETUP & INITIALIZATION
# ---------------------------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VANT-AI")

session_db.init_db()
rag_engine: Optional[RAGEngine] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles background initialization of the AI Engine to ensure fast startup."""
    import threading
    def load_engine():
        global rag_engine
        try:
            logger.info("Initializing RAG Engine...")
            rag_engine = RAGEngine()
            logger.info("RAG Engine ready.")
        except Exception as e:
            logger.error(f"Engine Startup Error: {e}")

    threading.Thread(target=load_engine, daemon=True).start()
    yield

app = FastAPI(title="VANT AI API", debug=DEBUG, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_engine():
    """Dependency helper to ensure the AI engine is ready before use."""
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="AI engine is still warming up. Please try again in 30 seconds.")
    return rag_engine

# ---------------------------------------------------------
# 2. CORE UI & UTILITY ROUTES
# ---------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Main entrance point for the web application."""
    with open("static/index.html", "r") as f:
        return f.read()

@app.get("/health")
async def health():
    return {"status": "online"}

@app.get("/models")
async def list_models():
    return {"models": AVAILABLE_MODELS}

@app.post("/models/change")
async def switch_llm(model_id: str = Form(...), engine: RAGEngine = Depends(get_engine)):
    """Dynamically switch the underlying LLM model (e.g., Llama 3 -> Mixtral)."""
    engine.change_model(model_id)
    return {"status": "success", "message": f"Switched to {model_id}"}

# ---------------------------------------------------------
# 3. AUTHENTICATION (User Management)
# ---------------------------------------------------------

@app.post("/signup")
async def register(username: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(session_db.get_db)):
    if db.query(session_db.User).filter(session_db.User.username == username).first():
        return JSONResponse({"status": "error", "message": "Username taken"}, status_code=400)
    
    new_user = session_db.User(username=username, email=email, hashed_password=auth.get_password_hash(password))
    db.add(new_user)
    db.commit()
    return {"status": "success", "message": "Account created"}

@app.post("/login")
async def authenticate(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(session_db.get_db)):
    user = db.query(session_db.User).filter(session_db.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

# ---------------------------------------------------------
# 4. DATA OPS (Document Processing)
# ---------------------------------------------------------

@app.get("/documents")
async def list_files(engine: RAGEngine = Depends(get_engine)):
    return {"documents": engine.list_documents()}

@app.post("/process")
async def upload_document(file: UploadFile = File(...), engine: RAGEngine = Depends(get_engine), user: session_db.User = Depends(auth.get_current_user)):
    """Upload and index a document into the secure RAG knowledge base."""
    temp_file = f"temp_{file.filename}"
    try:
        with open(temp_file, "wb") as f:
            shutil.copyfileobj(file.file, f)
        engine.process_document(temp_file)
        return {"status": "success", "message": f"{file.filename} indexed successfully."}
    except Exception as e:
        logger.error(f"Index Error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        if os.path.exists(temp_file): os.remove(temp_file)

@app.get("/summarize/{filename}")
async def get_summary(filename: str, engine: RAGEngine = Depends(get_engine), user: session_db.User = Depends(auth.get_current_user)):
    return {"status": "success", "summary": engine.summarize_document(filename)}

@app.delete("/documents/{filename}")
async def remove_document(filename: str, engine: RAGEngine = Depends(get_engine), user: session_db.User = Depends(auth.get_current_user)):
    engine.delete_document(filename)
    return {"status": "success", "message": f"{filename} deleted."}

# ---------------------------------------------------------
# 5. CHAT ENGINE (Multi-turn RAG)
# ---------------------------------------------------------

@app.get("/sessions")
async def get_sessions(db: Session = Depends(session_db.get_db), user: session_db.User = Depends(auth.get_current_user)):
    sessions = db.query(session_db.ChatSession).filter(session_db.ChatSession.user_id == user.id).order_by(session_db.ChatSession.created_at.desc()).all()
    return {"sessions": [{"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()} for s in sessions]}

@app.post("/sessions")
async def start_session(db: Session = Depends(session_db.get_db), user: session_db.User = Depends(auth.get_current_user)):
    session = session_db.ChatSession(user_id=user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id, "title": session.title}

@app.get("/sessions/{session_id}/history")
async def get_history(session_id: str, db: Session = Depends(session_db.get_db), user: session_db.User = Depends(auth.get_current_user)):
    msgs = db.query(session_db.ChatMessage).filter(session_db.ChatMessage.session_id == session_id).order_by(session_db.ChatMessage.created_at.asc()).all()
    return {"messages": [{"role": m.role, "content": m.content} for m in msgs]}

@app.post("/chat")
async def chat_interaction(message: str = Form(...), session_id: str = Form(...), db: Session = Depends(session_db.get_db), engine: RAGEngine = Depends(get_engine), user: session_db.User = Depends(auth.get_current_user)):
    """Main RAG chat endpoint. Connects user input to document knowledge."""
    # 1. Verify access
    session = db.query(session_db.ChatSession).filter(session_db.ChatSession.id == session_id, session_db.ChatSession.user_id == user.id).first()
    if not session: raise HTTPException(status_code=404, detail="Session not found")
        
    # 2. Reconstruct chat history for the AI
    history_records = db.query(session_db.ChatMessage).filter(session_db.ChatMessage.session_id == session_id).order_by(session_db.ChatMessage.created_at.asc()).all()
    history = [HumanMessage(content=m.content) if m.role == 'user' else AIMessage(content=m.content) for m in history_records]
    
    # 3. Process with AI Engine
    try:
        result = engine.query(message, history)
    except Exception as e:
        logger.error(f"Chat Engine Error: {str(e)}")
        return JSONResponse({"status": "error", "message": f"AI Engine failed to process: {str(e)}"}, status_code=500)
    
    # 4. Save interactions to database
    db.add(session_db.ChatMessage(session_id=session_id, role='user', content=message))
    db.add(session_db.ChatMessage(session_id=session_id, role='assistant', content=result["answer"]))
    
    # Auto-title first message
    if session.title == "New Chat":
        session.title = message[:30] + "..." if len(message) > 30 else message
        
    db.commit()
    return {"status": "success", "response": result["answer"], "sources": result["sources"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)

    
