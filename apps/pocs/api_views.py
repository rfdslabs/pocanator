from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import ProofOfConcept

class PoCCodeAPIView(APIView):
    """
    API view to retrieve PoC code for comparison purposes
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, poc_id):
        poc = get_object_or_404(ProofOfConcept, pk=poc_id)
        
        # Ensure user has access
        if poc.user != request.user and not request.user.is_staff:
            return Response(
                {"error": "You don't have permission to view this PoC"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return Response({
            "id": poc.id,
            "code": poc.code or "No code available",
            "language": poc.language,
            "created_at": poc.created_at,
            "status": poc.status
        })