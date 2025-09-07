"""
Data models for contribution records and evaluation results.
"""

class Contribution:
    """
    Represents a single contribution from any source.
    """
    def __init__(self, source: str, type: str, description: str, date: str, complexity: int, time_spent: float, bugs_reported: int):
        self.source = source
        self.type = type
        self.description = description
        self.date = date
        self.complexity = complexity
        self.time_spent = time_spent
        self.bugs_reported = bugs_reported

class EvaluationResult:
    """
    Represents the evaluation summary for a user.
    """
    def __init__(self, involvement: float, significance: float, effectiveness: float, complexity: float, time_required: float, bugs_and_fixes: int):
        self.involvement = involvement
        self.significance = significance
        self.effectiveness = effectiveness
        self.complexity = complexity
        self.time_required = time_required
        self.bugs_and_fixes = bugs_and_fixes

    def __str__(self):
        return (f"Involvement: {self.involvement}\nSignificance: {self.significance}\nEffectiveness: {self.effectiveness}\nComplexity: {self.complexity}\nTime Required: {self.time_required}\nBugs and Fixes: {self.bugs_and_fixes}")

