from fastapi import WebSocket
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from contextlib import contextmanager
import asyncio
import json
from collections import defaultdict
from database import ChatSession, ChatMessage, SessionLocal

class ConnectionManager:
    """WebSocket bağlantılarını yönetir"""
    
    def __init__(self, max_history_per_session: int = 100):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_sessions: Dict[str, str] = {}
        self.typing_status: Dict[str, bool] = {}
        self.session_metadata: Dict[str, dict] = {}
        self.max_history = max_history_per_session
        
    async def connect(self, websocket: WebSocket, session_token: str):
        """Yeni WebSocket bağlantısı kur"""
        await websocket.accept()
        self.active_connections[session_token] = websocket
        self.session_metadata[session_token] = {
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "message_count": 0
        }
        print(f"✅ Client connected: {session_token[:8]}...")
        
    def disconnect(self, session_token: str):
        """WebSocket bağlantısını kapat ve temizle"""
        if session_token in self.active_connections:
            del self.active_connections[session_token]
        if session_token in self.typing_status:
            del self.typing_status[session_token]
        if session_token in self.session_metadata:
            del self.session_metadata[session_token]
        print(f"❌ Client disconnected: {session_token[:8]}...")
    
    def update_activity(self, session_token: str):
        """Son aktivite zamanını güncelle"""
        if session_token in self.session_metadata:
            self.session_metadata[session_token]["last_activity"] = datetime.utcnow()
            self.session_metadata[session_token]["message_count"] += 1
    
    async def send_personal_message(self, message: dict, session_token: str):
        """Belirli bir istemciye mesaj gönder"""
        if session_token in self.active_connections:
            try:
                websocket = self.active_connections[session_token]
                await websocket.send_json(message)
                self.update_activity(session_token)
            except Exception as e:
                print(f"❌ Error sending message to {session_token[:8]}: {e}")
                self.disconnect(session_token)
    
    async def send_typing_indicator(self, session_token: str, is_typing: bool):
        """Yazıyor göstergesi gönder"""
        self.typing_status[session_token] = is_typing
        message = {
            "type": "typing",
            "is_typing": is_typing,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_personal_message(message, session_token)
    
    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        """Tüm bağlı istemcilere mesaj gönder"""
        disconnected = []
        
        for token, connection in self.active_connections.items():
            if token == exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"❌ Broadcast error to {token[:8]}: {e}")
                disconnected.append(token)
        
        # Bağlantısı kopanları temizle
        for token in disconnected:
            self.disconnect(token)
    
    def get_active_sessions(self) -> List[Dict]:
        """Aktif session listesi döndür"""
        return [
            {
                "token": token[:8] + "...",
                "connected_at": meta["connected_at"].isoformat(),
                "message_count": meta["message_count"]
            }
            for token, meta in self.session_metadata.items()
        ]
    
    def is_connected(self, session_token: str) -> bool:
        """Session bağlı mı kontrol et"""
        return session_token in self.active_connections
    
    async def cleanup_inactive_sessions(self, timeout_minutes: int = 30):
        """Inactive session'ları temizle (background task)"""
        while True:
            await asyncio.sleep(300)  # Her 5 dakikada bir
            
            now = datetime.utcnow()
            timeout = timedelta(minutes=timeout_minutes)
            
            inactive = [
                token for token, meta in self.session_metadata.items()
                if now - meta["last_activity"] > timeout
            ]
            
            for token in inactive:
                print(f"🧹 Cleaning up inactive session: {token[:8]}...")
                if token in self.active_connections:
                    try:
                        await self.active_connections[token].close()
                    except:
                        pass
                self.disconnect(token)

class ChatHistoryManager:
    """Chat geçmişini yönetir"""
    
    @contextmanager
    def get_db_session(self):
        """Güvenli database session context manager"""
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"❌ Database error: {e}")
            raise
        finally:
            db.close()
    
    def save_message(self, session_id: int, sender: str, message: str, 
                    message_type: str = "text") -> Optional[dict]:
        """Mesajı veritabanına kaydet"""
        with self.get_db_session() as db:
            chat_message = ChatMessage(
                session_id=session_id,
                sender=sender,
                message=message,
                message_type=message_type,
                timestamp=datetime.utcnow(),
                is_read=False
            )
            db.add(chat_message)
            db.flush()
            db.refresh(chat_message)
            
            return self._message_to_dict(chat_message)
    
    def get_chat_history(self, session_id: int, limit: int = 50) -> List[dict]:
        """Session'ın chat geçmişini getir"""
        with self.get_db_session() as db:
            messages = db.query(ChatMessage)\
                .filter(ChatMessage.session_id == session_id)\
                .order_by(ChatMessage.timestamp.desc())\
                .limit(limit)\
                .all()
            
            # Reversed for chronological order
            return [self._message_to_dict(msg) for msg in reversed(messages)]
    
    def mark_messages_as_read(self, session_id: int):
        """Tüm mesajları okundu olarak işaretle"""
        with self.get_db_session() as db:
            db.query(ChatMessage)\
                .filter(ChatMessage.session_id == session_id)\
                .update({"is_read": True})
    
    def get_unread_count(self, session_id: int) -> int:
        """Okunmamış mesaj sayısı"""
        with self.get_db_session() as db:
            return db.query(ChatMessage)\
                .filter(ChatMessage.session_id == session_id)\
                .filter(ChatMessage.is_read == False)\
                .count()
    
    def delete_old_messages(self, days: int = 30) -> int:
        """Eski mesajları sil"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        with self.get_db_session() as db:
            deleted = db.query(ChatMessage)\
                .filter(ChatMessage.timestamp < cutoff)\
                .delete()
            return deleted
    
    @staticmethod
    def _message_to_dict(msg: ChatMessage) -> dict:
        """ChatMessage'ı dict'e çevir"""
        return {
            "id": msg.id,
            "sender": msg.sender,
            "message": msg.message,
            "timestamp": msg.timestamp,
            "message_type": msg.message_type,
            "is_read": msg.is_read
        }

class MessageQueueManager:
    """Mesaj kuyruğunu yönetir"""
    
    def __init__(self, max_queue_size: int = 1000, max_requests_per_minute: int = 20):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.processing = False
        self.processing_task: Optional[asyncio.Task] = None
        self.rate_limiter: Dict[str, List[float]] = defaultdict(list)
        self.max_requests_per_minute = max_requests_per_minute
    
    async def add_to_queue(self, session_token: str, message: dict, priority: int = 0):
        """Kuyruğa mesaj ekle (rate limiting ile)"""
        
        # Rate limit kontrolü
        if not self._check_rate_limit(session_token):
            raise Exception(f"Rate limit exceeded for session {session_token[:8]}")
        
        try:
            await asyncio.wait_for(
                self.queue.put({
                    "session_token": session_token,
                    "message": message,
                    "priority": priority,
                    "timestamp": datetime.utcnow().isoformat()
                }),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            raise Exception("Message queue is full. Please try again later.")
    
    def _check_rate_limit(self, session_token: str) -> bool:
        """Rate limit kontrolü yap"""
        now = datetime.utcnow().timestamp()
        minute_ago = now - 60
        
        # Son 1 dakikadaki requestleri filtrele
        self.rate_limiter[session_token] = [
            ts for ts in self.rate_limiter[session_token] 
            if ts > minute_ago
        ]
        
        # Limit aşıldı mı?
        if len(self.rate_limiter[session_token]) >= self.max_requests_per_minute:
            return False
        
        self.rate_limiter[session_token].append(now)
        return True
    
    async def process_queue(self, connection_manager: ConnectionManager):
        """Kuyruktan mesajları işle"""
        self.processing = True
        
        while self.processing:
            try:
                if not self.queue.empty():
                    item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                    session_token = item["session_token"]
                    
                    # Bağlantı hala aktif mi?
                    if not connection_manager.is_connected(session_token):
                        print(f"⏭️  Skipping message for disconnected session")
                        self.queue.task_done()
                        continue
                    
                    try:
                        # Typing indicator başlat
                        await connection_manager.send_typing_indicator(session_token, True)
                        
                        # İşleme simülasyonu (gerçekte AI processing)
                        await asyncio.sleep(0.5)
                        
                        # Typing indicator durdur
                        await connection_manager.send_typing_indicator(session_token, False)
                        
                    except Exception as e:
                        print(f"❌ Error processing message: {e}")
                    finally:
                        self.queue.task_done()
                else:
                    await asyncio.sleep(0.1)
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"❌ Queue processing error: {e}")
                await asyncio.sleep(1)
    
    def start_processing(self, connection_manager: ConnectionManager):
        """Background queue processing başlat"""
        if not self.processing_task or self.processing_task.done():
            self.processing_task = asyncio.create_task(
                self.process_queue(connection_manager)
            )
    
    def stop_processing(self):
        """Queue processing'i durdur"""
        self.processing = False
        if self.processing_task:
            self.processing_task.cancel()
    
    def get_queue_size(self) -> int:
        """Mevcut kuyruk boyutu"""
        return self.queue.qsize()

class SessionValidator:
    """Session geçerliliğini kontrol eder"""
    
    @staticmethod
    def is_session_valid(session: ChatSession, max_inactivity_hours: int = 24) -> bool:
        """Session hala geçerli mi?"""
        if not session.is_active:
            return False
        
        inactivity = datetime.utcnow() - session.last_activity
        if inactivity.total_seconds() > max_inactivity_hours * 3600:
            return False
        
        return True
    
    @staticmethod
    def cleanup_old_sessions(days: int = 7) -> int:
        """Eski session'ları temizle"""
        db = SessionLocal()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            old_sessions = db.query(ChatSession).filter(
                ChatSession.last_activity < cutoff_date
            ).all()
            
            count = 0
            for session in old_sessions:
                # İlişkili mesajları sil
                db.query(ChatMessage).filter(
                    ChatMessage.session_id == session.id
                ).delete()
                
                db.delete(session)
                count += 1
            
            db.commit()
            return count
        except Exception as e:
            db.rollback()
            print(f"❌ Cleanup error: {e}")
            return 0
        finally:
            db.close()

class DraftManager:
    """
    Session bazında draft'ları yönetir (In-Memory)
    
    Hybrid approach:
    - Memory'de hızlı erişim için son draft
    - İleride database'e kolayca taşınabilir
    """
    
    def __init__(self, max_drafts_per_session: int = 10):
        """
        Args:
            max_drafts_per_session: Her session için max draft history
        """
        # session_id -> latest draft mapping (hızlı erişim)
        self.session_drafts: Dict[int, Dict[str, Any]] = {}
        
        # session_id -> draft history (isteğe bağlı)
        self.draft_history: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        
        self.max_drafts_per_session = max_drafts_per_session
        
        print("✅ DraftManager initialized")
    
    def save_draft(self, session_id: int, draft_data: Dict[str, Any]) -> bool:
        """
        Yeni draft kaydet
        
        Args:
            session_id: Session ID
            draft_data: Draft verisi (to, subject, body, draft_id, timestamp)
        
        Returns:
            bool: Başarılı mı?
        """
        try:
            # Timestamp ekle
            draft_data['saved_at'] = datetime.utcnow().isoformat()
            draft_data['version'] = self._get_next_version(session_id)
            
            # Son draft olarak kaydet
            self.session_drafts[session_id] = draft_data
            
            # History'ye ekle
            self.draft_history[session_id].append(draft_data.copy())
            
            # History limit kontrolü
            if len(self.draft_history[session_id]) > self.max_drafts_per_session:
                self.draft_history[session_id] = self.draft_history[session_id][-self.max_drafts_per_session:]
            
            print(f"📝 Draft saved for session {session_id} (version {draft_data['version']})")
            return True
            
        except Exception as e:
            print(f"❌ Error saving draft: {e}")
            return False
    
    def get_last_draft(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Session'ın son draft'ını getir
        
        Args:
            session_id: Session ID
        
        Returns:
            Dict veya None: Draft data
        """
        return self.session_drafts.get(session_id)
    
    def has_draft(self, session_id: int) -> bool:
        """Session'ın aktif draft'ı var mı?"""
        return session_id in self.session_drafts
    
    def update_draft(self, session_id: int, updated_data: Dict[str, Any]) -> bool:
        """
        Mevcut draft'ı güncelle
        
        Args:
            session_id: Session ID
            updated_data: Güncellenmiş draft verisi
        
        Returns:
            bool: Başarılı mı?
        """
        try:
            if not self.has_draft(session_id):
                print(f"⚠️ No draft found for session {session_id}")
                return False
            
            # Mevcut draft'ı al
            current_draft = self.session_drafts[session_id]
            
            # Güncelle
            current_draft.update(updated_data)
            current_draft['updated_at'] = datetime.utcnow().isoformat()
            current_draft['version'] = self._get_next_version(session_id)
            
            # History'ye yeni version ekle
            self.draft_history[session_id].append(current_draft.copy())
            
            print(f"✅ Draft updated for session {session_id} (version {current_draft['version']})")
            return True
            
        except Exception as e:
            print(f"❌ Error updating draft: {e}")
            return False
    
    def get_draft_history(self, session_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Session'ın draft history'sini getir
        
        Args:
            session_id: Session ID
            limit: Max kaç draft
        
        Returns:
            List[Dict]: Draft history (en yeniden eskiye)
        """
        history = self.draft_history.get(session_id, [])
        return list(reversed(history[-limit:]))
    
    def clear_session_drafts(self, session_id: int):
        """Session'ın tüm draft'larını temizle"""
        if session_id in self.session_drafts:
            del self.session_drafts[session_id]
        
        if session_id in self.draft_history:
            del self.draft_history[session_id]
        
        print(f"🧹 Cleared all drafts for session {session_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Draft istatistikleri"""
        return {
            'total_sessions_with_drafts': len(self.session_drafts),
            'total_drafts_in_history': sum(len(h) for h in self.draft_history.values()),
            'sessions': [
                {
                    'session_id': sid,
                    'draft_count': len(self.draft_history.get(sid, [])),
                    'last_draft_version': self.session_drafts[sid].get('version', 0)
                }
                for sid in self.session_drafts.keys()
            ]
        }
    
    def _get_next_version(self, session_id: int) -> int:
        """Session için sonraki version numarasını al"""
        history = self.draft_history.get(session_id, [])
        if not history:
            return 1
        return max(d.get('version', 0) for d in history) + 1

# Global instances
connection_manager = ConnectionManager()
history_manager = ChatHistoryManager()
queue_manager = MessageQueueManager()
draft_manager = DraftManager()