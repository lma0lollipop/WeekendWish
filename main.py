import streamlit as st
from dotenv import load_dotenv
import os

from api import (
    geocode_address,
    fsq_search_places,
    fetch_photos_for_top_places
)

from planner import generate_itinerary_from_selected

load_dotenv()

# Optional AI
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_KEY:
    from openai import OpenAI
    ai_client = OpenAI()
else:
    ai_client = None

def cli_log(*args):
    print("[CLI]", *args)


# -------------------------------------------------------
# Streamlit Setup
# -------------------------------------------------------
st.set_page_config(page_title="WeekendWish", page_icon="🧭", layout="wide")
st.title("🧭 WeekendWish — Smart Pune Day Planner")


# -------------------------------------------------------
# Caching (prevents repeated FSQ calls → stops 429)
# -------------------------------------------------------
@st.cache_data(ttl=600)
def cached_fsq_search(lat, lon):
    return fsq_search_places(lat, lon, radius=8000, limit=10)


# -------------------------------------------------------
# Session State
# -------------------------------------------------------
if "selected_places" not in st.session_state:
    st.session_state.selected_places = []

if "last_search_results" not in st.session_state:
    st.session_state.last_search_results = []


# -------------------------------------------------------
# Step 1 — User Inputs
# -------------------------------------------------------
st.subheader("Step 1: Trip Details")

col1, col2 = st.columns(2)

with col1:
    budget = st.number_input("Total Budget (₹)", min_value=200, max_value=20000, value=2000)

with col2:
    people = st.number_input("People", min_value=1, max_value=20, value=2)

address = st.text_input("Starting Address", placeholder="e.g. FC Road, Viman Nagar…")

search_btn = st.button("Search Places")


# -------------------------------------------------------
# Step 2 — Search FSQ
# -------------------------------------------------------
if search_btn:
    if not address:
        st.error("Enter an address first.")
    else:
        lat, lon = geocode_address(address)

        if lat is None:
            st.error("Couldn't find that address.")
        else:
            st.success("Location found!")

            places_raw = cached_fsq_search(lat, lon)

            normalized = []

            for p in places_raw:
                loc = p.get("location", {})
                plat = loc.get("latitude")
                plon = loc.get("longitude")
                if plat is None:
                    continue

                normalized.append({
                    "fsq_place_id": p.get("fsq_place_id"),
                    "name": p.get("name", "Unknown Place"),
                    "categories": [c.get("name", "") for c in p.get("categories", [])],
                    "lat": float(plat),
                    "lon": float(plon),
                    "price_tier": p.get("price"),
                    "popularity": p.get("popularity", 0.5),
                    "photo_url": None
                })

            fetch_photos_for_top_places(normalized, top_n=8)
            st.session_state.last_search_results = normalized


# -------------------------------------------------------
# Step 3 — Display Cards
# -------------------------------------------------------
if st.session_state.last_search_results:
    st.subheader("Step 2: Select Places")

    places = st.session_state.last_search_results
    cols = st.columns(3)

    for idx, place in enumerate(places):
        col = cols[idx % 3]
        with col:
            with st.container(border=True):
                st.image(
                    place["photo_url"] or "https://via.placeholder.com/400x250?text=No+Image",
                    use_column_width=True
                )

                st.markdown(f"### {place['name']}")
                st.caption(", ".join(place["categories"]))

                if place["price_tier"]:
                    st.write(f"💰 Price Tier: {place['price_tier']}")

                if st.button("Select", key=place["fsq_place_id"]):
                    st.session_state.selected_places.append(place)
                    st.success(f"Added {place['name']}")

    if st.session_state.selected_places:
        st.markdown("### Selected Places:")
        for p in st.session_state.selected_places:
            st.write("•", p["name"])


# -------------------------------------------------------
# Step 4 — Generate Itinerary
# -------------------------------------------------------
if st.session_state.selected_places:
    st.subheader("Step 3: Generate Itinerary")

    if st.button("Generate Journey"):
        lat, lon = geocode_address(address)

        itinerary = generate_itinerary_from_selected(
            st.session_state.selected_places,
            lat,
            lon,
            budget,
            people
        )

        if not itinerary:
            st.error("Couldn't generate itinerary — try selecting more places.")
        else:
            st.success("Here is your itinerary!")

            for idx, step in enumerate(itinerary, start=1):
                st.markdown(f"## Stop {idx}: {step['name']}")
                st.write(f"Category: {', '.join(step['categories'])}")
                st.write(f"Cost: ₹{step['cost']}")
                st.write(f"Travel Time: {step['travel_time']:.1f} min")
                st.write(f"Duration: {step['duration']} min")

                if step.get("photo_url"):
                    st.image(step["photo_url"], width=400)

            if ai_client:
                st.subheader("🧠 AI Summary")
                summary = ai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": "Summarize this itinerary: " +
                                        ", ".join([i["name"] for i in itinerary])
                        }
                    ]
                )
                st.write(summary.choices[0].message["content"])
