from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from .models import Analysis
from .serializers import AnalysisSerializer, AnalysisCreateSerializer
from .services import AnalysisService
from apps.advisories.models import Advisory


class AnalysisListAPIView(generics.ListAPIView):
    """API view to list all analyses"""
    queryset = Analysis.objects.all()
    serializer_class = AnalysisSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by advisory id
        advisory_id = self.request.query_params.get('advisory')
        if advisory_id:
            queryset = queryset.filter(advisory__github_id=advisory_id)
        
        # Filter by vulnerability type
        vuln_type = self.request.query_params.get('type')
        if vuln_type:
            queryset = queryset.filter(vuln_type=vuln_type)
        
        # Filter by PoC feasibility
        poc_min = self.request.query_params.get('poc_min')
        if poc_min and poc_min.isdigit():
            queryset = queryset.filter(poc_feasibility__gte=int(poc_min))
            
        poc_max = self.request.query_params.get('poc_max')
        if poc_max and poc_max.isdigit():
            queryset = queryset.filter(poc_feasibility__lte=int(poc_max))
        
        # Sort results
        sort_by = self.request.query_params.get('sort', '-created_at')
        if sort_by not in ['-created_at', 'created_at', 'poc_feasibility', '-poc_feasibility', 
                          'patch_effectiveness', '-patch_effectiveness']:
            sort_by = '-created_at'
            
        return queryset.order_by(sort_by)


class AnalysisDetailAPIView(generics.RetrieveAPIView):
    """API view to retrieve a single analysis"""
    queryset = Analysis.objects.all()
    serializer_class = AnalysisSerializer
    permission_classes = [permissions.IsAuthenticated]


class CreateAnalysisAPIView(APIView):
    """API view to create a new analysis for an advisory"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, github_id):
        try:
            advisory = get_object_or_404(Advisory, github_id=github_id)
            
            model = request.data.get('model', 'gpt-4o')
            
            # Get API key from request or user profile
            api_key = request.data.get('api_key')
            if not api_key and hasattr(request.user, 'profile'):
                api_key = request.user.profile.openai_api_key
            
            service = AnalysisService(api_key=api_key, user=request.user)
            analysis = service.analyze_advisory(advisory, model=model)
            
            if analysis:
                serializer = AnalysisSerializer(analysis)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {"error": "Failed to create analysis"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnalysisReportAPIView(APIView):
    """API view to get a formatted report for an analysis"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, pk):
        analysis = get_object_or_404(Analysis, pk=pk)
        
        format_type = request.query_params.get('format', 'markdown')
        
        if format_type == 'html':
            if analysis.html_report:
                return Response({"report": analysis.html_report})
            else:
                return Response(
                    {"error": "HTML report not available for this analysis"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            if analysis.markdown_report:
                return Response({"report": analysis.markdown_report})
            else:
                return Response(
                    {"error": "Markdown report not available for this analysis"}, 
                    status=status.HTTP_404_NOT_FOUND
                )