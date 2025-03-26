from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from .models import Advisory, Commit
from .serializers import AdvisorySerializer, CommitSerializer
from .services import GitHubAdvisoryService


class AdvisoryListAPIView(generics.ListAPIView):
    """API view to list all advisories"""
    queryset = Advisory.objects.all()
    serializer_class = AdvisorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by severity
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Filter by vulnerability type
        vuln_type = self.request.query_params.get('type')
        if vuln_type:
            queryset = queryset.filter(vulnerability_type=vuln_type)
        
        # Sort results
        sort_by = self.request.query_params.get('sort', '-discovered_date')
        if sort_by not in ['-discovered_date', 'discovered_date', 'severity', '-severity', 
                          'github_id', '-github_id']:
            sort_by = '-discovered_date'
            
        return queryset.order_by(sort_by)


class AdvisoryDetailAPIView(generics.RetrieveAPIView):
    """API view to retrieve a single advisory"""
    queryset = Advisory.objects.all()
    serializer_class = AdvisorySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'github_id'


class CommitListAPIView(generics.ListAPIView):
    """API view to list commits for an advisory"""
    serializer_class = CommitSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        github_id = self.kwargs.get('github_id')
        advisory = get_object_or_404(Advisory, github_id=github_id)
        return Commit.objects.filter(advisory=advisory)


class FetchAdvisoryAPIView(APIView):
    """API view to fetch an advisory from GitHub"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        advisory_url = request.data.get('advisory_url')
        if not advisory_url:
            return Response(
                {"error": "Advisory URL is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = GitHubAdvisoryService()
            advisory = service.fetch_advisory(advisory_url)
            
            if advisory:
                serializer = AdvisorySerializer(advisory)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {"error": "Failed to fetch advisory"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )