"""Veyron security layer.

Path policy, command policy, audit log, confirmation flow, and safety policies.
Every privileged action goes through here. See ARCHITECTURE.md §7.
"""

from veyron.security.command_policy import PermissionLevel, classify_command
from veyron.security.path_policy import PathPolicyError, validate_path
from veyron.security.policy import (
    ApprovalMode,
    RiskLevel,
    SafetyPolicy,
    classify_risk,
    get_safety_policy,
)

__all__ = [
    "PermissionLevel",
    "RiskLevel",
    "ApprovalMode",
    "classify_command",
    "classify_risk",
    "validate_path",
    "PathPolicyError",
    "SafetyPolicy",
    "get_safety_policy",
]
