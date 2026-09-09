# app/utils/feed_utils.py
import math
import numpy as np
from typing import Dict, List, Set, Any
from app.schemas.feed import TrackImpressionRequest


def calculate_time_decay(age_hours: float, validity: str) -> float:
    if validity == "breaking-news":
        if age_hours > 24: return 0.0
        return math.exp(- (math.log(2) / 6.0) * age_hours)
    elif validity == "daily-news":
        if age_hours > 90: return 0.0
        return math.exp(- (math.log(2) / 24.0) * age_hours)
    return 1.0  # evergreen


def calculate_interaction_scores(request: TrackImpressionRequest) -> Dict[int, float]:
    alpha_scores: Dict[int, float] = {}
    for item in request.interactions:
        alpha = 0.0
        if "hide" in item.actions:
            alpha = -1.0
        else:
            if "like" in item.actions: alpha += 0.4
            if "bookmark" in item.actions: alpha += 0.4
            if "share" in item.actions: alpha += 0.3
            if "read_more" in item.actions: alpha += 0.2

            if item.duration > 10:
                duration_score = (item.duration // 10) * 0.1
                alpha += min(0.3, duration_score)

            if not item.actions and item.duration <= 3:
                alpha -= 0.05

        alpha = max(-1.0, min(1.0, alpha))
        if alpha != 0.0:
            alpha_scores[item.news_id] = alpha

    return alpha_scores


def compute_new_vector(
        current_vector: List[float],
        alpha_scores: Dict[int, float],
        points: List[Any],
        news_tags_map: Dict[int, Set[str]],
        user_tags: Set[str]
) -> List[float]:
    new_vector = np.array(current_vector, dtype=np.float32)

    for point in points:
        alpha = alpha_scores.get(point.id, 0)
        news_vector = np.array(point.vector, dtype=np.float32)
        article_tags = news_tags_map.get(point.id, set())

        if user_tags and article_tags and user_tags.intersection(article_tags):
            gamma = 0.30
        elif user_tags:
            gamma = 0.08
        else:
            gamma = 0.15

        new_vector = (1 - gamma) * new_vector + (gamma * alpha * news_vector)

    norm = np.linalg.norm(new_vector)
    if norm > 0:
        new_vector = new_vector / norm

    return new_vector.tolist()