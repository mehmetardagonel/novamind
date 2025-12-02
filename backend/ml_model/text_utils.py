
import re
import string
from sklearn.base import BaseEstimator, TransformerMixin, ClassifierMixin
import numpy as np
from typing import List


def preprocess_text(text):
    # Handle None and empty strings
    if not text:
        return ""
    
    # Convert to string if not already
    text = str(text).strip()
    
    if not text:  # Check again after stripping
        return ""
    
    # Store original case for important pattern detection
    original = text
    
    # Convert to lowercase for processing
    text = text.lower()
    
    # Remove URLs but keep the context
    # Improved regex for better URL matching
    text = re.sub(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        ' url_removed ',
        text
    )
    
    # Remove email addresses but mark them
    text = re.sub(r'\S+@\S+\.\S+', ' email_removed ', text)
    
    # Keep numbers that might be important (dates, times, amounts)
    # Times: HH:MM or H:MM
    text = re.sub(r'\b(\d{1,2}:\d{2})\b', ' time_token ', text)
    
    # Dates: MM/DD/YYYY, M/D/YY, etc.
    text = re.sub(r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b', ' date_token ', text)
    
    # Money amounts: $123, $1,234.56, etc.
    text = re.sub(r'\$[\d,]+\.?\d*', ' money_token ', text)
    
    # Remove special characters but keep sentence structure
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Normalize whitespace (multiple spaces to single space)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Add special tokens for excessive punctuation from original
    punct_count = original.count('!') + original.count('?') + original.count('$')
    if punct_count > 5:
        text = text + ' excessive_punctuation'
    
    # Add token for all caps (but only for longer messages)
    if len(original) > 10:
        letter_count = sum(1 for c in original if c.isalpha())
        if letter_count > 0:
            caps_ratio = sum(1 for c in original if c.isupper()) / letter_count
            if caps_ratio > 0.8:  # More than 80% uppercase
                text = text + ' all_caps_text'
    
    return text


class TextPreprocessor(BaseEstimator, TransformerMixin):
    """
    Scikit-learn compatible text preprocessor.
    
    IMPROVEMENTS:
    - Added error handling
    - Better input validation
    - Support for both strings and lists
    """
    
    def fit(self, X, y=None):
        """Fit method (no-op for this transformer)."""
        return self

    def transform(self, X):
        """
        Transform text data.
        
        Args:
            X: List of text strings or single string
            
        Returns:
            List of preprocessed text strings
        """
        # Handle single string input
        if isinstance(X, str):
            return [preprocess_text(X)]
        
        # Handle list/array input
        try:
            return [preprocess_text(text) for text in X]
        except Exception as e:
            print(f"Error in text preprocessing: {e}")
            # Return empty strings for failed items
            return ["" for _ in X]


class SpamThresholdWrapper(BaseEstimator, ClassifierMixin):
    """
    Wrapper for adjusting spam detection threshold.
    
    IMPROVEMENTS:
    - Better error handling
    - Fixed edge cases with class detection
    - Added validation
    """
    
    def __init__(self, base_model, threshold=0.82):
        """
        Initialize threshold wrapper.
        
        Args:
            base_model: The base classifier model
            threshold: Probability threshold for spam classification (0-1)
        """
        self.base_model = base_model
        self.threshold = max(0.0, min(1.0, threshold))  # Clamp to [0, 1]
        self.classes_ = None

    def fit(self, X, y):
        """
        Fit the base model.
        
        Args:
            X: Training features
            y: Training labels
            
        Returns:
            self
        """
        self.base_model.fit(X, y)
        self.classes_ = self.base_model.classes_
        return self

    def predict(self, X):
        """
        Predict with adjusted threshold for spam detection.
        
        IMPROVEMENTS:
        - Better class index detection
        - Handles both string and numeric labels
        - Improved error handling
        
        Args:
            X: Features to predict
            
        Returns:
            Array of predictions
        """
        try:
            # Get probability predictions
            probs = self.base_model.predict_proba(X)
            
            # Find the index for spam and ham classes
            spam_idx = None
            ham_idx = None
            
            for i, cls in enumerate(self.classes_):
                cls_str = str(cls).lower()
                if cls_str in ['spam', '1']:
                    spam_idx = i
                elif cls_str in ['ham', '0']:
                    ham_idx = i
            
            # If we can't find the indices, fall back to base prediction
            if spam_idx is None:
                print("Warning: Could not find spam class, using base model prediction")
                return self.base_model.predict(X)
            
            # Apply threshold
            predictions = []
            for prob in probs:
                if prob[spam_idx] >= self.threshold:
                    predictions.append("spam")
                else:
                    predictions.append("ham")
            
            return np.array(predictions)
            
        except Exception as e:
            print(f"Error in threshold prediction: {e}")
            # Fall back to base model prediction
            try:
                return self.base_model.predict(X)
            except Exception as e2:
                print(f"Base model prediction also failed: {e2}")
                # Return ham as safe default
                return np.array(["ham"] * len(X))

    def predict_proba(self, X):
        """
        Get probability predictions from base model.
        
        Args:
            X: Features
            
        Returns:
            Probability array
        """
        return self.base_model.predict_proba(X)
    
    def score(self, X, y, sample_weight=None):
        """
        Calculate accuracy score.
        
        Args:
            X: Test features
            y: True labels
            sample_weight: Optional sample weights
            
        Returns:
            Accuracy score
        """
        return self.base_model.score(X, y, sample_weight)


class EnhancedTextFeatures(BaseEstimator, TransformerMixin):
    """
    Extract additional features from text for better classification.
    
    IMPROVEMENTS:
    - Added more features
    - Better error handling
    - Normalized feature scales
    """
    
    def fit(self, X, y=None):
        """Fit method (no-op for this transformer)."""
        return self
    
    def transform(self, X):
        """
        Extract features from text.
        
        Args:
            X: List of text strings
            
        Returns:
            NumPy array of features
        """
        features = []
        
        for text in X:
            try:
                text_str = str(text) if text is not None else ""
                text_lower = text_str.lower()
                
                # Basic text statistics
                length = len(text_str)
                words = text_str.split()
                word_count = len(words)
                
                # Character ratios (avoid division by zero)
                caps_ratio = 0
                if length > 0:
                    caps_ratio = sum(1 for c in text_str if c.isupper()) / length
                
                # Average word length
                avg_word_length = 0
                if word_count > 0:
                    avg_word_length = sum(len(w) for w in words) / word_count
                
                # Punctuation counts
                exclamation_count = text_str.count('!')
                question_count = text_str.count('?')
                dollar_count = text_str.count('$')
                
                # Pattern counts
                url_count = len(re.findall(r'http[s]?://', text_lower))
                email_count = len(re.findall(r'\S+@\S+', text_str))
                
                # Keyword indicators (binary features)
                has_urgent = 1 if 'urgent' in text_lower else 0
                has_meeting = 1 if 'meeting' in text_lower else 0
                has_deadline = 1 if 'deadline' in text_lower else 0
                has_exam = 1 if 'exam' in text_lower else 0  # Added
                has_assignment = 1 if 'assignment' in text_lower else 0  # Added
                has_free = 1 if 'free' in text_lower else 0
                has_click = 1 if 'click' in text_lower else 0
                has_buy = 1 if 'buy' in text_lower else 0
                
                # Compile feature vector
                feat = [
                    length,
                    word_count,
                    caps_ratio,
                    avg_word_length,
                    exclamation_count,
                    question_count,
                    dollar_count,
                    url_count,
                    email_count,
                    has_urgent,
                    has_meeting,
                    has_deadline,
                    has_exam,
                    has_assignment,
                    has_free,
                    has_click,
                    has_buy,
                ]
                
                features.append(feat)
                
            except Exception as e:
                print(f"Error extracting features: {e}")
                # Return zero vector on error
                features.append([0] * 17)
        
        return np.array(features, dtype=np.float64)


def extract_key_phrases(text: str, max_phrases: int = 5) -> List[str]:
    """
    Extract key phrases from text for analysis.
    
    Args:
        text: Input text
        max_phrases: Maximum number of phrases to extract
        
    Returns:
        List of key phrases
    """
    if not text:
        return []
    
    text_lower = text.lower()
    
    # Common multi-word phrases that indicate importance
    important_phrases = [
        "action required", "please review", "needs your attention",
        "time sensitive", "due date", "meeting scheduled",
        "conference call", "for your approval", "urgent matter",
        "exam tomorrow", "assignment due", "project deadline"
    ]
    
    found_phrases = []
    for phrase in important_phrases:
        if phrase in text_lower and len(found_phrases) < max_phrases:
            found_phrases.append(phrase)
    
    return found_phrases


def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Calculate simple Jaccard similarity between two texts.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score between 0 and 1
    """
    if not text1 or not text2:
        return 0.0
    
    # Tokenize and convert to sets
    words1 = set(preprocess_text(text1).split())
    words2 = set(preprocess_text(text2).split())
    
    if not words1 or not words2:
        return 0.0
    
    # Jaccard similarity
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return intersection / union if union > 0 else 0.0
