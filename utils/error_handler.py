"""
Enhanced error handling and validation framework for contract analysis workflow.
Provides classification, fallback strategies, and recovery mechanisms.
"""

import os
import json
import time
import logging
from enum import Enum
from typing import Dict, Any, Callable, List
from dataclasses import dataclass, asdict
from datetime import datetime


class ErrorSeverity(Enum):
    """Error severity levels for classification."""
    CRITICAL = "critical"      # Stop processing immediately
    RECOVERABLE = "recoverable"  # Try fallback/retry
    WARNING = "warning"        # Continue with degraded functionality
    INFO = "info"             # Log for monitoring


class ErrorCategory(Enum):
    """Categories of errors for appropriate handling."""
    PDF_PROCESSING = "pdf_processing"
    LLM_API = "llm_api"
    DATA_VALIDATION = "data_validation"
    FILE_IO = "file_io"
    NETWORK = "network"
    CONFIGURATION = "configuration"


@dataclass
class ErrorContext:
    """Comprehensive error context for tracking and recovery."""
    error_id: str
    timestamp: str
    node_name: str
    error_type: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    recoverable: bool
    retry_count: int = 0
    max_retries: int = 3
    fallback_attempted: bool = False
    context_data: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        result = asdict(self)
        result['severity'] = self.severity.value
        result['category'] = self.category.value
        return result


class FallbackStrategy:
    """Base class for fallback strategies."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def can_handle(self, error_context: ErrorContext) -> bool:
        """Check if this strategy can handle the given error."""
        raise NotImplementedError
    
    def execute(self, error_context: ErrorContext, **kwargs) -> Dict[str, Any]:
        """Execute the fallback strategy."""
        raise NotImplementedError


class MultiLibraryPDFFallback(FallbackStrategy):
    """Fallback strategy for PDF processing using multiple libraries."""
    
    def __init__(self):
        super().__init__(
            "multi_library_pdf",
            "Try alternative PDF processing libraries when primary fails"
        )
    
    def can_handle(self, error_context: ErrorContext) -> bool:
        return error_context.category == ErrorCategory.PDF_PROCESSING
    
    def execute(self, error_context: ErrorContext, pdf_path: str = None, **kwargs) -> Dict[str, Any]:
        """Try alternative PDF processing methods."""
        if not pdf_path:
            pdf_path = kwargs.get('pdf_path', error_context.context_data.get('pdf_path'))
        
        fallback_methods = [
            self._try_pypdf,
            self._try_pdfplumber,
            self._try_pymupdf,
            self._try_ocr_fallback
        ]
        
        for method in fallback_methods:
            try:
                result = method(pdf_path)
                if result and result.get('success'):
                    return result
            except Exception as e:
                logging.warning(f"PDF fallback method {method.__name__} failed: {e}")
                continue
        
        return {"success": False, "error": "All PDF processing methods failed"}
    
    def _try_pypdf(self, pdf_path: str) -> Dict[str, Any]:
        """Try PyPDF2/pypdf for extraction."""
        try:
            import pypdf
            with open(pdf_path, 'rb') as file:
                reader = pypdf.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                
                if len(text.strip()) < 100:  # Quality check
                    return {"success": False, "error": "Insufficient text extracted"}
                
                return {
                    "success": True,
                    "content": text,
                    "method": "pypdf",
                    "quality_score": self._assess_text_quality(text)
                }
        except ImportError:
            return {"success": False, "error": "pypdf not available"}
        except Exception as e:
            return {"success": False, "error": f"pypdf failed: {e}"}
    
    def _try_pdfplumber(self, pdf_path: str) -> Dict[str, Any]:
        """Try pdfplumber for extraction."""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                if len(text.strip()) < 100:
                    return {"success": False, "error": "Insufficient text extracted"}
                
                return {
                    "success": True,
                    "content": text,
                    "method": "pdfplumber",
                    "quality_score": self._assess_text_quality(text)
                }
        except ImportError:
            return {"success": False, "error": "pdfplumber not available"}
        except Exception as e:
            return {"success": False, "error": f"pdfplumber failed: {e}"}
    
    def _try_pymupdf(self, pdf_path: str) -> Dict[str, Any]:
        """Try PyMuPDF/fitz for extraction."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            
            if len(text.strip()) < 100:
                return {"success": False, "error": "Insufficient text extracted"}
            
            return {
                "success": True,
                "content": text,
                "method": "pymupdf",
                "quality_score": self._assess_text_quality(text)
            }
        except ImportError:
            return {"success": False, "error": "pymupdf not available"}
        except Exception as e:
            return {"success": False, "error": f"pymupdf failed: {e}"}
    
    def _try_ocr_fallback(self, pdf_path: str) -> Dict[str, Any]:
        """OCR fallback for image-based PDFs."""
        try:
            # This would require additional OCR setup (tesseract, etc.)
            # For now, return a placeholder
            return {"success": False, "error": "OCR fallback not implemented"}
        except Exception as e:
            return {"success": False, "error": f"OCR fallback failed: {e}"}
    
    def _assess_text_quality(self, text: str) -> float:
        """Assess the quality of extracted text (0-1 score)."""
        if not text or len(text.strip()) < 50:
            return 0.0
        
        # Basic quality metrics
        word_count = len(text.split())
        len(text)
        line_count = len(text.splitlines())
        
        # Check for common extraction issues
        special_char_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / len(text)
        if special_char_ratio > 0.3:  # Too many special characters
            return 0.3
        
        # Check for reasonable word length distribution
        words = text.split()
        if words:
            avg_word_length = sum(len(word) for word in words) / len(words)
            if avg_word_length < 2 or avg_word_length > 15:  # Unreasonable word lengths
                return 0.4
        
        # Basic quality score
        if word_count > 100 and line_count > 5:
            return 0.8
        elif word_count > 50:
            return 0.6
        else:
            return 0.4


class APIRetryFallback(FallbackStrategy):
    """Fallback strategy for API failures with alternative models/endpoints."""
    
    def __init__(self):
        super().__init__(
            "api_retry",
            "Retry API calls with backoff and alternative configurations"
        )
    
    def can_handle(self, error_context: ErrorContext) -> bool:
        return error_context.category == ErrorCategory.LLM_API or error_context.category == ErrorCategory.NETWORK
    
    def execute(self, error_context: ErrorContext, **kwargs) -> Dict[str, Any]:
        """Execute API retry with fallback configurations."""
        # This would integrate with the existing granite_client retry logic
        # and potentially try alternative models or endpoints
        return {"success": False, "error": "API fallback not yet implemented"}


class ErrorHandler:
    """Main error handler with classification and fallback coordination."""
    
    def __init__(self, log_dir: str | None = None):
        # Default logs under the application package: legal-document-analysis/logs
        if log_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, "logs")
        self.log_dir = log_dir
        self.fallback_strategies: List[FallbackStrategy] = [
            MultiLibraryPDFFallback(),
            APIRetryFallback()
        ]
        self.error_history: List[ErrorContext] = []
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup enhanced error logging."""
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create error handler specific logger
        self.logger = logging.getLogger('enhanced_error_handler')
        self.logger.setLevel(logging.DEBUG)
        
        # File handler for detailed error logs
        error_log_path = os.path.join(self.log_dir, 'enhanced_errors.log')
        file_handler = logging.FileHandler(error_log_path)
        file_handler.setLevel(logging.DEBUG)
        
        # Formatter for structured logging
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
    
    def classify_error(self, error: Exception, node_name: str, context_data: Dict[str, Any] = None) -> ErrorContext:
        """Classify an error and create appropriate error context."""
        error_type = type(error).__name__
        error_message = str(error)
        
        # Determine category and severity based on error type and context
        category = self._determine_category(error, node_name, error_message)
        severity = self._determine_severity(error, category, error_message)
        recoverable = severity in [ErrorSeverity.RECOVERABLE, ErrorSeverity.WARNING]
        
        error_context = ErrorContext(
            error_id=f"{node_name}_{int(time.time())}_{len(self.error_history)}",
            timestamp=datetime.now().isoformat(),
            node_name=node_name,
            error_type=error_type,
            error_message=error_message,
            severity=severity,
            category=category,
            recoverable=recoverable,
            context_data=context_data or {}
        )
        
        self.error_history.append(error_context)
        self._log_error(error_context)
        
        return error_context
    
    def _determine_category(self, error: Exception, node_name: str, error_message: str) -> ErrorCategory:
        """Determine error category based on error type and context."""
        error_type = type(error).__name__
        
        # PDF processing errors
        if 'pdf' in node_name.lower() or 'pdf' in error_message.lower():
            return ErrorCategory.PDF_PROCESSING
        
        # API errors
        if any(term in error_message.lower() for term in ['api', 'request', 'connection', 'timeout', 'rate limit']):
            return ErrorCategory.LLM_API
        
        # File I/O errors
        if error_type in ['FileNotFoundError', 'PermissionError', 'IOError']:
            return ErrorCategory.FILE_IO
        
        # Network errors
        if error_type in ['ConnectionError', 'TimeoutError', 'URLError']:
            return ErrorCategory.NETWORK
        
        # Data validation errors
        if error_type in ['ValueError', 'KeyError', 'IndexError', 'EmptyDataError']:
            return ErrorCategory.DATA_VALIDATION
        
        # Configuration errors
        if error_type in ['AttributeError', 'ImportError', 'ModuleNotFoundError']:
            return ErrorCategory.CONFIGURATION
        
        return ErrorCategory.DATA_VALIDATION  # Default
    
    def _determine_severity(self, error: Exception, category: ErrorCategory, error_message: str) -> ErrorSeverity:
        """Determine error severity for appropriate handling."""
        error_type = type(error).__name__
        
        # Critical errors that should stop processing
        critical_conditions = [
            'missing required configuration' in error_message.lower(),
            'authorization' in error_message.lower() and 'failed' in error_message.lower(),
            error_type in ['ImportError', 'ModuleNotFoundError'] and 'critical' in error_message.lower()
        ]
        
        if any(critical_conditions):
            return ErrorSeverity.CRITICAL
        
        # Recoverable errors that can be retried or have fallbacks
        recoverable_conditions = [
            category == ErrorCategory.PDF_PROCESSING,
            category == ErrorCategory.LLM_API,
            category == ErrorCategory.NETWORK,
            'timeout' in error_message.lower(),
            'connection' in error_message.lower(),
            'rate limit' in error_message.lower()
        ]
        
        if any(recoverable_conditions):
            return ErrorSeverity.RECOVERABLE
        
        # Data validation issues - continue with warnings
        if category == ErrorCategory.DATA_VALIDATION:
            return ErrorSeverity.WARNING
        
        return ErrorSeverity.RECOVERABLE  # Default to recoverable
    
    def handle_error(self, error: Exception, node_name: str, context_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Main error handling entry point with classification and fallback."""
        error_context = self.classify_error(error, node_name, context_data)
        
        # Log the error
        self.logger.error(f"Error in {node_name}: {error_context.to_dict()}")
        
        # Handle based on severity
        if error_context.severity == ErrorSeverity.CRITICAL:
            return self._handle_critical_error(error_context)
        
        elif error_context.severity == ErrorSeverity.RECOVERABLE:
            return self._attempt_recovery(error_context, **kwargs)
        
        elif error_context.severity == ErrorSeverity.WARNING:
            return self._handle_warning(error_context)
        
        else:  # INFO
            return self._handle_info(error_context)
    
    def _handle_critical_error(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Handle critical errors that require stopping processing."""
        return {
            "success": False,
            "error_context": error_context.to_dict(),
            "action": "stop_processing",
            "message": f"Critical error in {error_context.node_name}: {error_context.error_message}"
        }
    
    def _attempt_recovery(self, error_context: ErrorContext, **kwargs) -> Dict[str, Any]:
        """Attempt recovery using appropriate fallback strategies."""
        # Find applicable fallback strategies
        applicable_strategies = [
            strategy for strategy in self.fallback_strategies
            if strategy.can_handle(error_context)
        ]
        
        if not applicable_strategies:
            return {
                "success": False,
                "error_context": error_context.to_dict(),
                "action": "no_fallback_available",
                "message": f"No fallback strategy available for {error_context.category.value} error"
            }
        
        # Try each applicable strategy
        for strategy in applicable_strategies:
            try:
                self.logger.info(f"Attempting fallback strategy: {strategy.name}")
                result = strategy.execute(error_context, **kwargs)
                
                if result.get("success"):
                    error_context.fallback_attempted = True
                    self.logger.info(f"Fallback strategy {strategy.name} succeeded")
                    return {
                        "success": True,
                        "result": result,
                        "fallback_used": strategy.name,
                        "error_context": error_context.to_dict()
                    }
                    
            except Exception as fallback_error:
                self.logger.warning(f"Fallback strategy {strategy.name} failed: {fallback_error}")
                continue
        
        # All fallback strategies failed
        return {
            "success": False,
            "error_context": error_context.to_dict(),
            "action": "all_fallbacks_failed",
            "message": f"All fallback strategies failed for {error_context.category.value} error"
        }
    
    def _handle_warning(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Handle warning-level errors that allow continued processing."""
        return {
            "success": True,
            "warning": True,
            "error_context": error_context.to_dict(),
            "action": "continue_with_warning",
            "message": f"Warning in {error_context.node_name}: {error_context.error_message}"
        }
    
    def _handle_info(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Handle info-level errors for monitoring."""
        return {
            "success": True,
            "info": True,
            "error_context": error_context.to_dict(),
            "action": "logged_for_monitoring",
            "message": f"Info: {error_context.error_message}"
        }
    
    def _log_error(self, error_context: ErrorContext):
        """Log error context to structured log files."""
        # Log to main error log
        self.logger.error(json.dumps(error_context.to_dict(), indent=2))
        
        # Also save to specific error tracking file
        error_tracking_file = os.path.join(self.log_dir, 'error_tracking.jsonl')
        with open(error_tracking_file, 'a') as f:
            f.write(json.dumps(error_context.to_dict()) + '\n')
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors encountered during processing."""
        if not self.error_history:
            return {"total_errors": 0, "summary": "No errors encountered"}
        
        summary = {
            "total_errors": len(self.error_history),
            "by_severity": {},
            "by_category": {},
            "by_node": {},
            "fallbacks_attempted": sum(1 for e in self.error_history if e.fallback_attempted),
            "critical_errors": [e.to_dict() for e in self.error_history if e.severity == ErrorSeverity.CRITICAL]
        }
        
        # Group by various dimensions
        for error in self.error_history:
            # By severity
            severity_key = error.severity.value
            summary["by_severity"][severity_key] = summary["by_severity"].get(severity_key, 0) + 1
            
            # By category
            category_key = error.category.value
            summary["by_category"][category_key] = summary["by_category"].get(category_key, 0) + 1
            
            # By node
            node_key = error.node_name
            summary["by_node"][node_key] = summary["by_node"].get(node_key, 0) + 1
        
        return summary


# Global error handler instance
error_handler = ErrorHandler()


# Decorator for automatic error handling in node functions
def handle_node_errors(node_name: str = None):
    """Decorator to automatically handle errors in node functions."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            actual_node_name = node_name or func.__name__
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Extract state if available for context
                context_data = {}
                if args and hasattr(args[0], 'get'):
                    # Assume first arg is state dict
                    context_data = {
                        "target_document_path": args[0].get("target_document_path"),
                        "current_step": actual_node_name
                    }
                
                result = error_handler.handle_error(e, actual_node_name, context_data, **kwargs)
                
                if not result.get("success"):
                    # For critical errors, re-raise to stop processing
                    if result.get("action") == "stop_processing":
                        raise e
                    # For other failures, return empty dict (existing behavior)
                    return {}
                else:
                    # For warnings or successful fallbacks, return result or continue
                    return result.get("result", {})
        
        return wrapper
    return decorator