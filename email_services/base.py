"""
Email Service Base Interface

Tüm email servisleri bu interface'i implement etmelidir.
Bu sayede ActionHandler hangi servis kullanılırsa kullanılsın çalışır.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class EmailServiceBase(ABC):
    """
    Abstract Base Class for Email Services
    
    Tüm email servisleri (Gmail, Outlook, Mock, vb.) bu class'ı inherit etmelidir.
    """
    
    @abstractmethod
    async def fetch_emails(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Email'leri getir
        
        Args:
            params: {
                'time_period': str (optional) - 'today', 'yesterday', 'this_week'
                'importance': str (optional) - 'important', 'spam', 'normal'
                'sender': str (optional) - Gönderen adı veya email
                'label': str (optional) - 'Work', 'Personal', 'Promotions'
            }
        
        Returns:
            List[Dict]: Email listesi
            [
                {
                    'id': int,
                    'from': str,
                    'subject': str,
                    'preview': str,
                    'timestamp': str (ISO format),
                    'important': bool,
                    'label': str
                },
                ...
            ]
        
        Raises:
            Exception: Email fetch işlemi başarısız olursa
        """
        pass
    
    @abstractmethod
    async def move_emails(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Email'leri taşı
        
        Args:
            params: {
                'from_sender': str (optional) - Hangi gönderenden
                'to_folder': str - Hedef klasör
                'label': str (optional) - Label filtresi
            }
        
        Returns:
            Dict: {
                'count': int - Taşınan email sayısı
            }
        
        Raises:
            Exception: Move işlemi başarısız olursa
        """
        pass
    
    @abstractmethod
    async def delete_emails(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Email'leri sil
        
        Args:
            params: {
                'filter': str - 'spam', 'old', 'unread', vb.
                'label': str (optional) - Sadece bu label'dan sil
            }
        
        Returns:
            Dict: {
                'count': int - Silinen email sayısı
            }
        
        Raises:
            Exception: Delete işlemi başarısız olursa
        """
        pass
    
    @abstractmethod
    async def create_draft(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Email draft'ı oluştur
        
        Args:
            params: {
                'to': str - Alıcı email adresi
                'subject': str - Email konusu
                'body': str - Email içeriği (tam metin)
                'recipient_name': str - Alıcı adı
            }
        
        Returns:
            Dict: {
                'draft_id': str - Oluşturulan draft'ın ID'si
            }
        
        Raises:
            Exception: Draft oluşturma başarısız olursa
        """
        pass

@abstractmethod
async def update_draft(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mevcut draft'ın body'sini güncelle
    
    Args:
        params: {
            'draft_id': str - Güncellenecek draft'ın ID'si
            'new_body': str - Yeni email içeriği (tam metin)
            'update_instruction': str - Kullanıcının güncelleme talimatı (log için)
        }
    
    Returns:
        Dict: {
            'draft_id': str - Güncellenen draft'ın ID'si
            'success': bool - İşlem başarılı mı?
        }
    
    Raises:
        Exception: Update işlemi başarısız olursa
    """
    pass
    
    # İleride eklenebilecek metodlar:
    # - send_email()
    # - mark_as_read()
    # - mark_as_important()
    # - search_emails()
    # - get_email_by_id()