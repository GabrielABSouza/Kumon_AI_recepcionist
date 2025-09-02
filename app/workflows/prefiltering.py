"""
Intent Rule Prefiltering with Aho-Corasick Index

This module implements high-performance prefiltering for intent rules using
Aho-Corasick string matching algorithm. It reduces the number of regex evaluations
by filtering rules based on literal string presence in the input text.

Performance Requirements:
- Prefilter construction: O(Σ|prefilter_literal|) 
- Text matching: O(|text| + matches)
- Memory usage: ~2MB for 1000 rules
- P95 total latency: ≤ 5ms for prefiltering step
"""

import re
import unicodedata
from typing import List, Set, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import ahocorasick
import time
import logging

logger = logging.getLogger(__name__)


class PrefilterEngine(Enum):
    """Available prefiltering engines"""
    AHOCORASICK = "ahocorasick"
    TRIE = "trie"  # Future implementation


@dataclass
class PrefilterRule:
    """Rule metadata for prefiltering"""
    rule_id: str
    prefilter_literal: str
    priority: int
    lang: str
    
    def __post_init__(self):
        """Validate rule after initialization"""
        if len(self.prefilter_literal) < 3:
            raise ValueError(f"prefilter_literal must be ≥3 chars, got: {self.prefilter_literal}")
        if not re.match(r'^[a-z0-9_.-]+$', self.rule_id):
            raise ValueError(f"Invalid rule_id format: {self.rule_id}")


@dataclass 
class PrefilterMetrics:
    """Performance metrics for prefiltering"""
    construction_time_ms: float
    index_size_bytes: int
    total_rules: int
    unique_literals: int
    avg_literal_length: float
    
    # Runtime metrics (per query)
    query_time_ms: float = 0.0
    prefilter_hits: int = 0
    rules_evaluated: int = 0
    efficiency_ratio: float = 0.0  # rules_evaluated / total_rules


class AhoCorasickPrefilter:
    """
    High-performance Aho-Corasick based prefiltering for intent rules.
    
    Features:
    - Case-insensitive, Unicode-normalized matching
    - Rule priority awareness for deterministic ordering
    - Performance monitoring and metrics collection
    - Memory-efficient construction and querying
    """
    
    def __init__(self):
        self._automaton: Optional[ahocorasick.Automaton] = None
        self._rule_mapping: Dict[str, List[PrefilterRule]] = {}
        self._metrics: Optional[PrefilterMetrics] = None
        self._is_built = False
        
    def add_rules(self, rules: List[PrefilterRule]) -> None:
        """
        Add rules to the prefilter index.
        
        Args:
            rules: List of prefilter rules to add
            
        Raises:
            ValueError: If rules have invalid format or duplicates
        """
        if self._is_built:
            raise RuntimeError("Cannot add rules after automaton is built")
            
        # Validate and normalize rules
        normalized_rules = []
        seen_ids = set()
        
        for rule in rules:
            if rule.rule_id in seen_ids:
                raise ValueError(f"Duplicate rule_id: {rule.rule_id}")
            seen_ids.add(rule.rule_id)
            
            # Normalize prefilter literal
            normalized_literal = self._normalize_text(rule.prefilter_literal)
            normalized_rule = PrefilterRule(
                rule_id=rule.rule_id,
                prefilter_literal=normalized_literal,
                priority=rule.priority,
                lang=rule.lang
            )
            normalized_rules.append(normalized_rule)
            
        # Group rules by normalized literal
        for rule in normalized_rules:
            literal = rule.prefilter_literal
            if literal not in self._rule_mapping:
                self._rule_mapping[literal] = []
            self._rule_mapping[literal].append(rule)
            
        logger.info(f"Added {len(normalized_rules)} rules, {len(self._rule_mapping)} unique literals")
    
    def build(self) -> PrefilterMetrics:
        """
        Build the Aho-Corasick automaton from added rules.
        
        Returns:
            Construction metrics
            
        Raises:
            RuntimeError: If no rules were added or already built
        """
        if self._is_built:
            raise RuntimeError("Automaton already built")
        if not self._rule_mapping:
            raise RuntimeError("No rules added")
            
        start_time = time.perf_counter()
        
        # Create automaton
        self._automaton = ahocorasick.Automaton()
        
        # Add patterns
        for literal, rules in self._rule_mapping.items():
            # Sort rules by priority (descending) for deterministic ordering
            sorted_rules = sorted(rules, key=lambda r: (-r.priority, r.rule_id))
            self._automaton.add_word(literal, sorted_rules)
        
        # Make automaton
        self._automaton.make_automaton()
        self._is_built = True
        
        construction_time = (time.perf_counter() - start_time) * 1000
        
        # Calculate metrics
        all_rules = [rule for rules in self._rule_mapping.values() for rule in rules]
        total_literal_length = sum(len(rule.prefilter_literal) for rule in all_rules)
        avg_literal_length = total_literal_length / len(all_rules) if all_rules else 0
        
        self._metrics = PrefilterMetrics(
            construction_time_ms=construction_time,
            index_size_bytes=len(str(self._automaton)),  # Approximation
            total_rules=len(all_rules),
            unique_literals=len(self._rule_mapping),
            avg_literal_length=avg_literal_length
        )
        
        logger.info(f"Built Aho-Corasick automaton: {self._metrics.total_rules} rules, "
                   f"{self._metrics.unique_literals} literals, {construction_time:.2f}ms")
        
        return self._metrics
    
    def prefilter(self, text: str, lang: Optional[str] = None) -> Tuple[Set[str], Dict[str, any]]:
        """
        Find rules whose prefilter_literal matches in the input text.
        
        Args:
            text: Input text to search
            lang: Language filter (optional)
            
        Returns:
            Tuple of (matched_rule_ids, query_metrics)
            
        Raises:
            RuntimeError: If automaton not built
        """
        if not self._is_built or self._automaton is None:
            raise RuntimeError("Automaton not built. Call build() first.")
            
        start_time = time.perf_counter()
        
        # Normalize input text
        normalized_text = self._normalize_text(text)
        
        # Find matches
        matched_rules = set()
        prefilter_hits = 0
        
        for end_index, rules_list in self._automaton.iter(normalized_text):
            prefilter_hits += 1
            
            # Apply language filter
            for rule in rules_list:
                if lang is None or rule.lang == lang:
                    matched_rules.add(rule.rule_id)
        
        query_time = (time.perf_counter() - start_time) * 1000
        
        # Calculate efficiency
        efficiency = len(matched_rules) / self._metrics.total_rules if self._metrics else 0
        
        metrics = {
            "query_time_ms": query_time,
            "prefilter_hits": prefilter_hits,
            "rules_evaluated": len(matched_rules),
            "efficiency_ratio": efficiency,
            "input_length": len(text),
            "normalized_length": len(normalized_text)
        }
        
        logger.debug(f"Prefilter: {len(matched_rules)}/{self._metrics.total_rules} rules "
                    f"({efficiency:.1%} efficiency) in {query_time:.2f}ms")
        
        return matched_rules, metrics
    
    def get_metrics(self) -> Optional[PrefilterMetrics]:
        """Get construction metrics"""
        return self._metrics
    
    def get_rule_count(self) -> int:
        """Get total number of rules in index"""
        return self._metrics.total_rules if self._metrics else 0
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for consistent matching.
        
        Normalization steps:
        1. Unicode NFKD normalization
        2. Convert to lowercase
        3. Remove combining marks (diacritics)
        4. Strip leading/trailing whitespace
        
        Args:
            text: Input text
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
            
        # Unicode normalization
        normalized = unicodedata.normalize('NFKD', text)
        
        # Remove diacritics (combining characters)
        no_diacritics = ''.join(
            char for char in normalized 
            if not unicodedata.combining(char)
        )
        
        # Convert to lowercase and strip
        return no_diacritics.lower().strip()


class PrefilterFactory:
    """Factory for creating prefilter instances"""
    
    @staticmethod
    def create_prefilter(engine: PrefilterEngine = PrefilterEngine.AHOCORASICK) -> AhoCorasickPrefilter:
        """
        Create a prefilter instance.
        
        Args:
            engine: Prefiltering engine to use
            
        Returns:
            Prefilter instance
        """
        if engine == PrefilterEngine.AHOCORASICK:
            return AhoCorasickPrefilter()
        else:
            raise NotImplementedError(f"Engine {engine} not implemented")


# Utility functions for integration
def load_rules_from_yaml(yaml_path: str) -> List[PrefilterRule]:
    """
    Load prefilter rules from intent_rules.yaml file.
    
    Args:
        yaml_path: Path to YAML configuration
        
    Returns:
        List of prefilter rules
    """
    import yaml
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    rules = []
    for rule_data in config.get('intents', []):
        rule = PrefilterRule(
            rule_id=rule_data['id'],
            prefilter_literal=rule_data['prefilter_literal'],
            priority=rule_data['priority'],
            lang=rule_data['lang']
        )
        rules.append(rule)
    
    return rules


def build_prefilter_from_yaml(yaml_path: str) -> AhoCorasickPrefilter:
    """
    Build complete prefilter from YAML configuration.
    
    Args:
        yaml_path: Path to intent_rules.yaml
        
    Returns:
        Built prefilter ready for querying
    """
    prefilter = PrefilterFactory.create_prefilter()
    rules = load_rules_from_yaml(yaml_path)
    prefilter.add_rules(rules)
    prefilter.build()
    return prefilter