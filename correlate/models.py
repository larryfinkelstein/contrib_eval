"""
Data models for contribution records and evaluation results.
"""

# Removed unused Contribution class (normalize.models.ContributionEvent is the canonical event model).


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
        return (
            f"Involvement: {self.involvement}\n"
            f"Significance: {self.significance}\n"
            f"Effectiveness: {self.effectiveness}\n"
            f"Complexity: {self.complexity}\n"
            f"Time Required: {self.time_required}\n"
            f"Bugs and Fixes: {self.bugs_and_fixes}"
        )
