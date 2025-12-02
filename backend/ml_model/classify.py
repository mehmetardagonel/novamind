
import os
import pickle
import re
import warnings
import logging
from typing import Optional, Tuple, Dict
from threading import Lock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Handle optional dependencies gracefully
try:
    import numpy as np
except ImportError:
    np = None
    logger.warning("NumPy not available, some features may be limited")

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None
    logger.warning("sentence-transformers not available, using rule-based classification only")

# Configuration
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(CURRENT_DIR, "models")


# Global model instances with thread-safe loading
_model_lock = Lock()
_models_loaded = False
spam_pipeline = None
embedder = None
imp_model = None


def load_models() -> Tuple[Optional[object], Optional[object], Optional[object]]:
    """
    Thread-safe model loading with singleton pattern.
    
    Returns:
        Tuple of (spam_pipeline, embedder, importance_model) or (None, None, None) if unavailable
    """
    global spam_pipeline, embedder, imp_model, _models_loaded
    
    # Double-checked locking pattern for thread safety
    if _models_loaded:
        return spam_pipeline, embedder, imp_model
    
    with _model_lock:
        if _models_loaded:  # Check again inside lock
            return spam_pipeline, embedder, imp_model
        
        try:
            if not os.path.exists(MODEL_DIR):
                logger.warning(f"Model directory not found: {MODEL_DIR}")
                _models_loaded = True  # Don't try again
                return None, None, None
            
            # Load spam detection pipeline
            spam_model_path = os.path.join(MODEL_DIR, "spam_model.pkl")
            if os.path.exists(spam_model_path):
                try:
                    logger.info(f"   📂 Loading spam model from {spam_model_path}")
                    with open(spam_model_path, "rb") as f:
                        spam_pipeline = pickle.load(f)
                    logger.info("   ✅ Spam model loaded successfully")
                except Exception as e:
                    logger.error(f"   ❌ Failed to load spam model: {e}")
            
            # Load sentence embedder
            if SentenceTransformer:
                try:
                    logger.info("   📦 Loading sentence embedder (all-MiniLM-L6-v2)...")
                    logger.info("   ⏳ This may download ~90MB on first run")
                    embedder = SentenceTransformer("all-MiniLM-L6-v2")
                    logger.info("   ✅ Sentence embedder loaded successfully")
                except Exception as e:
                    logger.error(f"   ❌ Failed to load embedder: {e}")
            
            # Load importance classification model
            imp_model_path = os.path.join(MODEL_DIR, "embedding_model.pkl")
            if os.path.exists(imp_model_path):
                try:
                    logger.info(f"   📂 Loading importance model from {imp_model_path}")
                    with open(imp_model_path, "rb") as f:
                        data = pickle.load(f)
                        imp_model = data.get("model")
                    logger.info("   ✅ Importance model loaded successfully")
                except Exception as e:
                    logger.error(f"   ❌ Failed to load importance model: {e}")
            
            _models_loaded = True
            return spam_pipeline, embedder, imp_model
            
        except Exception as e:
            logger.error(f"Unexpected error loading models: {e}")
            _models_loaded = True
            return None, None, None


def detect_prompt_injection(text: str) -> bool:
    """
    Detect potential prompt injection attempts in email text.
    
    Uses multiple detection strategies:
    1. Pattern matching for known injection techniques
    2. Structural analysis for suspicious formatting
    3. Semantic analysis for contradictory instructions
    
    Args:
        text: Email text to analyze
        
    Returns:
        True if injection detected, False otherwise
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Compile patterns once for performance (in real deployment, move to module level)
    injection_patterns = [
        # Instruction manipulation
        r"ignore\s+(all\s+)?previous\s+instructions?",
        r"disregard\s+(all\s+)?previous",
        r"forget\s+everything",
        
        # System/admin attempts
        r"override\s+classification",
        r"admin\s+mode",
        r"administrator\s+access",
        r"\[system\].*\[\/system\]",
        r"system:\s*override",
        r"sudo\s+classify",
        
        # Direct classification manipulation
        r"classify:\s*(important|spam|ham)",
        r"classification\s*=\s*(important|spam|ham)",
        r"set\s+classification\s+to",
        r"mark\s+this\s+(as\s+)?(important|spam|ham)",
        r"declare\s+this\s+message\s+as",
        r"label\s+this\s+(as\s+)?(important|spam|ham)",
        
        # Role confusion
        r"you\s+are\s+(now\s+)?a\s+helpful\s+assistant",
        r"as\s+the\s+email\s+classifier",
        r"i\s+am\s+the\s+(administrator|admin|owner)",
        r"acting\s+as\s+system",
        
        # Meta instructions
        r"meta:\s*classify",
        r"\[meta:.*\]",
        r"```\s*classification",
        
        # Delimiter attacks
        r"---\s*system:.*---",
        r"\|\|\|\s*override:.*\|\|\|",
        
        # Multi-step attacks
        r"step\s+\d+:\s*(ignore|override|classify)",
        r"first,?\s+ignore.*then\s+classify",
        
        # Code injection attempts
        r"<script>.*</script>",
        r"javascript:",
        r"eval\s*\(",
    ]
    
    for pattern in injection_patterns:
        if re.search(pattern, text_lower):
            logger.warning(f"Prompt injection detected: pattern '{pattern[:30]}...'")
            return True
    
    # Contradictory instructions
    if "not spam" in text_lower and any(x in text_lower for x in ["buy now", "click here", "free money"]):
        logger.warning("Prompt injection detected: contradictory spam instructions")
        return True
    
    # Multiple conflicting classifications
    classifications = ["this is spam", "this is important", "this is ham", 
                      "classify as spam", "classify as important", "classify as ham"]
    matches = sum(1 for c in classifications if c in text_lower)
    if matches > 1:
        logger.warning("Prompt injection detected: multiple conflicting classifications")
        return True
    
    # Suspicious command-like structures
    if re.search(r"^(SYSTEM|ADMIN|OVERRIDE|COMMAND):", text, re.MULTILINE):
        logger.warning("Prompt injection detected: suspicious command structure")
        return True
    
    return False


def is_spam_content(text: str) -> bool:
    """
    Check for traditional spam indicators using rule-based detection.
    
    IMPROVEMENTS:
    - Added more pharmaceutical spam patterns
    - Improved URL detection
    - Better handling of legitimate business communications
    - Reduced false positives for work emails
    
    Args:
        text: Email text to analyze
        
    Returns:
        True if spam indicators exceed threshold, False otherwise
    """
    if not text:
        return False
    
    text_lower = text.lower()
    spam_score = 0
    
    # Comprehensive spam keyword list with weights
    spam_keywords = {
        # High-weight financial scams (2 points each)
        "nigerian prince": 2, "million dollars": 2, "inheritance": 2,
        "lottery winner": 2, "tax refund": 2, "wire transfer": 2,
        
        # Medium-weight spam (1 point each)
        "buy now": 1, "click here": 1, "limited offer": 1, "act now": 1,
        "free money": 1, "winner": 1, "congratulations you": 1, "prize": 1,
        "100% free": 1, "no credit check": 1, "guarantee": 1, "risk free": 1,
        
        # Pharmaceutical spam
        "viagra": 1, "cialis": 1, "pills online": 1, "pharmacy": 1,
        "weight loss": 1, "lose weight fast": 1, "diet pills": 1,
        
        # Marketing spam
        "casino": 1, "betting": 1, "work from home": 1,
        "multi level marketing": 1, "mlm": 1, "get rich quick": 1,
        
        # Adult content
        "xxx": 2, "singles in your area": 2,
        
        # Urgency spam (but exclude legitimate work urgency)
        "urgent response required": 1, "expire": 1, "last chance": 1,
    }
    
    # Check for spam keywords with weights
    for keyword, weight in spam_keywords.items():
        if keyword in text_lower:
            spam_score += weight
    
    # Check for excessive capitalization (excluding work terms)
    if len(text) > 10:
        work_terms = ["urgent", "meeting", "deadline", "project", "report", 
                     "asap", "eod", "cob", "fyi", "review", "exam", "assignment"]
        has_work_term = any(term in text_lower for term in work_terms)
        
        if not has_work_term:
            letter_count = sum(1 for c in text if c.isalpha())
            if letter_count > 0:
                capital_ratio = sum(1 for c in text if c.isupper()) / letter_count
                if capital_ratio > 0.6:  # More than 60% capitals
                    spam_score += 2
    
    # Check for excessive punctuation
    if text.count('!') >= 3:
        spam_score += 2
    if text.count('$') >= 2:
        spam_score += 2
    if re.search(r'\*{3,}', text):
        spam_score += 1
    
    # Check for suspicious URL patterns
    suspicious_urls = ['bit.ly', 'tinyurl', 'short.link', 'click.here', 
                      't.co', 'goo.gl', 'ow.ly']
    if any(url in text_lower for url in suspicious_urls):
        spam_score += 2
    
    # Check for multiple URLs (legitimate emails rarely have many)
    url_count = len(re.findall(r'http[s]?://', text_lower))
    if url_count >= 3:
        spam_score += 1
    
    # Threshold for spam detection (lowered slightly to reduce false negatives)
    return spam_score >= 3


def is_important_content(text: str) -> bool:
    """
    Check if email contains work-related important content.
    
    IMPROVEMENTS:
    - Added educational keywords (exam, assignment, course, lecture, etc.)
    - Better phrase detection with regex
    - Improved scoring system
    - Added context-aware detection
    
    Args:
        text: Email text to analyze
        
    Returns:
        True if important work-related content detected, False otherwise
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Remove URLs to avoid false positives
    text_clean = re.sub(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', 
        '', text_lower
    )
    
    # Comprehensive work-related keywords with weights
    important_keywords = {
        # High-priority indicators (weight 2)
        "urgent": 2, "asap": 2, "immediately": 2, "critical": 2,
        "deadline": 2, "time sensitive": 2,
        
        # Meeting related (weight 1)
        "meeting": 1, "conference": 1, "presentation": 1, "agenda": 1,
        "zoom": 1, "teams": 1, "webinar": 1,
        
        # Project/work related (weight 1)
        "project": 1, "report": 1, "proposal": 1, "contract": 1,
        "deliverable": 1, "milestone": 1, "review": 1, "approval": 1,
        "feedback": 1, "budget": 1,
        
        # Educational terms (weight 1) - ADDED FOR IMPROVEMENT
        "exam": 1, "test": 1, "quiz": 1, "assignment": 1,
        "homework": 1, "course": 1, "lecture": 1, "syllabus": 1,
        "grade": 1, "semester": 1, "professor": 1, "instructor": 1,
        "class": 1, "tutorial": 1, "lab": 1, "thesis": 1,
        
        # Business terms (weight 1)
        "client": 1, "customer": 1, "stakeholder": 1, "management": 1,
        "executive": 1, "quarterly": 1, "annual": 1, "fiscal": 1,
        
        # Action items (weight 1)
        "action required": 1, "please review": 1, "needs your": 1,
        "requires your": 1, "for your approval": 1, "sign off": 1,
    }
    
    # Count weighted keyword matches
    keyword_score = 0
    for keyword, weight in important_keywords.items():
        if keyword in text_clean:
            keyword_score += weight
    
    # Check for important phrases with regex
    important_phrases = [
        r"please\s+review",
        r"need(s)?\s+your\s+(attention|approval|review|input)",
        r"requires?\s+your",
        r"action\s+required",
        r"time\s+sensitive",
        r"by\s+(end\s+of\s+day|eod|cob|tomorrow|today)",
        r"meeting\s+(scheduled|today|tomorrow)",
        r"conference\s+call",
        r"due\s+(date|by|on|tomorrow|today)",
        r"for\s+your\s+(review|approval|signature|consideration)",
        r"exam\s+(on|tomorrow|today|next\s+week)",  # Educational
        r"assignment\s+due",  # Educational
        r"submit\s+by",  # Educational
    ]
    
    phrase_matches = sum(1 for phrase in important_phrases if re.search(phrase, text_clean))
    
    # Decision logic with improved thresholds
    if keyword_score >= 3 or phrase_matches >= 2:
        return True
    
    if keyword_score >= 2 and phrase_matches >= 1:
        return True
    
    # Check for business email patterns
    business_patterns = [
        r"dear\s+(team|all|colleagues|students|class)",
        r"(regards|sincerely|best),?\s*\n",
        r"please\s+find\s+attached",
        r"as\s+discussed",
        r"following\s+up\s+on",
        r"attached\s+(is|are|you'll\s+find)",
    ]
    
    if any(re.search(pattern, text_clean) for pattern in business_patterns):
        if keyword_score >= 1:
            return True
    
    return False


def classify_with_ml_models(text: str) -> Optional[str]:
    """
    Classify email using ML models if available.
    
    IMPROVEMENTS:
    - Better error handling
    - Fallback logic for partial model loading
    - Added logging for debugging
    
    Args:
        text: Email text to classify
        
    Returns:
        Classification result or None if models unavailable
    """
    global spam_pipeline, embedder, imp_model
    
    if not _models_loaded:
        load_models()
    
    # Check if we have at least spam model
    if spam_pipeline is None:
        logger.debug("Spam model not available for ML classification")
        return None
    
    try:
        # Check with spam model
        spam_pred = spam_pipeline.predict([text])[0]
        if spam_pred == "spam":
            logger.debug("ML model classified as spam")
            return "spam"
        
        # Check importance with embedding model (if available)
        if embedder is not None and imp_model is not None:
            try:
                embedding = embedder.encode([text])
                imp_pred = imp_model.predict(embedding)[0]
                logger.debug(f"ML importance model classified as: {imp_pred}")
                return imp_pred
            except Exception as e:
                logger.warning(f"Importance model failed: {e}")
                # Fall through to return ham
        
        # If we only have spam model and it's not spam, default to ham
        return "ham"
        
    except Exception as e:
        logger.error(f"ML classification error: {e}")
        return None


def classify_email(text: str) -> str:
    """
    Main email classification function with improved logic flow.
    
    Classifies emails into three categories:
    - spam: Unwanted promotional or malicious emails
    - ham: Normal, non-important emails
    - important: Work-related or high-priority emails
    
    IMPROVEMENTS:
    - Better priority ordering
    - Enhanced edge case handling
    - Improved logging
    - Confidence-based decisions
    
    Args:
        text: Email text to classify
        
    Returns:
        Classification result: "spam", "ham", or "important"
    """
    try:
        # Handle empty input
        if not text or not text.strip():
            return "ham"
        
        text = str(text).strip()  # Ensure string type and remove whitespace
        text_lower = text.lower()
        
        # Priority 1: Security - Check for prompt injection
        if detect_prompt_injection(text):
            logger.info("Classified as spam due to prompt injection")
            return "spam"
        
        # Priority 2: Check if it's important work-related content
        is_important = is_important_content(text)
        
        # Priority 3: Check for spam indicators
        # Special case: All-caps important messages shouldn't be spam
        if is_important and text.isupper() and len(text) > 10:
            urgent_terms = ["urgent", "meeting", "deadline", "exam", "assignment"]
            if any(term in text_lower for term in urgent_terms):
                logger.info("Classified as important (all-caps work message)")
                return "important"
        
        is_spam = is_spam_content(text)
        
        # If both spam and important indicators, use context to decide
        if is_spam and is_important:
            # Check for strong important indicators
            strong_important = any(term in text_lower for term in 
                                 ["urgent", "deadline", "meeting", "exam", "assignment"])
            if strong_important:
                logger.info("Classified as important (overriding spam indicators)")
                return "important"
            else:
                logger.info("Classified as spam (stronger indicators)")
                return "spam"
        
        if is_spam:
            logger.info("Classified as spam (rule-based)")
            return "spam"
        
        if is_important:
            logger.info("Classified as important (rule-based)")
            return "important"
        
        # Priority 4: Try ML models for ambiguous cases
        ml_result = classify_with_ml_models(text)
        if ml_result:
            # Override ML for strong rule-based signals
            urgent_terms = ["urgent", "meeting", "deadline", "exam", "assignment"]
            if ml_result == "ham" and any(word in text_lower for word in urgent_terms):
                logger.info("Classified as important (ML override)")
                return "important"
            
            logger.info(f"Classified as {ml_result} (ML model)")
            return ml_result
        
        # Priority 5: Pattern-based classification for simple messages
        simple_greetings = [
            r'^(hi|hello|hey|good\s+(morning|afternoon|evening))',
            r'^(thanks|thank\s+you|regards|best|sincerely)',
            r'how\s+are\s+you',
            r'hope\s+(you|this).*well',
        ]
        
        if any(re.search(pattern, text_lower) for pattern in simple_greetings):
            logger.info("Classified as ham (greeting pattern)")
            return "ham"
        
        # Default classification
        logger.info("Classified as ham (default)")
        return "ham"
        
    except Exception as e:
        logger.error(f"Classification error: {e}", exc_info=True)
        return "ham"  # Safe default


def classify_email_with_confidence(text: str) -> Dict[str, any]:
    """
    Extended classification function that returns confidence scores.
    
    Args:
        text: Email text to classify
        
    Returns:
        Dictionary with 'label' and 'confidence' keys
    """
    label = classify_email(text)
    
    # Simple confidence heuristic (can be improved with ML model probabilities)
    confidence = 0.7  # Default
    
    if detect_prompt_injection(text):
        confidence = 0.95  # High confidence for injection detection
    elif is_spam_content(text) and is_important_content(text):
        confidence = 0.6  # Lower confidence for conflicting signals
    elif is_spam_content(text) or is_important_content(text):
        confidence = 0.85  # High confidence for clear rule matches
    
    return {
        "label": label,
        "confidence": confidence
    }


# For backward compatibility
classify_email_improved = classify_email

# NOTE: Models are loaded lazily via get_classifier() in ml_service.py
# or explicitly in FastAPI startup event. This prevents blocking during module import.
