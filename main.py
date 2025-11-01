from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import asyncio

from database import get_db, ChatSession, ChatMessage, User
from session_manager import connection_manager, history_manager, queue_manager, SessionValidator, draft_manager
from ai_processor import processor
from action_handler import ActionHandler
from email_services import MockEmailService
from fastapi.responses import RedirectResponse

action_handler = None

app = FastAPI(
    title="Email AI Assistant API",
    description="AI-powered email management assistant with text chat",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    print("🚀 Starting Email AI Assistant...")
    
    # ✅ Email service ve action handler'ı initialize et
    global action_handler
    email_service = MockEmailService(delay=0.3)  # 0.3 saniye gecikme simülasyonu
    action_handler = ActionHandler(
        email_service=email_service,
        debug=True  # Production'da False yapılabilir
    )
    print("✅ Action Handler initialized with Mock Email Service")
    
    # Diğer startup kodları...
    queue_manager.start_processing(connection_manager)
    asyncio.create_task(connection_manager.cleanup_inactive_sessions(timeout_minutes=30))
    
    async def daily_cleanup():
        while True:
            await asyncio.sleep(86400)
            deleted_messages = history_manager.delete_old_messages(days=30)
            deleted_sessions = SessionValidator.cleanup_old_sessions(days=7)
            print(f"🧹 Daily Cleanup: {deleted_messages} messages, {deleted_sessions} sessions")
    
    asyncio.create_task(daily_cleanup())
    print("✅ All background tasks started")

@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 Shutting down...")
    queue_manager.stop_processing()
    print("✅ Shutdown complete")

@app.get("/")
def read_root():
    return {
        "message": "Email AI Assistant API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "websocket": "/ws/chat/{session_token}",
            "create_session": "POST /api/session/create",
            "chat_history": "GET /api/chat/history/{session_token}",
            "test_interface": "GET /test-chat"
        }
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(connection_manager.get_active_sessions()),
        "queue_size": queue_manager.get_queue_size()
    }

@app.post("/api/session/create")
def create_session(user_id: int = 1, db: Session = Depends(get_db)):
    try:
        session_token = secrets.token_urlsafe(32)
        new_session = ChatSession(
            user_id=user_id,
            session_token=session_token,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            is_active=True
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return {
            "success": True,
            "session_token": session_token,
            "session_id": new_session.id,
            "created_at": new_session.created_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@app.get("/api/chat/history/{session_token}")
def get_chat_history(session_token: str, limit: int = 50, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(
        ChatSession.session_token == session_token
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = history_manager.get_chat_history(session.id, limit)
    
    return {
        "success": True,
        "session_token": session_token,
        "message_count": len(messages),
        "messages": [
            {
                "id": msg["id"],
                "sender": msg["sender"],
                "message": msg["message"],
                "timestamp": msg["timestamp"].isoformat() if isinstance(msg["timestamp"], datetime) else msg["timestamp"],
                "type": msg["message_type"]
            }
            for msg in messages
        ]
    }

@app.get("/api/session/status/{session_token}")
def get_session_status(session_token: str, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(
        ChatSession.session_token == session_token
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    unread_count = history_manager.get_unread_count(session.id)
    is_connected = connection_manager.is_connected(session_token)
    is_valid = SessionValidator.is_session_valid(session)
    
    return {
        "success": True,
        "session_token": session_token,
        "is_active": session.is_active,
        "is_valid": is_valid,
        "is_connected": is_connected,
        "last_activity": session.last_activity.isoformat(),
        "unread_count": unread_count
    }

@app.websocket("/ws/chat/{session_token}")
async def websocket_endpoint(websocket: WebSocket, session_token: str, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(
        ChatSession.session_token == session_token
    ).first()
    
    if not session:
        await websocket.close(code=4004, reason="Invalid session token")
        return
    
    if not SessionValidator.is_session_valid(session):
        await websocket.close(code=4003, reason="Session expired")
        return
    
    await connection_manager.connect(websocket, session_token)
    
    try:
        welcome_message = {
            "type": "system",
            "message": "Connected! I'm your Email Assistant. How can I help you today?",
            "timestamp": datetime.utcnow().isoformat()
        }
        await connection_manager.send_personal_message(welcome_message, session_token)
        
        history = history_manager.get_chat_history(session.id, limit=10)
        if history:
            history_message = {
                "type": "history",
                "messages": [
                    {
                        "sender": msg["sender"],
                        "message": msg["message"],
                        "timestamp": msg["timestamp"].isoformat() if isinstance(msg["timestamp"], datetime) else msg["timestamp"]
                    }
                    for msg in history
                ]
            }
            await connection_manager.send_personal_message(history_message, session_token)
        
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type", "message")
            
            if message_type == "message":
                user_message = data.get("message", "").strip()
                if not user_message:
                    continue
                
                # Kullanıcı mesajını kaydet
                history_manager.save_message(
                    session_id=session.id,
                    sender="user",
                    message=user_message,
                    message_type="text"
                )
                
                # Session güncelle
                session.last_activity = datetime.utcnow()
                db.commit()
                
                # Typing indicator başlat
                await connection_manager.send_typing_indicator(session_token, True)
                await asyncio.sleep(0.5)
                
                # AI'dan cevap al
                ai_response = processor.process_command(user_message, session_id=session.id)
                response_text = ai_response['response']
                
                # AI cevabını kaydet
                history_manager.save_message(
                    session_id=session.id,
                    sender="assistant",
                    message=response_text,
                    message_type="text"
                )
                
                # Action varsa çalıştır
                action = ai_response.get('action', {})
                action_result = None
                
                if action.get('type') != 'chat_only':
                    try:
                        # ✅ Update draft için session_id ekle
                        if action.get('type') == 'update_draft':
                            action['params']['session_id'] = session.id
                        
                        # Action'ı çalıştır
                        action_result = await action_handler.execute_action(action)
                        
                        # ✅ Draft oluşturulduysa Draft Manager'a kaydet
                        if action.get('type') == 'draft_email' and action_result.get('success'):
                            draft_data = action_result.get('draft_data')
                            if draft_data:
                                draft_manager.save_draft(session.id, draft_data)
                                print(f"📝 Draft saved to Draft Manager (session: {session.id})")
                        
                        # ✅ Draft güncellendiyse Draft Manager'ı güncelle
                        if action.get('type') == 'update_draft' and action_result.get('success'):
                            # Draft Manager zaten _update_draft içinde güncelleniyor
                            print(f"📝 Draft updated in Draft Manager (session: {session.id})")
                        
                        # ✅ DÜZELTME: Sonucu kullanıcıya bildir (sadece email işlemleri için)
                        if action_result.get('success') and action_result.get('action_performed'):
                            action_type = action.get('type')
                            
                            # Sadece email listesi gibi data içeren actionlar için result gönder
                            if action_type in ['fetch_emails', 'move_emails', 'delete_emails']:
                                result_msg = {
                                    "type": "action_result",
                                    "message": action_result['message'],
                                    "data": action_result,
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                                await connection_manager.send_personal_message(result_msg, session_token)
                            
                            # Draft işlemleri için sadece log (mesaj gönderme, AI mesajı zaten draft preview ile geliyor)
                            elif action_type in ['draft_email', 'update_draft']:
                                print(f"✅ {action_type} completed, draft will be shown in AI message")
                        
                    except Exception as e:
                        print(f"❌ Action execution error: {e}")
                        error_msg = {
                            "type": "action_error",
                            "message": f"⚠️ Action failed: {str(e)}",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        await connection_manager.send_personal_message(error_msg, session_token)
                
                # Typing indicator durdur
                await connection_manager.send_typing_indicator(session_token, False)
                
                # AI cevabını gönder (Draft data ile)
                ai_message = {
                    "type": "message",
                    "sender": "assistant",
                    "message": response_text,
                    "timestamp": datetime.utcnow().isoformat(),
                    "intent": ai_response.get('intent'),
                    "action_performed": action_result is not None and action_result.get('action_performed', False),
                    # Draft data ekle
                    "draft_data": action_result.get('draft_data') if action_result else None,
                    "expandable": action_result.get('draft_data') is not None if action_result else False
                }
                await connection_manager.send_personal_message(ai_message, session_token)
            
            elif message_type == "ping":
                pong_message = {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }
                await connection_manager.send_personal_message(pong_message, session_token)
    
    except WebSocketDisconnect:
        connection_manager.disconnect(session_token)
        print(f"Client disconnected: {session_token[:8]}...")
    except Exception as e:
        print(f"Error in websocket: {e}")
        connection_manager.disconnect(session_token)
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass

@app.get("/test-chat")
def get_chat_page():
    return RedirectResponse(url="/static/chat.html")