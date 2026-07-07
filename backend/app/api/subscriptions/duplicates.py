"""Duplicate-detection endpoint.

Handles: GET /duplicates.
"""

from collections import defaultdict
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.email_message import subscription_emails
from app.models.subscription import Subscription
from app.models.user import User
from app.security.dependencies import get_current_user
from app.services.reference_matching import references_match

router = APIRouter()


def _service_references(sub: Subscription) -> Dict[str, Any]:
    """Return the non-empty ``service_references`` dict for a subscription."""
    metadata = sub.extraction_metadata or {}
    return metadata.get("service_references") or {}


def _cluster_bucket(subs: List[Subscription]) -> List[List[Subscription]]:
    """Split one provider+billing_cycle bucket into duplicate clusters.

    Ref-bearing subscriptions are grouped by connected components: an edge
    links two subs whose non-empty ``service_references`` match (share an
    identical key/value pair), so transitively-overlapping refs land in one
    cluster. Subscriptions with empty/absent refs cannot be disambiguated and
    are collapsed into a single "no-reference" cluster.

    Input ordering (provider, created_at) is preserved for determinism.
    """
    ref_subs = [s for s in subs if _service_references(s)]
    no_ref_subs = [s for s in subs if not _service_references(s)]

    # Connected components over ref-bearing subs via union-find.
    parent = list(range(len(ref_subs)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        root_i, root_j = find(i), find(j)
        if root_i != root_j:
            # Keep the smaller index as root to preserve stable ordering.
            if root_i < root_j:
                parent[root_j] = root_i
            else:
                parent[root_i] = root_j

    for i in range(len(ref_subs)):
        for j in range(i + 1, len(ref_subs)):
            if references_match(
                _service_references(ref_subs[i]), _service_references(ref_subs[j])
            ):
                union(i, j)

    # Group ref subs by component root, keeping first-seen (stable) order.
    components: Dict[int, List[Subscription]] = defaultdict(list)
    for idx, sub in enumerate(ref_subs):
        components[find(idx)].append(sub)

    clusters: List[List[Subscription]] = list(components.values())
    if no_ref_subs:
        clusters.append(no_ref_subs)

    return clusters


def _compute_similar_amounts(subs: List[Subscription]) -> bool:
    """Return True if all non-null amounts fall within 20% of the average."""
    amounts = [float(s.amount) for s in subs if s.amount is not None]
    if len(amounts) <= 1:
        return False

    max_diff = max(amounts) - min(amounts)
    avg_amount = sum(amounts) / len(amounts)
    return (max_diff / avg_amount) < 0.20 if avg_amount > 0 else True


@router.get("/duplicates", response_model=List[dict])
async def find_duplicate_subscriptions(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Find potential duplicate subscriptions for the current user.

    Subscriptions are first bucketed by provider + billing cycle, then each
    bucket is split into clusters so that subscriptions whose non-empty service
    references do not overlap are treated as distinct services (e.g. different
    OVH domains or Twitch channels) and never reported as duplicates.
    """
    # Get all active subscriptions for user
    subscriptions = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id)
        .order_by(Subscription.provider, Subscription.created_at)
        .all()
    )

    # Group by provider and billing cycle
    groups: Dict[str, List[Subscription]] = defaultdict(list)
    for sub in subscriptions:
        # Create grouping key: provider + billing_cycle (or "unknown" if missing)
        key = f"{sub.provider.lower()}_{sub.billing_cycle or 'unknown'}"
        groups[key].append(sub)

    # Within each bucket, split into clusters and report clusters with 2+ subs.
    duplicate_groups = []
    for subs in groups.values():
        for cluster in _cluster_bucket(subs):
            if len(cluster) <= 1:
                continue

            provider = cluster[0].provider
            billing_cycle = cluster[0].billing_cycle

            duplicate_groups.append(
                {
                    "provider": provider,
                    "billing_cycle": billing_cycle,
                    "count": len(cluster),
                    "similar_amounts": _compute_similar_amounts(cluster),
                    "subscriptions": [
                        {
                            "id": str(s.id),
                            "provider": s.provider,
                            "amount": float(s.amount) if s.amount else None,
                            "currency": s.currency,
                            "billing_cycle": s.billing_cycle,
                            "custom_label": s.custom_label,
                            "created_at": s.created_at.isoformat(),
                            "renewal_date": (
                                s.renewal_date.isoformat() if s.renewal_date else None
                            ),
                            "is_active": s.is_active,
                            "email_count": db.query(func.count())
                            .select_from(subscription_emails)
                            .filter(subscription_emails.c.subscription_id == s.id)
                            .scalar(),
                        }
                        for s in cluster
                    ],
                }
            )

    return duplicate_groups
