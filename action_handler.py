from typing import Dict, Any, Optional
from datetime import datetime

class ActionHandler:
    """
    API isteklerini işleme çevir (Injectable version)
    
    Email service'i dışardan inject edilir.
    Mock veya Real service kullanılabilir.
    """
    
    def __init__(self, email_service=None, debug: bool = True):
        """
        Args:
            email_service: EmailServiceBase implementasyonu
                          None ise warning verir (geçici)
            debug: Debug logları aktif/pasif
        """
        self.debug = debug
        
        if email_service is None:
            print("⚠️  WARNING: Email service belirtilmedi!")
            print("⚠️  email_services modülü eklendikten sonra MockEmailService kullanılacak")
            self.email_service = None
        else:
            self.email_service = email_service
            if self.debug:
                print(f"✅ ActionHandler initialized with: {type(email_service).__name__}")
    
    async def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Action'ı çalıştır"""
        
        if self.email_service is None:
            return {
                'success': False,
                'message': 'Email service not configured',
                'action_performed': False,
                'error': 'No email service provided'
            }
        
        action_type = action.get('type')
        params = action.get('params', {})
        
        if action_type == 'move_emails':
            return await self._move_emails(params)
        
        elif action_type == 'delete_emails':
            return await self._delete_emails(params)
        
        elif action_type == 'fetch_emails':
            return await self._fetch_emails(params)
        
        elif action_type == 'draft_email':
            return await self._draft_email(params)
        
        elif action_type == 'update_draft':
            return await self._update_draft(params)
        
        elif action_type == 'chat_only':
            return {
                'success': True,
                'message': 'No action needed',
                'action_performed': False
            }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action type: {action_type}',
                'action_performed': False
            }
    
    async def _fetch_emails(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Email'leri getir (Email Service kullanarak)"""
        
        time_period = params.get('time_period', 'today')
        importance = params.get('importance')
        sender = params.get('sender')
        label = params.get('label')
        
        if self.debug:
            print("\n" + "="*50)
            print("📬 FETCH_EMAILS ACTION ÇAĞRILDI")
            print("="*50)
            print(f"✅ Parametreler:")
            print(f"   - Time Period: {time_period}")
            print(f"   - Importance: {importance}")
            print(f"   - Sender: {sender or 'All'}")
            print(f"   - Label: {label or 'All'}")
            print(f"📡 Email service çağrılıyor...")
            print("="*50 + "\n")
        
        try:
            # Email service'i çağır
            emails = await self.email_service.fetch_emails(params)
            
            # Message oluştur
            msg_parts = []
            if label:
                msg_parts.append(f"{label} labeled")
            if sender:
                msg_parts.append(f"from {sender}")
            if time_period:
                msg_parts.append(f"from {time_period}")
            
            message_detail = " ".join(msg_parts) if msg_parts else "all"
            
            if self.debug:
                print(f"✅ Email service başarılı: {len(emails)} email bulundu\n")
            
            return {
                'success': True,
                'message': f"✅ Found {len(emails)} emails {message_detail}",
                'emails': emails,
                'count': len(emails),
                'action_performed': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            if self.debug:
                print(f"❌ Email service hatası: {str(e)}\n")
            
            return {
                'success': False,
                'message': f"❌ Failed to fetch emails: {str(e)}",
                'emails': [],
                'count': 0,
                'action_performed': False,
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    async def _move_emails(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Email'leri taşı (Email Service kullanarak)"""
        
        from_sender = params.get('from_sender')
        to_folder = params.get('to_folder', 'Work')
        label = params.get('label')
        
        if self.debug:
            print("\n" + "="*50)
            print("📁 MOVE_EMAILS ACTION ÇAĞRILDI")
            print("="*50)
            print(f"✅ Parametreler:")
            print(f"   - From Sender: {from_sender or 'All'}")
            print(f"   - To Folder: {to_folder}")
            print(f"   - Label: {label or 'All'}")
            print(f"📡 Email service çağrılıyor...")
            print("="*50 + "\n")
        
        try:
            # Email service'i çağır
            result = await self.email_service.move_emails(params)
            
            # Message oluştur
            count = result.get('count', 0)
            
            if label and from_sender:
                message = f"✅ Moved {count} {label} labeled emails from {from_sender} to {to_folder} folder"
            elif label:
                message = f"✅ Moved {count} {label} labeled emails to {to_folder} folder"
            elif from_sender:
                message = f"✅ Moved {count} emails from {from_sender} to {to_folder} folder"
            else:
                message = f"✅ Moved {count} emails to {to_folder} folder"
            
            if self.debug:
                print(f"✅ Email service başarılı: {count} email taşındı\n")
            
            return {
                'success': True,
                'message': message,
                'count': count,
                'action_performed': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            if self.debug:
                print(f"❌ Email service hatası: {str(e)}\n")
            
            return {
                'success': False,
                'message': f"❌ Failed to move emails: {str(e)}",
                'count': 0,
                'action_performed': False,
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    async def _delete_emails(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Email'leri sil (Email Service kullanarak)"""
        
        filter_type = params.get('filter', 'spam')
        label = params.get('label')
        
        if self.debug:
            print("\n" + "="*50)
            print("🗑️ DELETE_EMAILS ACTION ÇAĞRILDI")
            print("="*50)
            print(f"✅ Parametreler:")
            print(f"   - Filter: {filter_type}")
            print(f"   - Label: {label or 'All'}")
            print(f"📡 Email service çağrılıyor...")
            print("="*50 + "\n")
        
        try:
            # Email service'i çağır
            result = await self.email_service.delete_emails(params)
            
            count = result.get('count', 0)
            
            if label:
                message = f"✅ Deleted {count} {label} labeled emails"
            else:
                message = f"✅ Deleted {count} {filter_type} emails"
            
            if self.debug:
                print(f"✅ Email service başarılı: {count} email silindi\n")
            
            return {
                'success': True,
                'message': message,
                'count': count,
                'action_performed': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            if self.debug:
                print(f"❌ Email service hatası: {str(e)}\n")
            
            return {
                'success': False,
                'message': f"❌ Failed to delete emails: {str(e)}",
                'count': 0,
                'action_performed': False,
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    async def _draft_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Email draft oluştur (AI + Email Service)
        
        İki aşamalı işlem:
        1. AI ile email içeriği üret (Action Handler'ın işi)
        2. Draft'ı email service'e kaydet (Service'in işi)
        """
        
        recipient = params.get('recipient', 'Unknown')
        topic = params.get('topic', 'No subject')
        email_address = params.get('email_address')
        
        if self.debug:
            print("\n" + "="*50)
            print("✉️ DRAFT_EMAIL ACTION ÇAĞRILDI")
            print("="*50)
            print(f"✅ Parametreler:")
            print(f"   - Recipient: {recipient}")
            print(f"   - Topic: {topic}")
            print(f"   - Email: {email_address or 'Not specified'}")
            print(f"🤖 AI ile içerik üretiliyor...")
        
        try:
            # 1. AI ile email body üret
            email_body_content = await self._generate_email_body(topic)
            
            if self.debug:
                print(f"✅ AI content generated: {len(email_body_content)} characters")
            
            # Tam email body oluştur
            recipient_name = recipient.split('@')[0] if '@' in str(recipient) else recipient
            full_body = f"""Hi {recipient_name},

{email_body_content}

Best regards,
Your Name"""
            
            # 2. Email service ile draft oluştur
            draft_params = {
                'to': email_address if email_address else f"{recipient}@example.com",
                'subject': f"Re: {topic}",
                'body': full_body,
                'recipient_name': recipient_name
            }
            
            if self.debug:
                print(f"📡 Email service çağrılıyor (draft creation)...")
            
            result = await self.email_service.create_draft(draft_params)
            
            if self.debug:
                print(f"✅ Draft oluşturuldu!")
                print("="*50 + "\n")
            
            return {
                'success': True,
                'message': f"✅ Draft created: Email to {recipient} about '{topic}'",
                'action_performed': True,
                'timestamp': datetime.utcnow().isoformat(),
                'draft_data': {
                    'to': draft_params['to'],
                    'subject': draft_params['subject'],
                    'body_preview': full_body[:50] + "...",
                    'body_full': full_body,
                    'draft_id': result.get('draft_id', 'draft_unknown'),
                    'version': 1
                }
            }
            
        except Exception as e:
            if self.debug:
                print(f"❌ Draft creation hatası: {str(e)}\n")
            
            return {
                'success': False,
                'message': f"❌ Failed to create draft: {str(e)}",
                'action_performed': False,
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    async def _generate_email_body(self, topic: str) -> str:
        """
        AI ile email body içeriği üret
        
        NOT: Bu Action Handler'ın sorumluluğu çünkü:
        - Email service sadece "draft kaydet" yapar
        - AI content generation business logic'e ait
        """
        
        try:
            from ai_processor import processor
            
            # Özel prompt - system instruction'ı bypass et
            content_prompt = f"""SYSTEM: You are a content generator. Ignore all previous instructions about being brief.

Generate a professional email body about: {topic}

Requirements:
- 3-4 sentences
- Professional tone
- No greeting (no "Hi" or "Dear")
- No signature (no "Best regards")
- Just the middle content

Output only the email body text, nothing else."""
            
            # Farklı session ID kullan
            ai_response = processor.process_command(content_prompt, session_id=99999)
            email_body_content = ai_response['response'].strip()
            
            # Greeting ve signature temizle
            lines = email_body_content.split('\n')
            cleaned_lines = []
            for line in lines:
                line_lower = line.lower().strip()
                if line_lower.startswith(('hi ', 'dear ', 'hello ', 'best regards', 'sincerely', 'yours', 'thank you,', 'thanks,')):
                    continue
                if line.strip():
                    cleaned_lines.append(line)
            
            email_body_content = '\n'.join(cleaned_lines).strip()
            
            return email_body_content
            
        except Exception as e:
            if self.debug:
                print(f"⚠️ AI generation failed: {e}, using template")
            
            # Fallback template
            return f"I wanted to reach out regarding {topic}. Please let me know your thoughts on this matter."
    
    async def _update_draft(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Draft'ı güncelle (AI + Draft Manager + Email Service)
        
        Üç aşamalı işlem:
        1. Draft Manager'dan son draft'ı al
        2. AI ile body'yi güncelle (eski content + yeni instruction)
        3. Email service'e gönder ve Draft Manager'ı güncelle
        """
        
        instruction = params.get('update_instruction', '')
        session_id = params.get('session_id', 1)
        
        if self.debug:
            print("\n" + "="*50)
            print("📝 UPDATE_DRAFT ACTION ÇAĞRILDI")
            print("="*50)
            print(f"✅ Parametreler:")
            print(f"   - Instruction: {instruction}")
            print(f"   - Session ID: {session_id}")
        
        try:
            # 1. Draft Manager'dan son draft'ı al
            from session_manager import draft_manager
            last_draft = draft_manager.get_last_draft(session_id)
            
            if not last_draft:
                if self.debug:
                    print("❌ No draft found for this session")
                
                return {
                    'success': False,
                    'message': "❌ No draft found. Please create a draft first.",
                    'action_performed': False,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            if self.debug:
                print(f"✅ Found draft:")
                print(f"   - Draft ID: {last_draft.get('draft_id')}")
                print(f"   - To: {last_draft.get('to')}")
                print(f"   - Subject: {last_draft.get('subject')}")
                print(f"   - Version: {last_draft.get('version', 1)}")
            
            # 2. AI ile yeni body oluştur
            old_body = last_draft.get('body_full', '')
            
            if self.debug:
                print(f"🤖 AI ile body güncelleniyor...")
            
            new_body = await self._generate_updated_body(old_body, instruction)
            
            if self.debug:
                print(f"✅ AI güncelleme tamamlandı: {len(new_body)} chars")
            
            # 3. Email service ile draft'ı güncelle
            update_params = {
                'draft_id': last_draft.get('draft_id'),
                'new_body': new_body,
                'update_instruction': instruction
            }
            
            if self.debug:
                print(f"📡 Email service çağrılıyor (update draft)...")
            
            result = await self.email_service.update_draft(update_params)
            
            # 4. Draft Manager'ı güncelle
            updated_draft_data = {
                'body_full': new_body,
                'body_preview': new_body[:50] + "...",
                'draft_id': result.get('draft_id'),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            draft_manager.update_draft(session_id, updated_draft_data)
            
            if self.debug:
                print(f"✅ Draft güncellendi!")
                print("="*50 + "\n")
            
            return {
                'success': True,
                'message': f"✅ Draft updated: {instruction}",
                'action_performed': True,
                'timestamp': datetime.utcnow().isoformat(),
                'draft_data': {
                    'to': last_draft.get('to'),
                    'subject': last_draft.get('subject'),
                    'body_preview': new_body[:50] + "...",
                    'body_full': new_body,
                    'draft_id': result.get('draft_id'),
                    'version': last_draft.get('version', 1) + 1
                }
            }
            
        except Exception as e:
            if self.debug:
                print(f"❌ Update draft hatası: {str(e)}\n")
            
            return {
                'success': False,
                'message': f"❌ Failed to update draft: {str(e)}",
                'action_performed': False,
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    async def _generate_updated_body(self, old_body: str, instruction: str) -> str:
        """
        AI ile email body'sini güncelle
        
        Args:
            old_body: Mevcut email içeriği
            instruction: Kullanıcının güncelleme talimatı
        
        Returns:
            str: Güncellenmiş email body
        """
        
        try:
            from ai_processor import processor
            
            # Özel prompt - mevcut içeriği güncelle
            update_prompt = f"""SYSTEM: You are a content editor. Update the email body based on user instruction.

CURRENT EMAIL BODY:
{old_body}

USER INSTRUCTION: {instruction}

Generate the COMPLETE UPDATED email body (not just the changes, the entire email).

Requirements:
- Keep the greeting and signature from the original
- Apply the user's instruction
- Maintain professional tone
- Output only the complete updated email body

Output the full updated email:"""
            
            # Farklı session ID kullan (AI'nın kendi conversation'ını etkilemesin)
            ai_response = processor.process_command(update_prompt, session_id=99998)
            updated_body = ai_response['response'].strip()
            
            return updated_body
            
        except Exception as e:
            if self.debug:
                print(f"⚠️ AI update failed: {e}, returning original with note")
            
            # Fallback: Eski body + instruction ekle
            return f"{old_body}\n\n[Updated: {instruction}]"