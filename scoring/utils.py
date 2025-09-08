"""
Scoring utility functions.
Provides weight loading and aggregation helpers used by scoring.metrics.
"""
from typing import Dict, Any, Optional
import os
import importlib.util

# filename used for weight YAML configuration
WEIGHTS_FILENAME = 'weights.yaml'

DEFAULT_WEIGHTS = {
    'involvement': 1.0,
    'significance': 2.0,
    'effectiveness': 1.5,
    'complexity': 1.0,
    'time_required': 0.5,
    'bugs_and_fixes': 2.0,
    'bug_fallout': -1.0,  # negative weight: higher fallout reduces score
    # new metric: average number of status flips per event; negative weight penalizes instability
    'status_instability_avg_flips': -1.0,
}

# default smoothing alpha (1.0 = no smoothing, <1 blends toward baseline)
DEFAULT_SMOOTHING_ALPHA = 1.0


def load_weights(path: Optional[str] = None) -> Dict[str, float]:
    """
    Load metric weights from a YAML file if available, otherwise return defaults.
    The function checks for PyYAML before attempting to import it to avoid import errors.
    """
    if not path:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', WEIGHTS_FILENAME)
    if os.path.exists(path):
        try:
            if importlib.util.find_spec('yaml') is not None:
                import yaml
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                    return {k: float(data.get(k, DEFAULT_WEIGHTS.get(k, 1.0))) for k in DEFAULT_WEIGHTS.keys()}
        except Exception:
            # parsing failed or yaml not usable
            pass
    return DEFAULT_WEIGHTS.copy()


def compute_weighted_score(metrics: Dict[str, Any], weights: Dict[str, float]) -> float:
    """
    Compute a single aggregate score from individual metric values using provided weights.
    Missing metrics are treated as zero.
    """
    total = 0.0
    for k, w in weights.items():
        val = float(metrics.get(k, 0.0) or 0.0)
        total += val * float(w)
    return total


# --- New helpers for time normalization and smoothing ---

def compute_user_time_factors(events: list) -> Dict[str, float]:
    """
    Compute normalization factors per user so that users with unusually high or low
    average time per event are normalized toward the global mean. Returns a mapping
    user_id -> factor where factor multiplies the user's total time_required.

    The factor is computed as: global_avg_time_per_event / user_avg_time_per_event
    with safety clamps to avoid extreme scaling (min 0.5, max 2.0).
    """
    # helper to aggregate per-user time and counts
    def _aggregate_user_times(events_list: list):
        total_time = 0.0
        count = 0
        per_user_local = {}
        for e in events_list:
            meta = getattr(e, 'metadata', {}) or {}
            uid = getattr(e, 'actor_user_id', '') or getattr(e, 'actor', '') or 'unknown'
            t = float(meta.get('time_spent', 0.0) or 0.0)
            per_user_local.setdefault(uid, {'time': 0.0, 'count': 0})
            per_user_local[uid]['time'] += t
            per_user_local[uid]['count'] += 1
            total_time += t
            count += 1
        return total_time, count, per_user_local

    if not events:
        return {}

    total_time, count, per_user = _aggregate_user_times(events)
    if count == 0:
        return {u: 1.0 for u in per_user.keys()}

    global_avg = total_time / count
    factors = {}
    for u, data in per_user.items():
        user_avg = (data['time'] / data['count']) if data['count'] else 0.0
        if user_avg > 0.0:
            factor = global_avg / user_avg
            # clamp
            factor = max(0.5, min(2.0, factor))
        else:
            factor = 1.0
        factors[u] = factor
    return factors


def apply_smoothing(metrics: Dict[str, float], alpha: float = DEFAULT_SMOOTHING_ALPHA, baseline: Dict[str, float] = None) -> Dict[str, float]:
    """
    Apply exponential smoothing toward a baseline for metric values.
    alpha in (0,1]; alpha=1.0 returns metrics unchanged. baseline defaults to zeros.
    """
    if not baseline:
        baseline = {k: 0.0 for k in metrics.keys()}
    if alpha is None:
        alpha = DEFAULT_SMOOTHING_ALPHA
    alpha = float(alpha)
    if alpha >= 1.0:
        return metrics
    smoothed = {}
    for k, v in metrics.items():
        b = float(baseline.get(k, 0.0) or 0.0)
        smoothed[k] = alpha * float(v or 0.0) + (1.0 - alpha) * b
    return smoothed


def load_preset(preset_name: str, path: Optional[str] = None) -> Dict[str, float]:
    """
    Load and return a merged weights mapping for the given preset name.

    Behavior:
    - Loads the base/top-level weights using the same path resolution as load_weights().
    - If the config file contains a 'presets' section and the named preset exists, the
      preset values are merged over the base weights and the merged dict is returned.
    - If the preset is not found, raises a ValueError.

    Example:
        merged = load_preset('quality_focused')

    """
    if not path:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', WEIGHTS_FILENAME)
    base = load_weights(path)
    if not os.path.exists(path):
        raise ValueError(f"Weights config file not found at: {path}")
    # read YAML safely if available
    try:
        if importlib.util.find_spec('yaml') is None:
            raise ValueError('PyYAML not installed; cannot load presets from YAML')
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            doc = yaml.safe_load(f) or {}
    except Exception as ex:
        raise ValueError(f"Failed to load presets from {path}: {ex}")

    presets = doc.get('presets') if isinstance(doc, dict) else None
    if not presets or preset_name not in presets:
        raise ValueError(f"Preset '{preset_name}' not found in {path}")

    preset_map = presets.get(preset_name) or {}
    # merge: preset overrides base
    merged = base.copy()
    for k, v in (preset_map.items() if isinstance(preset_map, dict) else []):
        try:
            merged[k] = float(v)
        except Exception:
            merged[k] = v
    return merged


def list_presets(path: Optional[str] = None) -> list:
    """Return a list of available preset names from the weights YAML (or empty list)."""
    if not path:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', WEIGHTS_FILENAME)
    if not os.path.exists(path):
        return []
    try:
        if importlib.util.find_spec('yaml') is None:
            return []
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            doc = yaml.safe_load(f) or {}
        presets = doc.get('presets') if isinstance(doc, dict) else {}
        return list(presets.keys())
    except Exception:
        return []
