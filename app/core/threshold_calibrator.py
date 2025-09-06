# app/core/threshold_calibrator.py
"""
Threshold Calibrator - F1 Proxy Optimization para Shadow Traffic

Calibra T_TEMPLATE, T_LLM_RAG, T_LOW baseado em métricas shadow:
- F1 proxy: positivo = boa decisão (alta slot completeness + acordo V1 ou extração superior)
- Constraints: handoff ≤ 3%, p95 latência ≤ baseline+15%
- Bias por stage: thresholds ajustados por quantis por estágio
"""

import json
import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# Optional matplotlib import
try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    plt = None

from .shadow_metrics_collector import shadow_metrics_collector

logger = logging.getLogger(__name__)


@dataclass
class ThresholdConfig:
    """Threshold configuration for routing decisions"""
    T_TEMPLATE: float = 0.74
    T_LLM_RAG: float = 0.60  
    T_LOW: float = 0.38
    
    # Stage-specific biases
    stage_biases: Dict[str, Dict[str, float]] = None
    
    def __post_init__(self):
        if self.stage_biases is None:
            self.stage_biases = {}
    
    def get_threshold(self, threshold_type: str, stage: str = "default") -> float:
        """Get threshold with stage-specific bias applied"""
        
        base_threshold = getattr(self, threshold_type)
        
        if stage in self.stage_biases:
            bias = self.stage_biases[stage].get(threshold_type, 0.0)
            return base_threshold + bias
        
        return base_threshold
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for serialization"""
        return {
            "T_TEMPLATE": self.T_TEMPLATE,
            "T_LLM_RAG": self.T_LLM_RAG, 
            "T_LOW": self.T_LOW,
            "stage_biases": self.stage_biases
        }


@dataclass 
class CalibrationMetrics:
    """Metrics from threshold calibration"""
    precision: float
    recall: float
    f1_score: float
    handoff_rate: float
    p95_latency: float
    disagreement_rate: float
    slot_completeness_rate: float
    
    
class ThresholdCalibrator:
    """
    Calibra thresholds usando métricas shadow com F1 proxy optimization
    """
    
    def __init__(self):
        self.metrics_collector = shadow_metrics_collector
        self.baseline_latency_p95 = 150.0  # ms - will be calculated from data
        
    def calibrate_thresholds(
        self,
        hours_back: int = 24,
        holdout_hours: int = 6,
        save_plots: bool = True
    ) -> ThresholdConfig:
        """
        Calibra thresholds usando dados shadow dos últimas N horas
        
        Args:
            hours_back: Horas de dados para usar
            holdout_hours: Horas finais para hold-out validation
            save_plots: Salvar plots de análise
            
        Returns:
            ThresholdConfig otimizado
        """
        
        logger.info(f"🎯 Starting threshold calibration with {hours_back}h data")
        
        # Load metrics data
        all_samples = self.metrics_collector.load_metrics_for_analysis(hours_back)
        
        if len(all_samples) < 100:
            logger.warning(f"Insufficient data for calibration: {len(all_samples)} samples")
            return self._get_default_thresholds()
        
        # Split training/holdout
        cutoff_idx = len(all_samples) - int(len(all_samples) * (holdout_hours / hours_back))
        train_samples = all_samples[:cutoff_idx]
        holdout_samples = all_samples[cutoff_idx:]
        
        logger.info(f"Training samples: {len(train_samples)}, Holdout: {len(holdout_samples)}")
        
        # Calculate baseline metrics
        self.baseline_latency_p95 = self._calculate_baseline_latency(train_samples)
        
        # Analyze distributions by strategy
        if save_plots:
            self._plot_score_distributions(train_samples)
        
        # Grid search for optimal thresholds
        best_config = self._grid_search_thresholds(train_samples)
        
        # Add stage-specific biases
        best_config = self._add_stage_biases(best_config, train_samples)
        
        # Validate on holdout
        holdout_metrics = self._evaluate_thresholds(best_config, holdout_samples)
        
        # Log results
        self._log_calibration_results(best_config, holdout_metrics)
        
        return best_config
    
    def _calculate_baseline_latency(self, samples: List[Dict]) -> float:
        """Calculate baseline P95 latency from V1 operations"""
        
        latencies = [s["latency_total_ms"] for s in samples if s["latency_total_ms"] > 0]
        
        if not latencies:
            return 150.0  # default fallback
        
        p95 = np.percentile(latencies, 95)
        logger.info(f"📊 Baseline P95 latency: {p95:.1f}ms")
        
        return p95
    
    def _plot_score_distributions(self, samples: List[Dict]):
        """Plot combined_score distributions by strategy buckets"""
        
        if not HAS_MATPLOTLIB:
            logger.info("📈 Matplotlib not available, skipping plots")
            return
        
        try:
            # Group by delivery outcome
            by_outcome = defaultdict(list)
            for s in samples:
                outcome = s["delivery_outcome"]
                combined_score = s["v2_combined_score"]
                if combined_score > 0:  # valid scores only
                    by_outcome[outcome].append(combined_score)
            
            # Create distribution plot
            plt.figure(figsize=(12, 6))
            
            for outcome, scores in by_outcome.items():
                if len(scores) > 5:  # enough data
                    plt.hist(scores, bins=20, alpha=0.6, label=f"{outcome} (n={len(scores)})")
            
            plt.xlabel("Combined Score")
            plt.ylabel("Frequency")
            plt.title("V2 Combined Score Distributions by Delivery Outcome")
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            # Save plot
            plots_dir = Path("shadow_analysis_plots")
            plots_dir.mkdir(exist_ok=True)
            plt.savefig(plots_dir / "score_distributions.png", dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info("📈 Saved score distribution plot")
            
        except Exception as e:
            logger.warning(f"Failed to create distribution plot: {e}")
    
    def _grid_search_thresholds(self, samples: List[Dict]) -> ThresholdConfig:
        """Grid search for optimal thresholds"""
        
        logger.info("🔍 Starting threshold grid search...")
        
        # Threshold ranges to search
        template_range = np.arange(0.60, 0.90, 0.05)
        llm_rag_range = np.arange(0.40, 0.80, 0.05)
        low_range = np.arange(0.20, 0.60, 0.05)
        
        best_f1 = 0.0
        best_config = None
        search_results = []
        
        for t_template in template_range:
            for t_llm_rag in llm_rag_range:
                for t_low in low_range:
                    
                    # Ensure proper ordering
                    if not (t_template > t_llm_rag > t_low):
                        continue
                    
                    config = ThresholdConfig(
                        T_TEMPLATE=t_template,
                        T_LLM_RAG=t_llm_rag,
                        T_LOW=t_low
                    )
                    
                    # Evaluate configuration
                    metrics = self._evaluate_thresholds(config, samples)
                    
                    # Check constraints
                    handoff_ok = metrics.handoff_rate <= 0.03  # ≤3%
                    latency_ok = metrics.p95_latency <= self.baseline_latency_p95 * 1.15  # ≤baseline+15%
                    
                    if handoff_ok and latency_ok and metrics.f1_score > best_f1:
                        best_f1 = metrics.f1_score
                        best_config = config
                    
                    search_results.append({
                        "config": config.to_dict(),
                        "metrics": metrics,
                        "valid": handoff_ok and latency_ok
                    })
        
        logger.info(f"✅ Grid search complete. Best F1: {best_f1:.3f}")
        
        if best_config is None:
            logger.warning("⚠️  No valid configuration found, using defaults")
            return self._get_default_thresholds()
        
        return best_config
    
    def _evaluate_thresholds(self, config: ThresholdConfig, samples: List[Dict]) -> CalibrationMetrics:
        """Evaluate threshold configuration on samples"""
        
        predictions = []
        ground_truth = []
        handoff_count = 0
        latencies = []
        disagreements = 0
        slot_completeness_count = 0
        
        for sample in samples:
            combined_score = sample["v2_combined_score"]
            
            # Apply thresholds to predict strategy
            if combined_score >= config.T_TEMPLATE:
                pred_strategy = "template"
            elif combined_score >= config.T_LLM_RAG:
                pred_strategy = "llm_rag"
            else:
                pred_strategy = "handoff"
                handoff_count += 1
            
            predictions.append(pred_strategy)
            
            # Ground truth based on quality proxy
            quality_positive = sample["quality_proxy_positive"]
            ground_truth.append(quality_positive)
            
            # Collect metrics
            if sample["latency_total_ms"] > 0:
                latencies.append(sample["latency_total_ms"])
            
            if sample["stage_disagreement"]:
                disagreements += 1
            
            if sample["v2_slots_complete"]:
                slot_completeness_count += 1
        
        # Calculate F1 metrics
        true_positives = sum(1 for pred, gt in zip(predictions, ground_truth) 
                           if pred != "handoff" and gt)
        false_positives = sum(1 for pred, gt in zip(predictions, ground_truth) 
                            if pred != "handoff" and not gt)
        false_negatives = sum(1 for pred, gt in zip(predictions, ground_truth) 
                            if pred == "handoff" and gt)
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Other metrics
        handoff_rate = handoff_count / len(samples) if samples else 0.0
        p95_latency = np.percentile(latencies, 95) if latencies else 0.0
        disagreement_rate = disagreements / len(samples) if samples else 0.0
        slot_completeness_rate = slot_completeness_count / len(samples) if samples else 0.0
        
        return CalibrationMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            handoff_rate=handoff_rate,
            p95_latency=p95_latency,
            disagreement_rate=disagreement_rate,
            slot_completeness_rate=slot_completeness_rate
        )
    
    def _add_stage_biases(self, config: ThresholdConfig, samples: List[Dict]) -> ThresholdConfig:
        """Add stage-specific threshold biases"""
        
        # Group samples by stage
        by_stage = defaultdict(list)
        for sample in samples:
            stage = sample["v2_next_stage"]
            combined_score = sample["v2_combined_score"]
            if combined_score > 0:
                by_stage[stage].append(combined_score)
        
        # Calculate stage-specific quantiles
        stage_biases = {}
        
        for stage, scores in by_stage.items():
            if len(scores) < 20:  # insufficient data
                continue
            
            # Calculate quantiles
            q75 = np.percentile(scores, 75)
            q50 = np.percentile(scores, 50)
            
            # Scheduling tends to have higher scores → threshold adjustment
            if stage == "scheduling" and q75 > config.T_TEMPLATE:
                stage_biases[stage] = {
                    "T_TEMPLATE": min(0.05, q75 - config.T_TEMPLATE),
                    "T_LLM_RAG": 0.02,
                    "T_LOW": 0.0
                }
            # Greeting tends to have lower scores → threshold adjustment
            elif stage == "greeting" and q50 < config.T_LLM_RAG:
                stage_biases[stage] = {
                    "T_TEMPLATE": -0.02,
                    "T_LLM_RAG": -0.03,
                    "T_LOW": -0.02
                }
        
        config.stage_biases = stage_biases
        
        logger.info(f"📊 Added stage biases for {len(stage_biases)} stages")
        
        return config
    
    def _get_default_thresholds(self) -> ThresholdConfig:
        """Get safe default thresholds"""
        return ThresholdConfig(
            T_TEMPLATE=0.74,
            T_LLM_RAG=0.60,
            T_LOW=0.38
        )
    
    def _log_calibration_results(self, config: ThresholdConfig, holdout_metrics: CalibrationMetrics):
        """Log calibration results"""
        
        logger.info("🎯 THRESHOLD CALIBRATION RESULTS")
        logger.info("=" * 50)
        logger.info(f"T_TEMPLATE: {config.T_TEMPLATE:.3f}")
        logger.info(f"T_LLM_RAG: {config.T_LLM_RAG:.3f}")
        logger.info(f"T_LOW: {config.T_LOW:.3f}")
        
        if config.stage_biases:
            logger.info(f"Stage biases: {len(config.stage_biases)} stages")
        
        logger.info("")
        logger.info("📊 HOLDOUT VALIDATION METRICS")
        logger.info(f"F1 Score: {holdout_metrics.f1_score:.3f}")
        logger.info(f"Precision: {holdout_metrics.precision:.3f}")
        logger.info(f"Recall: {holdout_metrics.recall:.3f}")
        logger.info(f"Handoff Rate: {holdout_metrics.handoff_rate:.1%} (target ≤3%)")
        logger.info(f"P95 Latency: {holdout_metrics.p95_latency:.1f}ms (baseline: {self.baseline_latency_p95:.1f}ms)")
        logger.info(f"Disagreement Rate: {holdout_metrics.disagreement_rate:.1%}")
        logger.info(f"Slot Completeness: {holdout_metrics.slot_completeness_rate:.1%}")
    
    def save_calibration_config(self, config: ThresholdConfig, filepath: str = "calibrated_thresholds.json"):
        """Save calibrated configuration to file"""
        
        try:
            config_dict = config.to_dict()
            config_dict["calibration_timestamp"] = datetime.now().isoformat()
            config_dict["baseline_latency_p95"] = self.baseline_latency_p95
            
            with open(filepath, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            logger.info(f"✅ Saved calibrated thresholds to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save calibration config: {e}")
    
    def load_calibration_config(self, filepath: str = "calibrated_thresholds.json") -> Optional[ThresholdConfig]:
        """Load calibrated configuration from file"""
        
        try:
            with open(filepath, 'r') as f:
                config_dict = json.load(f)
            
            config = ThresholdConfig(
                T_TEMPLATE=config_dict["T_TEMPLATE"],
                T_LLM_RAG=config_dict["T_LLM_RAG"],
                T_LOW=config_dict["T_LOW"],
                stage_biases=config_dict.get("stage_biases", {})
            )
            
            logger.info(f"✅ Loaded calibrated thresholds from {filepath}")
            return config
            
        except Exception as e:
            logger.warning(f"Failed to load calibration config: {e}")
            return None


# Global instance
threshold_calibrator = ThresholdCalibrator()