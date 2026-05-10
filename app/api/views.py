from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import RouteRequestSerializer
from .services import compute_route

class RouteView(APIView):
    def get(self, request):
        serializer = RouteRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = compute_route(
                serializer.validated_data['start'],
                serializer.validated_data['finish']
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({'error': f"Unexpected error: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)