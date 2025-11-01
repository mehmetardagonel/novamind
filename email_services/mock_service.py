"""
Mock Email Service

Test ve development için kullanılır.
Gerçek API'ya bağlanmaz, sahte data döndürür.
"""

from typing import List, Dict, Any
from datetime import datetime
import asyncio
from .base import EmailServiceBase


class MockEmailService(EmailServiceBase):
    """
    Mock Email Service Implementation
    
    Gerçek email servisi gibi davranır ama mock data kullanır.
    Test ve development ortamları için idealdir.
    """
    
    def __init__(self, delay: float = 0.2):
        """
        Args:
            delay: API call simülasyonu için bekleme süresi (saniye)
        """
        self.delay = delay
        print("✅ MockEmailService initialized")
    
    async def fetch_emails(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Email'leri getir (MOCK)"""
        
        # API call simülasyonu
        await asyncio.sleep(self.delay)
        
        time_period = params.get('time_period', 'today')
        importance = params.get('importance')
        sender = params.get('sender')
        label = params.get('label')
        
        # Mock email database
        mock_emails = [
            {
                "id": 1,
                "from": "boss@company.com",
                "subject": "Important Meeting",
                "preview": "We need to discuss the project timeline...",
                "timestamp": "2025-10-20T10:30:00Z",
                "important": True,
                "label": "Work"
            },
            {
                "id": 2,
                "from": "team@company.com",
                "subject": "Weekly Update",
                "preview": "Here's what happened this week in our team...",
                "timestamp": "2025-10-20T09:15:00Z",
                "important": False,
                "label": "Work"
            },
            {
                "id": 3,
                "from": "notifications@service.com",
                "subject": "Your order has shipped",
                "preview": "Track your package using the link below...",
                "timestamp": "2025-10-20T08:00:00Z",
                "important": False,
                "label": "Promotions"
            },
            {
                "id": 4,
                "from": "mom@gmail.com",
                "subject": "Family Dinner",
                "preview": "Don't forget dinner on Sunday at 6 PM...",
                "timestamp": "2025-10-19T19:00:00Z",
                "important": True,
                "label": "Personal"
            },
            {
                "id": 5,
                "from": "spam@unknown.com",
                "subject": "You won a prize!",
                "preview": "Click here to claim your prize...",
                "timestamp": "2025-10-19T15:30:00Z",
                "important": False,
                "label": "Spam"
            },
            {
                "id": 6,
                "from": "hr@company.com",
                "subject": "Benefits Update",
                "preview": "Annual benefits enrollment is now open...",
                "timestamp": "2025-10-18T14:00:00Z",
                "important": True,
                "label": "Work"
            }
        ]
        
        # Filtering
        filtered_emails = mock_emails
        
        if importance == 'important':
            filtered_emails = [e for e in filtered_emails if e['important']]
        elif importance == 'spam':
            filtered_emails = [e for e in filtered_emails if e['label'] == 'Spam']
        
        if label:
            filtered_emails = [e for e in filtered_emails if e.get('label') == label]
        
        if sender:
            filtered_emails = [
                e for e in filtered_emails 
                if sender.lower() in e['from'].lower()
            ]
        
        # Time period filtering (basit versiyon)
        if time_period == 'today':
            # Son 2 email'i al (bugünkü gibi davransın)
            filtered_emails = filtered_emails[:2]
        elif time_period == 'yesterday':
            filtered_emails = filtered_emails[2:4]
        
        return filtered_emails
    
    async def move_emails(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Email'leri taşı (MOCK)"""
        
        await asyncio.sleep(self.delay)
        
        from_sender = params.get('from_sender')
        to_folder = params.get('to_folder', 'Work')
        label = params.get('label')
        
        # Mock: Rastgele sayıda email taşınmış gibi yap
        if label and from_sender:
            count = 5
        elif label:
            count = 8
        elif from_sender:
            count = 3
        else:
            count = 5
        
        return {'count': count}
    
    async def delete_emails(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Email'leri sil (MOCK)"""
        
        await asyncio.sleep(self.delay)
        
        filter_type = params.get('filter', 'spam')
        label = params.get('label')
        
        # Mock: Rastgele sayıda email silinmiş gibi yap
        if label:
            count = 7
        else:
            if filter_type == 'spam':
                count = 12
            elif filter_type == 'old':
                count = 25
            else:
                count = 3
        
        return {'count': count}
    
    async def create_draft(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Draft oluştur (MOCK)"""
        
        await asyncio.sleep(self.delay)
        
        to = params.get('to', 'unknown@example.com')
        subject = params.get('subject', 'No Subject')
        body = params.get('body', '')
        
        # Mock draft ID
        draft_id = f"draft_mock_{datetime.utcnow().timestamp()}"
        
        print(f"📧 [MOCK] Draft created:")
        print(f"   To: {to}")
        print(f"   Subject: {subject}")
        print(f"   Body length: {len(body)} chars")
        print(f"   Draft ID: {draft_id}")
        
        return {'draft_id': draft_id}
    
    async def update_draft(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Draft'ı güncelle (MOCK)"""
    
        await asyncio.sleep(self.delay)
    
        draft_id = params.get('draft_id', 'unknown')
        new_body = params.get('new_body', '')
        update_instruction = params.get('update_instruction', '')
    
        (f"📝 [MOCK] Draft updated:")
        print(f"   Draft ID: {draft_id}")
        print(f"   Instruction: {update_instruction}")
        print(f"   New body length: {len(new_body)} chars")
        print(f"   Preview: {new_body[:100]}...")
    
        return {
            'draft_id': draft_id,
            'success': True,
            'updated_at': datetime.utcnow().isoformat()
        }