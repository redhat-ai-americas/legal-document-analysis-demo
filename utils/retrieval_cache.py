"""
Retrieval Cache and Optimization
Provides caching and performance optimization for retrieval operations
"""

import os
import hashlib
import time
import pickle
from typing import List, Dict, Optional, Any
from pathlib import Path
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class CachedResult:
    """Cached retrieval result"""
    query: str
    results: List[Any]
    timestamp: float
    hit_count: int = 0
    metadata: Optional[Dict[str, Any]] = None


class RetrievalCache:
    """LRU cache for retrieval results"""
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 3600,
        cache_dir: Optional[str] = None
    ):
        """
        Initialize retrieval cache
        
        Args:
            max_size: Maximum cache entries
            ttl_seconds: Time to live for cache entries
            cache_dir: Directory for persistent cache
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        
        # LRU cache using OrderedDict
        self.cache: OrderedDict[str, CachedResult] = OrderedDict()
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
        # Persistent cache directory
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data" / "cache" / "retrieval"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load persistent cache
        self._load_persistent_cache()
    
    def get(self, query: str) -> Optional[List[Any]]:
        """
        Get cached results for query
        
        Args:
            query: Search query
            
        Returns:
            Cached results or None
        """
        cache_key = self._get_cache_key(query)
        
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            
            # Check TTL
            if time.time() - cached.timestamp < self.ttl_seconds:
                # Move to end (most recently used)
                self.cache.move_to_end(cache_key)
                
                # Update statistics
                cached.hit_count += 1
                self.hits += 1
                
                return cached.results
            else:
                # Expired, remove from cache
                del self.cache[cache_key]
        
        self.misses += 1
        return None
    
    def put(
        self,
        query: str,
        results: List[Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Cache retrieval results
        
        Args:
            query: Search query
            results: Results to cache
            metadata: Optional metadata
        """
        cache_key = self._get_cache_key(query)
        
        # Create cached result
        cached = CachedResult(
            query=query,
            results=results,
            timestamp=time.time(),
            metadata=metadata
        )
        
        # Add to cache
        self.cache[cache_key] = cached
        self.cache.move_to_end(cache_key)
        
        # Evict if over size limit
        while len(self.cache) > self.max_size:
            # Remove least recently used
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            self.evictions += 1
    
    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        return {
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "evictions": self.evictions,
            "ttl_seconds": self.ttl_seconds
        }
    
    def save_persistent(self):
        """Save cache to disk"""
        cache_file = self.cache_dir / "cache.pkl"
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(dict(self.cache), f)
        except Exception as e:
            print(f"Error saving cache: {str(e)}")
    
    def _load_persistent_cache(self):
        """Load cache from disk"""
        cache_file = self.cache_dir / "cache.pkl"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    saved_cache = pickle.load(f)
                    
                    # Load non-expired entries
                    current_time = time.time()
                    for key, cached in saved_cache.items():
                        if current_time - cached.timestamp < self.ttl_seconds:
                            self.cache[key] = cached
                    
                    print(f"Loaded {len(self.cache)} cached entries")
                    
            except Exception as e:
                print(f"Error loading cache: {str(e)}")
    
    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for query"""
        return hashlib.md5(query.encode()).hexdigest()


class RetrievalOptimizer:
    """Optimization strategies for retrieval"""
    
    def __init__(self):
        """Initialize retrieval optimizer"""
        self.query_cache = RetrievalCache()
        self.performance_stats = {
            "total_queries": 0,
            "total_time": 0.0,
            "query_times": []
        }
    
    def optimize_query(self, query: str) -> str:
        """
        Optimize query for better retrieval
        
        Args:
            query: Original query
            
        Returns:
            Optimized query
        """
        # Remove stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
            'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are',
            'was', 'were', 'been', 'be', 'have', 'has', 'had'
        }
        
        words = query.lower().split()
        filtered = [w for w in words if w not in stop_words]
        
        # Expand abbreviations
        abbreviations = {
            'sla': 'service level agreement',
            'nda': 'non disclosure agreement',
            'ip': 'intellectual property',
            'roi': 'return on investment'
        }
        
        expanded = []
        for word in filtered:
            if word in abbreviations:
                expanded.extend(abbreviations[word].split())
            else:
                expanded.append(word)
        
        return ' '.join(expanded)
    
    def parallel_retrieve(
        self,
        queries: List[str],
        retriever,
        top_k: int = 10,
        batch_size: int = 10
    ) -> List[List[Any]]:
        """
        Retrieve for multiple queries in parallel
        
        Args:
            queries: List of queries
            retriever: Retriever instance
            top_k: Results per query
            batch_size: Batch size
            
        Returns:
            List of result lists
        """
        all_results = []
        
        for i in range(0, len(queries), batch_size):
            batch = queries[i:i+batch_size]
            batch_results = []
            
            for query in batch:
                # Check cache first
                cached = self.query_cache.get(query)
                if cached is not None:
                    batch_results.append(cached)
                else:
                    # Retrieve and cache
                    start_time = time.time()
                    results = retriever.retrieve(query, top_k)
                    elapsed = time.time() - start_time
                    
                    # Update stats
                    self.performance_stats["total_queries"] += 1
                    self.performance_stats["total_time"] += elapsed
                    self.performance_stats["query_times"].append(elapsed)
                    
                    # Cache results
                    self.query_cache.put(query, results)
                    batch_results.append(results)
            
            all_results.extend(batch_results)
        
        return all_results
    
    def deduplicate_results(
        self,
        results: List[Any],
        key_func=None
    ) -> List[Any]:
        """
        Remove duplicate results
        
        Args:
            results: List of results
            key_func: Function to extract deduplication key
            
        Returns:
            Deduplicated results
        """
        if not key_func:
            def key_func(x):
                return x.doc_id if hasattr(x, 'doc_id') else str(x)
        
        seen = set()
        unique = []
        
        for result in results:
            key = key_func(result)
            if key not in seen:
                seen.add(key)
                unique.append(result)
        
        return unique
    
    def rerank_results(
        self,
        results: List[Any],
        query: str,
        reranker=None
    ) -> List[Any]:
        """
        Rerank results for better relevance
        
        Args:
            results: Initial results
            query: Original query
            reranker: Optional reranker model
            
        Returns:
            Reranked results
        """
        if not reranker:
            # Simple reranking based on query term overlap
            query_terms = set(query.lower().split())
            
            def score_func(result):
                text = result.text if hasattr(result, 'text') else str(result)
                text_terms = set(text.lower().split())
                overlap = len(query_terms & text_terms)
                return overlap / len(query_terms) if query_terms else 0
            
            # Add rerank scores
            for result in results:
                if hasattr(result, 'metadata'):
                    if result.metadata is None:
                        result.metadata = {}
                    result.metadata['rerank_score'] = score_func(result)
            
            # Sort by rerank score
            results.sort(
                key=lambda x: x.metadata.get('rerank_score', 0) if hasattr(x, 'metadata') else 0,
                reverse=True
            )
        
        return results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        query_times = self.performance_stats["query_times"]
        
        if query_times:
            import numpy as np
            stats = {
                "total_queries": self.performance_stats["total_queries"],
                "avg_time": np.mean(query_times),
                "median_time": np.median(query_times),
                "p95_time": np.percentile(query_times, 95),
                "p99_time": np.percentile(query_times, 99),
                "cache_stats": self.query_cache.get_stats()
            }
        else:
            stats = {
                "total_queries": 0,
                "cache_stats": self.query_cache.get_stats()
            }
        
        return stats


# Global instances
retrieval_cache = RetrievalCache()
retrieval_optimizer = RetrievalOptimizer()


# Convenience functions
def cache_retrieval_results(query: str, results: List[Any]):
    """Cache retrieval results"""
    retrieval_cache.put(query, results)


def get_cached_results(query: str) -> Optional[List[Any]]:
    """Get cached retrieval results"""
    return retrieval_cache.get(query)


def optimize_retrieval_query(query: str) -> str:
    """Optimize query for retrieval"""
    return retrieval_optimizer.optimize_query(query)