import requests
from django.contrib.gis.geos import LineString
from django.contrib.gis.db.models.functions import LineLocatePoint
from django.contrib.gis.measure import D
from .models import TruckStop

#  FREE EXTERNAL APIs 
OSRM_BASE = "https://router.project-osrm.org"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

#  VEHICLE CONSTANTS 
MAX_RANGE_MILES = 500.0
MPG = 10.0
TANK_GALLONS = MAX_RANGE_MILES / MPG   # 50 gallons

def geocode(address):
    """Convert address string to (lng, lat, country)."""
    resp = requests.get(
        NOMINATIM_URL,
        params={
            'q': address,
            'format': 'json', 'limit': 1,
            'addressdetails': 1
        },
        headers={'User-Agent': 'SpotterAPI/1.0 (your@email.com)'},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"Could not geocode: {address}")
    country = data[0].get('address', {}).get('country', '')
    return float(data[0]['lon']), float(data[0]['lat']), country

def get_osrm_route(start_lng, start_lat, end_lng, end_lat):
    """Call OSRM, return polyline (GeoJSON coords) and distance in miles."""
    url = f"{OSRM_BASE}/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}"
    params = {'overview': 'full', 'geometries': 'geojson', 'steps': 'false'}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data['code'] != 'Ok':
        raise RuntimeError("OSRM routing failed")
    route = data['routes'][0]
    distance_m = route['distance']
    polyline = route['geometry']['coordinates']
    return polyline, distance_m * 0.000621371   # miles

def filter_stations(polyline, total_miles, corridor_miles=10):
    """
    Find TruckStops within `corridor_miles` of the route, project them onto the route,
    and return a sorted list of dicts.
    """
    route_line = LineString(polyline, srid=4326)
    qs = TruckStop.objects.filter(
        location__distance_lte=(route_line, D(mi=corridor_miles)),
        location__isnull=False
    ).annotate(
        route_fraction=LineLocatePoint(route_line, 'location')
    ).order_by('route_fraction')

    raw = []
    for s in qs:
        dist_along = s.route_fraction * total_miles
        raw.append({
            'dist': dist_along,
            'price': s.price,
            'name': s.name,
            'city': s.city,
            'state': s.state,
            'lat': s.location.y,
            'lng': s.location.x,
        })

    # Keep only cheapest price at each (lat, lng)
    seen = {}
    for s in sorted(raw, key=lambda x: x['dist']):
        key = (round(s['lat'], 5), round(s['lng'], 5))
        if key not in seen or s['price'] < seen[key]['price']:
            seen[key] = s
    return sorted(seen.values(), key=lambda x: x['dist'])


def _stations_have_gap(stations, total_miles):
    """Return True if any consecutive stations are more than MAX_RANGE_MILES apart."""
    if not stations:
        return True
    prev = 0.0
    for s in stations:
        if s['dist'] - prev > MAX_RANGE_MILES:
            return True
        prev = s['dist']
    if total_miles - prev > MAX_RANGE_MILES:
        return True
    return False


def find_stations_robust(route_poly, total_miles):
    """
    Find stations with a progressively wider corridor until no 500‑mile gaps exist.
    Returns the station list.
    """
    for width in (10, 15, 20, 30, 50):   # try increasingly generous buffers
        stations = filter_stations(route_poly, total_miles, corridor_miles=width)
        if not _stations_have_gap(stations, total_miles):
            return stations
    # If even 50 miles fails, raise an error – truly impossible
    raise RuntimeError("Impossible route – gap > 500 miles between stations even with wide corridor")


def optimal_fuel_stops(stations, total_miles):
    """
    Provably optimal greedy algorithm.
    stations: sorted list of dicts with keys 'dist', 'price', 'name', ...
    total_miles: total route distance.
    """
    # Virtual start (free full tank) and destination
    stations = stations.copy()  # avoid mutating the caller's list
    stations.insert(0, {
        'dist': 0.0, 'price': 0.0,    # price 0 because starting fuel is free
        'name': 'Start', 'city': '', 'state': '', 'lat': None, 'lng': None
    })
    stations.append({
        'dist': total_miles, 'price': 0.0,
        'name': 'Destination', 'city': '', 'state': '', 'lat': None, 'lng': None
    })

    fuel = TANK_GALLONS        # current gallons in tank (free at start)
    total_cost = 0.0
    chosen_stops = []
    i = 0
    n = len(stations)

    while i < n - 1:
        dist_i   = stations[i]['dist']
        price_i  = stations[i]['price']

        # All stations reachable from i (fuel range not limiting because we can buy here)
        reachable = []
        for j in range(i + 1, n):
            if stations[j]['dist'] - dist_i <= MAX_RANGE_MILES:
                reachable.append(j)
            else:
                break

        if not reachable:
            raise RuntimeError("Impossible route – gap > 500 miles between stations")

        #  Destination directly reachable?
        if stations[reachable[-1]]['dist'] == total_miles:
            needed = (total_miles - dist_i) / MPG
            if fuel < needed:
                buy = needed - fuel
                total_cost += buy * price_i
                chosen_stops.append(make_stop(stations[i], buy, price_i))
            break

        #  Find the nearest station with price < price_i
        cheaper_idx = None
        for j in reachable:
            if stations[j]['price'] < price_i:
                cheaper_idx = j
                break

        if cheaper_idx is not None:
            # Drive to the nearest cheaper station, buying only enough fuel to get there
            target = cheaper_idx
            needed = (stations[target]['dist'] - dist_i) / MPG
            if fuel < needed:
                buy = needed - fuel
                total_cost += buy * price_i
                chosen_stops.append(make_stop(stations[i], buy, price_i))
                fuel = needed
            fuel -= needed
            i = target
        else:
            # No cheaper station ahead → we are at the cheapest in this window.
            # Fill the tank to maximum (to avoid buying more expensive later) and
            # go to the FARTHEST station among those with the MINIMUM price.
            min_price = min(stations[j]['price'] for j in reachable)

            # Pick the farthest station with this minimum price
            target = None
            for j in reversed(reachable):
                if stations[j]['price'] == min_price:
                    target = j
                    break

            needed = (stations[target]['dist'] - dist_i) / MPG

            # Fill tank to max (only if we have to buy anything)
            buy = TANK_GALLONS - fuel
            if buy > 0:
                total_cost += buy * price_i
                chosen_stops.append(make_stop(stations[i], buy, price_i))
                fuel = TANK_GALLONS

            fuel -= needed
            i = target

    return chosen_stops, round(total_cost, 2)


def make_stop(station, gallons, price):
    return {
        'station_name': station['name'],
        'city': station['city'],
        'state': station['state'],
        'coordinates': [station['lat'], station['lng']] if station['lat'] else None,
        'gallons_purchased': round(gallons, 2),
        'price_per_gallon': price,
        'cost_at_stop': round(gallons * price, 2),
    }


def compute_route(start_addr, finish_addr):
    """Main pipeline: geocode → route → stations → optimal plan."""
    # 1. Geocode (2 API calls) – now returns country as well
    start_lng, start_lat, _ = geocode(start_addr)
    finish_lng, finish_lat, _ = geocode(finish_addr)

    # 2. Get route (1 API call)
    route_poly, total_miles = get_osrm_route(
        start_lng, start_lat,
        finish_lng, finish_lat
    )

    # 3. Find stations with robust corridor widening
    stations = find_stations_robust(route_poly, total_miles)

    # 4. Optimal fuel plan
    stops, total_cost = optimal_fuel_stops(stations, total_miles)

    return {
        'route_map': {
            'type': 'LineString',
            'coordinates': route_poly
        },
        'total_distance_miles': round(total_miles, 2),
        'optimal_stops': stops,
        'total_fuel_cost': total_cost,
    }


def build_visualization_geojson(route_polyline, stops, start_coords, finish_coords):
    """
    Create a GeoJSON FeatureCollection with:
      - blue LineString for the route
      - green marker at the start
      - black‑and‑white checkered marker at the finish
      - red fuel‑pump markers at each optimal stop
    """
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": route_polyline   # [lng, lat]
            },
            "properties": {
                "stroke": "#3388ff",
                "stroke-width": 4
            }
        },
        #  Start marker (green flag)
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": start_coords  # [lng, lat]
            },
            "properties": {
                "marker-color": "#00cc00",
                "marker-symbol": "marker",
                "title": "Start"
            }
        },
        #  Finish marker (black/white checkered flag)
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": finish_coords  # [lng, lat]
            },
            "properties": {
                "marker-color": "#000000",
                "marker-symbol": "star",
                "title": "Finish"
            }
        }
    ]

    # Fuel stops (red pumps) 
    stop_coords = []
    for s in stops:
        if s.get('coordinates') and len(s['coordinates']) == 2:
            lat, lng = s['coordinates']
            stop_coords.append([lng, lat])

    if stop_coords:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "MultiPoint",
                "coordinates": stop_coords
            },
            "properties": {
                "marker-color": "#ff0000",
                "marker-symbol": "fuel"
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features
    }