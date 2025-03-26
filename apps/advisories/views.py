from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, FormView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse
from django.db.models import Q
from django.http import JsonResponse
import requests
from bs4 import BeautifulSoup
import time
import random
import re
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

from .models import Advisory, Commit
from .services import GitHubAdvisoryService
from .forms import ImportAdvisoryForm


class AdvisoryListView(ListView):
    """View to display a list of advisories"""
    
    model = Advisory
    template_name = 'advisories/advisory_list.html'
    context_object_name = 'advisories'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Advisory.objects.all()
        
        # Filter by severity if provided
        severity = self.request.GET.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Filter by vulnerability type if provided
        vuln_type = self.request.GET.get('type')
        if vuln_type:
            queryset = queryset.filter(vulnerability_type=vuln_type)
        
        # Sort by requested field
        sort_by = self.request.GET.get('sort', '-discovered_date')
        if sort_by not in ['-discovered_date', 'discovered_date', 'severity', '-severity', 
                          'github_id', '-github_id']:
            sort_by = '-discovered_date'
        
        return queryset.order_by(sort_by)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['severity_choices'] = Advisory.SEVERITY_CHOICES
        context['current_severity'] = self.request.GET.get('severity', '')
        context['current_type'] = self.request.GET.get('type', '')
        context['current_sort'] = self.request.GET.get('sort', '-discovered_date')
        
        # Get distinct vulnerability types
        context['vulnerability_types'] = Advisory.objects.exclude(
            vulnerability_type__isnull=True
        ).exclude(
            vulnerability_type__exact=''
        ).values_list('vulnerability_type', flat=True).distinct()
        
        return context


class AdvisoryDetailView(DetailView):
    """View to display a single advisory"""
    
    model = Advisory
    template_name = 'advisories/advisory_detail.html'
    context_object_name = 'advisory'
    slug_field = 'github_id'
    slug_url_kwarg = 'github_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['commits'] = self.object.commits.all()
        context['analyses'] = self.object.analyses.all()
        return context


class ImportAdvisoryView(LoginRequiredMixin, FormView):
    """View to import an advisory from GitHub"""
    
    template_name = 'advisories/import_advisory.html'
    form_class = ImportAdvisoryForm
    
    def form_valid(self, form):
        advisory_url = form.cleaned_data['advisory_url']
        
        # Extract GHSA ID from URL if needed
        if 'GHSA-' in advisory_url:
            ghsa_id = advisory_url.split('/')[-1]
            
            # Check if advisory already exists
            if Advisory.objects.filter(github_id=ghsa_id).exists():
                messages.info(self.request, f"Advisory {ghsa_id} already exists in the database.")
                return redirect('advisory-detail', github_id=ghsa_id)
        
        # Import the advisory
        try:
            service = GitHubAdvisoryService()
            advisory = service.fetch_advisory(advisory_url)
            
            if advisory:
                messages.success(self.request, f"Successfully imported advisory: {advisory.github_id}")
                return redirect('advisory-detail', github_id=advisory.github_id)
            else:
                messages.error(self.request, f"Failed to import advisory from URL: {advisory_url}")
        except Exception as e:
            messages.error(self.request, f"Error importing advisory: {str(e)}")
        
        return super().form_invalid(form)


class AdvisorySearchView(ListView):
    """View to search for advisories"""
    
    model = Advisory
    template_name = 'advisories/advisory_search.html'
    context_object_name = 'advisories'
    paginate_by = 20
    
    def get_queryset(self):
        query = self.request.GET.get('q', '')
        if query:
            return Advisory.objects.filter(
                Q(github_id__icontains=query) |
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(cve_id__icontains=query) |
                Q(vulnerability_type__icontains=query)
            ).order_by('-discovered_date')
        return Advisory.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context


class BatchImportView(LoginRequiredMixin, View):
    """View to batch import multiple advisories from GitHub search results"""
    
    template_name = 'advisories/batch_import.html'  # Make sure this template exists in the container
    
    # Constants for batch importing
    BASE_SEARCH_URL = "https://github.com/advisories"
    BASE_QUERY_PARAMS = {'query': 'rce type:reviewed rce'}
    REQUEST_TIMEOUT = 20
    MIN_DELAY = 0.8
    MAX_DELAY = 2.0
    
    def get(self, request):
        """Display the batch import form"""
        return render(request, self.template_name, {
            'total_advisories': Advisory.objects.count(),
        })
    
    def post(self, request):
        """Process batch import request"""
        try:
            # Get number of pages to fetch
            num_pages = int(request.POST.get('num_pages', 1))
            if num_pages < 1 or num_pages > 10:
                messages.error(request, "Please enter a number between 1 and 10.")
                return render(request, self.template_name)
            
            # Get query parameters
            query = request.POST.get('query', 'rce type:reviewed')
            
            # Set up query params
            query_params = {'query': query}
            
            # Start import in background
            import_results = self._batch_import_advisories(num_pages, query_params)
            
            # Return results
            return render(request, self.template_name, {
                'total_advisories': Advisory.objects.count(),
                'results': import_results,
                'num_pages': num_pages,
                'query': query,
            })
            
        except Exception as e:
            messages.error(request, f"Error during batch import: {str(e)}")
            return render(request, self.template_name)
    
    def _get_polite_delay(self):
        """Get a random delay to be polite to GitHub's servers"""
        return random.uniform(self.MIN_DELAY, self.MAX_DELAY)
    
    def _fetch_advisory_links_page(self, page_num, base_url, query_params):
        """Fetch a page of advisory links from GitHub search results"""
        advisory_links = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        current_query_params = query_params.copy()
        if page_num > 1:
            current_query_params['page'] = str(page_num)
        
        target_url = f"{base_url}?{urlencode(current_query_params)}"
        
        try:
            response = requests.get(target_url, headers=headers, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            all_links = soup.find_all('a')
            processed_hrefs_on_page = set()
            
            for link_tag in all_links:
                href = link_tag.get('href')
                if href and href.startswith('/advisories/GHSA-') and href not in processed_hrefs_on_page:
                    full_url = urljoin("https://github.com", href)
                    advisory_links.append(full_url)
                    processed_hrefs_on_page.add(href)
            
            return advisory_links
            
        except Exception as e:
            return []
    
    def _batch_import_advisories(self, num_pages, query_params):
        """Batch import advisories from GitHub search results"""
        results = {
            'total_pages': num_pages,
            'total_links_found': 0,
            'advisories_imported': 0,
            'advisories_existing': 0,
            'advisories_failed': 0,
            'imported_ids': [],
        }
        
        # Fetch advisory links
        all_advisory_urls = []
        master_processed_hrefs = set()
        
        for page in range(1, num_pages + 1):
            page_links = self._fetch_advisory_links_page(page, self.BASE_SEARCH_URL, query_params)
            
            if page_links:
                new_links_count = 0
                for link in page_links:
                    path = urlparse(link).path
                    if path not in master_processed_hrefs:
                        all_advisory_urls.append(link)
                        master_processed_hrefs.add(path)
                        new_links_count += 1
            
            if page < num_pages:
                time.sleep(self._get_polite_delay())
        
        results['total_links_found'] = len(all_advisory_urls)
        
        # Process each advisory
        service = GitHubAdvisoryService()
        
        for i, adv_url in enumerate(all_advisory_urls):
            try:
                # Extract GHSA ID from URL
                ghsa_id = re.search(r'GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}', adv_url).group(0)
                
                # Check if advisory already exists
                if Advisory.objects.filter(github_id=ghsa_id).exists():
                    results['advisories_existing'] += 1
                    continue
                
                # Import the advisory
                advisory = service.fetch_advisory(adv_url)
                
                if advisory:
                    results['advisories_imported'] += 1
                    results['imported_ids'].append(advisory.github_id)
                else:
                    results['advisories_failed'] += 1
                
            except Exception as e:
                results['advisories_failed'] += 1
            
            # Add delay between API calls
            time.sleep(self._get_polite_delay())
        
        return results