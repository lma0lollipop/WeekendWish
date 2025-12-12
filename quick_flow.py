# quick_flow.py (example)
from extras import geocode_address, fsq_search_places, fsq_get_photo_url, travel_time_min
from planner import normalize_fsq_place
start_addr = "FC Road, Pune"
lat, lon = geocode_address(start_addr)

places = fsq_search_places(lat, lon, radius=8000, limit=40)
rows = []
for p in places:
    r = normalize_fsq_place(p)
    r['distance_km'] = distance_km(lat, lon, r['lat'], r['lon'])
    r['travel_min'] = travel_time_min(lat, lon, r['lat'], r['lon'])
    r['image'] = fsq_get_photo_url(r['fsq_id'])
    rows.append(r)

# Now rows is a list of dicts you can present as cards in Streamlit
