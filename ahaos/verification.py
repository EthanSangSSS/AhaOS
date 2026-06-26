from __future__ import annotations

from .models import InsightCandidate


TRUST_SCORE = {
    "verified_telemetry": 1.0,
    "first_party_file": 0.85,
    "user_statement": 0.7,
    "model_inference": 0.35,
    "untrusted_external": 0.2,
}


def evidence_score(candidate: InsightCandidate) -> float:
    if not candidate.evidence:
        return 0.0
    scores = [TRUST_SCORE.get(item.trust_level, 0.4) for item in candidate.evidence]
    return sum(scores) / len(scores)


def verify_candidate(candidate: InsightCandidate, require_evidence: bool = True) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if not candidate.claim.strip():
        errors.append("missing claim")
    if require_evidence:
        if not candidate.evidence:
            errors.append("missing evidence")
        if evidence_score(candidate) < 0.45:
            errors.append("evidence score too low")
        if candidate.evidence and all(item.trust_level == "model_inference" for item in candidate.evidence):
            errors.append("model inference cannot be the only evidence")
            
    if not candidate.recommended_action.strip():
        errors.append("missing recommended_action")
    if not candidate.do_not_do.strip():
        errors.append("missing do_not_do boundary")
    if candidate.risk > 0.35:
        errors.append("risk too high for delivery")
    if candidate.actionability < 0.6:
        errors.append("actionability too low")

    return not errors, errors


def filter_verified(candidates: list[InsightCandidate], require_evidence: bool = True) -> list[InsightCandidate]:
    verified: list[InsightCandidate] = []
    for candidate in candidates:
        ok, _ = verify_candidate(candidate, require_evidence=require_evidence)
        if ok:
            verified.append(candidate)
    return verified
