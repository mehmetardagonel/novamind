"""
ML Service - Email Classification Integration
Wraps the ML classification model to work with the email backend
"""

import sys
import os
import logging
from typing import Dict, List, Optional

# Add ml_model directory to path
ml_model_path = os.path.join(os.path.dirname(__file__), 'ml_model')
sys.path.insert(0, ml_model_path)

from ml_model.classify import classify_email, classify_email_with_confidence

logger = logging.getLogger(__name__)


class EmailClassifier:
    """
    Wrapper for ML email classification model.
    Integrates with the existing email backend.
    """
    
    def __init__(self):
        """Initialize the classifier"""
        logger.info("🤖 Initializing ML Email Classifier...")
        logger.info("   ⏳ This may take a moment if downloading models for the first time")
        try:
            # Test the classifier on startup
            logger.info("   🔧 Testing classification with sample email...")
            test_result = classify_email("test email")
            logger.info(f"   ✅ Classification test passed: {test_result}")
            logger.info("✅ ML Classifier is ready!")
        except Exception as e:
            logger.error(f"❌ Failed to initialize ML classifier: {str(e)}", exc_info=True)
            raise
    
    def classify_single_email(self, email_data: Dict) -> Dict:
        """
        Classify a single email and add ML predictions to it.
        
        Args:
            email_data: Email dictionary with keys like:
                {
                    "id": "msg_123",
                    "sender": "someone@example.com",
                    "subject": "Meeting tomorrow",
                    "body": "Let's meet at 3pm...",
                    "date": "2025-01-15T10:30:00",
                    ...
                }
        
        Returns:
            Same email data with added ML fields:
                {
                    ...original fields...,
                    "ml_prediction": "ham" | "spam" | "important",
                    "ml_confidence": 0.95,
                    "ml_category": "work" | "personal" | "spam" | etc.
                }
        """
        # Copy original data
        result = email_data.copy()
        
        try:
            # Combine subject and body for classification
            subject = email_data.get('subject', '')
            body = email_data.get('body', '')
            email_text = f"{subject} {body}".strip()
            
            if not email_text:
                logger.warning(f"Empty email text for email {email_data.get('id')}")
                result['ml_prediction'] = 'unknown'
                result['ml_confidence'] = 0.0
                result['ml_category'] = 'uncategorized'
                return result
            
            # Get prediction with confidence
            ml_result = classify_email_with_confidence(email_text)
            
            # Add ML predictions to email data
            result['ml_prediction'] = ml_result['label']
            result['ml_confidence'] = round(ml_result['confidence'], 3)
            result['ml_category'] = self._map_to_category(ml_result['label'])
            
            logger.debug(
                f"Email {email_data.get('id')} classified as "
                f"{ml_result['label']} (confidence: {ml_result['confidence']:.2f})"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Classification error for email {email_data.get('id')}: {str(e)}")
            # Return original data with error indicators
            result['ml_prediction'] = 'error'
            result['ml_confidence'] = 0.0
            result['ml_category'] = 'error'
            result['ml_error'] = str(e)
            return result
    
    def classify_batch(self, emails: List[Dict]) -> List[Dict]:
        """
        Classify multiple emails in batch.
        
        Args:
            emails: List of email dictionaries
        
        Returns:
            List of emails with ML predictions added
        """
        if not emails:
            logger.warning("Empty email list provided for classification")
            return []
        
        logger.info(f"🔄 Classifying batch of {len(emails)} emails...")
        
        classified_emails = []
        success_count = 0
        error_count = 0
        
        for email in emails:
            classified_email = self.classify_single_email(email)
            classified_emails.append(classified_email)
            
            if classified_email.get('ml_prediction') != 'error':
                success_count += 1
            else:
                error_count += 1
        
        logger.info(
            f"✅ Batch classification complete: "
            f"{success_count} successful, {error_count} errors"
        )
        
        return classified_emails
    
    def get_classification_summary(self, classified_emails: List[Dict]) -> Dict:
        """
        Generate summary statistics from classified emails.
        
        Args:
            classified_emails: List of emails with ML predictions
        
        Returns:
            Dictionary with summary statistics:
            {
                "total": 50,
                "by_prediction": {"spam": 10, "ham": 35, "important": 5},
                "by_category": {"work": 20, "personal": 15, "spam": 10, ...},
                "avg_confidence": 0.85,
                "high_confidence_count": 40,  # confidence > 0.8
            }
        """
        if not classified_emails:
            return {
                "total": 0,
                "by_prediction": {},
                "by_category": {},
                "avg_confidence": 0.0,
                "high_confidence_count": 0
            }
        
        by_prediction = {}
        by_category = {}
        total_confidence = 0.0
        valid_count = 0
        high_confidence_count = 0
        
        for email in classified_emails:
            # Count by prediction
            pred = email.get('ml_prediction', 'unknown')
            by_prediction[pred] = by_prediction.get(pred, 0) + 1
            
            # Count by category
            cat = email.get('ml_category', 'uncategorized')
            by_category[cat] = by_category.get(cat, 0) + 1
            
            # Sum confidence scores
            conf = email.get('ml_confidence', 0.0)
            if isinstance(conf, (int, float)) and pred != 'error':
                total_confidence += conf
                valid_count += 1
                if conf > 0.8:
                    high_confidence_count += 1
        
        avg_confidence = total_confidence / valid_count if valid_count > 0 else 0.0
        
        return {
            "total": len(classified_emails),
            "by_prediction": by_prediction,
            "by_category": by_category,
            "avg_confidence": round(avg_confidence, 3),
            "high_confidence_count": high_confidence_count,
            "error_count": by_prediction.get('error', 0)
        }
    
    def _map_to_category(self, prediction: str) -> str:
        """
        Map ML prediction to user-friendly category.
        
        Args:
            prediction: 'spam', 'ham', or 'important'
        
        Returns:
            Category string
        """
        prediction_lower = str(prediction).lower()
        
        if prediction_lower == 'spam':
            return 'spam'
        elif prediction_lower == 'important':
            return 'important'
        elif prediction_lower == 'ham':
            return 'inbox'
        else:
            return 'uncategorized'
    
    def classify_text_only(self, text: str) -> Dict:
        """
        Classify raw text (for testing/debugging).
        
        Args:
            text: Email text to classify
        
        Returns:
            Classification result with label and confidence
        """
        try:
            result = classify_email_with_confidence(text)
            return {
                "prediction": result['label'],
                "confidence": round(result['confidence'], 3),
                "category": self._map_to_category(result['label'])
            }
        except Exception as e:
            logger.error(f"Text classification error: {str(e)}")
            return {
                "prediction": "error",
                "confidence": 0.0,
                "category": "error",
                "error": str(e)
            }


# Global instance (singleton pattern)
_classifier_instance = None


def get_classifier() -> EmailClassifier:
    """
    Get or create the global classifier instance.
    
    Returns:
        EmailClassifier instance
    """
    global _classifier_instance
    
    if _classifier_instance is None:
        _classifier_instance = EmailClassifier()
    
    return _classifier_instance
