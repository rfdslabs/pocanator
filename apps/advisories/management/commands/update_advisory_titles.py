import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from bs4 import BeautifulSoup
import requests
from apps.advisories.models import Advisory
from apps.advisories.services import GitHubAdvisoryService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Updates titles for existing advisories that might have incorrect or missing titles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Update all advisories, not just those with missing or problematic titles',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without making any changes',
        )

    def handle(self, *args, **options):
        update_all = options['all']
        dry_run = options['dry_run']
        
        service = GitHubAdvisoryService()
        
        # Get advisories to update
        if update_all:
            advisories = Advisory.objects.all()
            self.stdout.write(f"Updating titles for all {advisories.count()} advisories")
        else:
            # Only update advisories with missing, unknown, or problematic titles
            problematic_titles = [
                "Unknown Title", 
                "No title available",
                "Search code, repositories, users, issues, pull requests..."
            ]
            
            # Also include any that have these phrases in the title
            advisories = Advisory.objects.filter(
                title__in=problematic_titles
            ) | Advisory.objects.filter(
                title__icontains="Search"
            ) | Advisory.objects.filter(
                title__exact=""
            ) | Advisory.objects.filter(
                title__isnull=True
            )
            
            self.stdout.write(f"Found {advisories.count()} advisories with problematic titles")
        
        updated_count = 0
        failed_count = 0
        
        # Process each advisory
        for advisory in advisories:
            try:
                old_title = advisory.title or "None"
                
                # Fetch the advisory page
                response = requests.get(advisory.url, timeout=20)
                response.raise_for_status()
                
                # Parse HTML and extract the title
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Custom title extraction method that's more aggressive than the service version
                new_title = self._extract_title(soup)
                
                # Fall back to service method if our custom method fails
                if not new_title or new_title == "Unknown Title" or "Search" in new_title:
                    new_title = service._extract_title(soup)
                
                if new_title == old_title:
                    self.stdout.write(f"Title unchanged for {advisory.github_id}: {old_title}")
                    continue
                    
                self.stdout.write(f"Updating title for {advisory.github_id}:")
                self.stdout.write(f"  Old: {old_title}")
                self.stdout.write(f"  New: {new_title}")
                
                if not dry_run:
                    with transaction.atomic():
                        advisory.title = new_title
                        advisory.save(update_fields=['title'])
                    self.stdout.write(self.style.SUCCESS(f"Updated {advisory.github_id}"))
                else:
                    self.stdout.write(self.style.WARNING(f"DRY RUN - Would update {advisory.github_id}"))
                
                updated_count += 1
                
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Failed to update {advisory.github_id}: {str(e)}")
                )
                logger.exception(f"Error updating title for advisory {advisory.github_id}")
        
        # Print summary
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"DRY RUN COMPLETED: Would have updated {updated_count} advisories. {failed_count} failures."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Successfully updated {updated_count} advisories. {failed_count} failures."
            ))
    
    def _extract_title(self, soup):
        """
        Enhanced method to extract advisory titles from GitHub pages.
        Tries multiple approaches to find the real title.
        """
        # Approach 1: Look for the vulnerability summary directly
        # This is the most reliable way to get the actual title rather than just the CVE ID
        for selector in [
            '.markdown-body h2:first-of-type',
            '.markdown-body h3:first-of-type',
            '.Box-body .markdown-body p:first-of-type strong',
            '.Box-body .markdown-body p strong',
            '.Box-body .markdown-body p:first-of-type'
        ]:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                # Look for likely vulnerability descriptions (avoid navigation elements)
                if text and len(text) > 15 and not 'Search' in text and not 'GitHub' in text:
                    # Vulnerability titles often mention the vulnerability type
                    vuln_keywords = ['vulnerability', 'injection', 'overflow', 'bypass', 'disclosure', 
                                    'XSS', 'execution', 'escalation', 'authentication']
                    for keyword in vuln_keywords:
                        if keyword.lower() in text.lower():
                            return text
        
        # Approach 2: Look for h1 in article.advisoryContent
        article = soup.select_one('article.advisoryContent')
        if article:
            h1 = article.find('h1')
            if h1 and not 'Search' in h1.text:
                return h1.text.strip()
        
        # Approach 3: Look for specific divs that might contain the title
        for selector in [
            'h1.lh-condensed', 
            'h1.gh-header-title',
            'div.Box-header h1',
            'h1.gh-header-title span.js-issue-title',
            'h1.sr-only'
        ]:
            title_elem = soup.select_one(selector)
            if title_elem and title_elem.text and not 'Search' in title_elem.text:
                return title_elem.text.strip()
                
        # Approach 4: Look for the markdown summary section
        markdown_body = soup.select_one('.markdown-body')
        if markdown_body:
            # Try to get the first paragraph with meaningful content
            paragraphs = markdown_body.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 20 and not text.startswith('CVE-') and not 'Search' in text:
                    # Truncate if it's too long
                    if len(text) > 100:
                        return text[:100] + "..."
                    return text
                    
            # Try to construct title from vulnerability details
            h2s = markdown_body.find_all('h2')
            for h2 in h2s:
                if h2.text and ('Description' in h2.text or 'Summary' in h2.text or 'Overview' in h2.text):
                    # Get the next element which might contain the summary
                    next_elem = h2.find_next(['p', 'div', 'ul'])
                    if next_elem:
                        text = next_elem.get_text(strip=True)
                        if text and len(text) > 20:
                            # Truncate if it's too long
                            if len(text) > 100:
                                return text[:100] + "..."
                            return text
        
        # Approach 5: Look at the page title (in the <title> tag)
        title_tag = soup.find('title')
        if title_tag and not 'Search' in title_tag.text:
            # GitHub titles are usually in the format "TITLE | GitHub Advisory Database"
            title_parts = title_tag.text.split('|')
            if len(title_parts) > 1:
                # If it's just a CVE ID, we'll need a better title
                if title_parts[0].strip().startswith('CVE-'):
                    # Try to extract actual vulnerability name from page content
                    # Most CVE descriptions follow a pattern like "XXX in YYY allows ZZZ"
                    text_content = soup.get_text()
                    for pattern in [
                        r'vulnerability in .{5,100}',
                        r'allows .{5,100} via',
                        r'vulnerable to .{5,100}'
                    ]:
                        import re
                        match = re.search(pattern, text_content, re.IGNORECASE)
                        if match:
                            return f"{title_parts[0].strip()} - {match.group(0)}"
                return title_parts[0].strip()
                
        # Approach a 6: Look at the metadata
        meta_title = soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content') and not 'Search' in meta_title.get('content'):
            return meta_title.get('content').strip()
        
        # Fall back to h2 elements with specific classes
        for h2 in soup.find_all('h2', class_=['Subhead-heading', 'h3-mktg']):
            if h2.text and not 'Search' in h2.text:
                return h2.text.strip()
        
        # Check all h2 elements if other methods fail
        for h2 in soup.find_all('h2'):
            if h2.text and not 'Search' in h2.text and not h2.has_attr('data-pjax'):
                return h2.text.strip()
        
        return "Unknown Title"