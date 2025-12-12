"""
planner.py
Logic for scoring places and generating a journey
ONLY from the user-selected cards.

This file does NOT call any external APIs.
It receives:
- selected places (list of dicts from API layer)
- starting coords (lat/lon)
- budget, people count

Returns:
- A clean ordered itinerary list
"""

from geopy.distance import geodesic


# -----------------------------------------
# Distance + Travel Time
# -----------------------------------------
def distance_km(lat1, lon1, lat2, lon2):
    return geodesic((lat1, lon1), (lat2, lon2)).km


def travel_time_min(lat1, lon1, lat2, lon2, speed=20):
    """Approx travel time at average Pune city speed."""
    dist = distance_km(lat1, lon1, lat2, lon2)
    return (dist / speed) * 60


# -----------------------------------------
# Scoring Function
# -----------------------------------------
def compute_score(place, budget_per_person, travel_min):
    """
    Score based on:
    - popularity
    - cost alignment to budget
    - travel time penalty
    """

    popularity = place.get("popularity", 0.6)

    # price_tier: 1 = cheap, 2 = moderate, 3 = costly, 4 = expensive
    price_tier = place.get("price_tier", 2)

    # map FSQ price tier to approximate INR cost per person
    approx_cost = {
        1: 200,
        2: 400,
        3: 800,
        4: 1200
    }.get(price_tier, 400)

    # how well the place fits within budget
    cost_factor = max(0, (budget_per_person - approx_cost) / max(1, budget_per_person))

    # travel time penalty (more time = lower score)
    travel_penalty = travel_min / 30  # normalized approx

    score = (
        0.5 * popularity +
        0.3 * cost_factor -
        0.2 * travel_penalty
    )

    return score, approx_cost


# -----------------------------------------
# MAIN — Generate Journey From Selected Places
# -----------------------------------------
def generate_itinerary_from_selected(selected_places, start_lat, start_lon, total_budget, people):
    """
    selected_places: list of dicts from Foursquare (each normalized in main/ui)
    start_lat, start_lon: starting coordinates from geocoded user address
    total_budget: user's total budget (INR)
    people: number of people
    """

    if not selected_places:
        return []

    # -----------------------------------------
    # 1) Precompute travel time + score for each selected place
    # -----------------------------------------

    budget_per_person = total_budget / max(1, people)

    enriched = []
    for p in selected_places:

        plat, plon = p["lat"], p["lon"]

        travel_min = travel_time_min(start_lat, start_lon, plat, plon)
        score, approx_cost_pp = compute_score(p, budget_per_person, travel_min)

        enriched.append({
            **p,
            "travel_from_start": travel_min,
            "score": score,
            "approx_cost_pp": approx_cost_pp
        })

    # Sort by score (best first)
    enriched.sort(key=lambda x: x["score"], reverse=True)

    # -----------------------------------------
    # 2) Greedy itinerary building
    # -----------------------------------------
    itinerary = []
    remaining_budget = total_budget
    current_lat, current_lon = start_lat, start_lon
    total_minutes_used = 0
    MAX_MINUTES = 8 * 60  # 8 hours trip

    for p in enriched:
        # cost per person * people
        total_cost = p["approx_cost_pp"] * people
        if total_cost > remaining_budget:
            continue

        travel_min = travel_time_min(current_lat, current_lon, p["lat"], p["lon"])

        visit_duration = estimate_visit_duration(p)

        # time check
        if total_minutes_used + travel_min + visit_duration > MAX_MINUTES:
            continue

        # add to itinerary
        itinerary.append({
            "name": p["name"],
            "categories": p.get("categories", []),
            "photo_url": p.get("photo_url"),
            "cost": total_cost,
            "travel_time": travel_min,
            "duration": visit_duration,
            "lat": p["lat"],
            "lon": p["lon"]
        })

        # update state
        remaining_budget -= total_cost
        total_minutes_used += travel_min + visit_duration
        current_lat, current_lon = p["lat"], p["lon"]  # move to next start

    return itinerary


# -----------------------------------------
# Visit Duration Estimate (By Category)
# -----------------------------------------
def estimate_visit_duration(place):
    cats = [c.lower() for c in place.get("categories", [])]

    if any("park" in c or "garden" in c for c in cats):
        return 60
    if any("cafe" in c for c in cats):
        return 45
    if any("restaurant" in c for c in cats):
        return 75
    if any("mall" in c for c in cats):
        return 120
    if any("museum" in c for c in cats):
        return 60
    if any("adventure" in c or "amusement" in c for c in cats):
        return 90

    return 45  # default
