import json
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import RouteRequestSerializer
from .services import (
    geocode,
    get_osrm_route,
    filter_stations,
    optimal_fuel_stops,
    build_visualization_geojson,
)

class RouteView(APIView):
    def get(self, request):
        serializer = RouteRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            start_addr = serializer.validated_data['start']
            finish_addr = serializer.validated_data['finish']

            # 1. Geocode
            start_coords = geocode(start_addr)
            finish_coords = geocode(finish_addr)

            # 2. Route
            route_poly, total_miles = get_osrm_route(
                start_coords[0], start_coords[1],
                finish_coords[0], finish_coords[1]
            )

            # 3. Filter stations
            stations = filter_stations(route_poly, total_miles)

            # 4. Optimal stops
            stops, total_cost = optimal_fuel_stops(stations, total_miles)

            # 5. Build visualization GeoJSON
            vis_geojson = build_visualization_geojson(route_poly, stops, start_coords, finish_coords)

            #  Optional GeoJSON file download 
            if request.query_params.get('export_geojson', '').lower() in ('true', '1', 'yes'):
                response = HttpResponse(
                    json.dumps(vis_geojson, indent=2),
                    content_type='application/geo+json'
                )
                response['Content-Disposition'] = 'attachment; filename="route_visualization.geojson"'
                return response

            #  Normal JSON response 
            result = {
                'route_map': {
                    'type': 'LineString',
                    'coordinates': route_poly
                },
                'total_distance_miles': round(total_miles, 2),
                'optimal_stops': stops,
                'total_fuel_cost': total_cost,
            }
            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({'error': f"Unexpected error: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)