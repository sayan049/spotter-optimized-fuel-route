# Spotter Fuel Route Optimizer

API that computes the cheapest refueling plan for a trip between any two US locations, given a fixed vehicle range of 500 miles, a fuel efficiency of 10 MPG, and a CSV of real truck‑stop fuel prices.

Built with **Django 5**, **Django REST Framework**, and **PostgreSQL/PostGIS**. Routing is powered by the free public OSRM server and geocoding by Nominatim – no API keys required.

---

## Quick Start (Docker)

1. Clone the repository:

   ```bash
   git clone https://github.com/sayan049/spotter-optimized-fuel-route.git
   cd spotter-optimized-fuel-route
(Optional) Set environment variables – create a .env file from the example:

bash
cp .env.example .env
# edit if needed, defaults work for local docker
Start the services:

bash
docker-compose up -d
Run migrations:

bash
docker-compose exec web python manage.py migrate
Load the fuel‑price data (one‑time, may take a few hours due to free geocoding rate limits):

bash
docker-compose exec web python manage.py load_fuel_data fuel-prices-for-be-assessment.csv
The API is now available at http://localhost:8000/api/route/

API Usage
GET /api/route/
Query parameters:

start – start location (e.g. Chicago,IL)

finish – end location (e.g. Houston,TX)

export_geojson (optional) – set to true to download a ready‑to‑view GeoJSON file for geojson.io.

Example (JSON response):

bash
curl "http://localhost:8000/api/route/?start=Chicago,IL&finish=Houston,TX"
Response:

json
{
  "route_map": {
    "type": "LineString",
    "coordinates": [ [ -87.6298, 41.8781 ], … ]
  },
  "total_distance_miles": 1083.41,
  "optimal_stops": [
    {
      "station_name": "QUIKTRIP #7191",
      "city": "Effingham",
      "state": "IL",
      "coordinates": [39.1369746, -88.5607241],
      "gallons_purchased": 20.9,
      "price_per_gallon": 2.999,
      "cost_at_stop": 62.67
    },
    …
  ],
  "total_fuel_cost": 175.74
}
Visualization (instant map)
Add &export_geojson=true to any route request and you’ll download a GeoJSON file that already contains:

Blue route line

Green marker at the starting point

Black star at the destination

Red fuel‑pump markers at every optimal refueling stop

Example:

bash
curl "http://localhost:8000/api/route/?start=Chicago,IL&finish=Houston,TX&export_geojson=true" -o chicago_houston.geojson
Then simply drag the .geojson file onto geojson.io – the complete map will appear instantly.
(You can also do the same from Postman: check the “Send and Download” button or save the response body with a .geojson extension.)

Algorithm
The system uses a provably optimal greedy algorithm for the continuous‑refueling problem with full future price knowledge:

At each station, look ahead 500 miles.

If a cheaper station exists within range, buy only enough fuel to reach the nearest cheaper station.

If no cheaper station exists, fill the tank to maximum and drive to the farthest station with the minimum price (or to the destination if it’s within range).

Total fuel cost is guaranteed to be the absolute minimum achievable given the vehicle constraints and the fuel‑price data.

Project Structure
text
spotter-backend/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── app/
│   ├── manage.py
│   ├── spotter/          # Django project settings
│   └── api/              # Main application
│       ├── models.py
│       ├── services.py   # Geocoding, routing, optimal fuel planner + visualization builder
│       ├── views.py
│       ├── urls.py
│       └── management/commands/
│           └── load_fuel_data.py
└── fuel-prices-for-be-assessment.csv
Tech Stack
Python 3.11, Django 5, Django REST Framework

PostgreSQL 15 + PostGIS (spatial queries)

Free external APIs: OSRM (routing), Nominatim (geocoding)

Docker & Docker Compose

License
This project is built for a technical assessment and is not intended for production use without additional review.