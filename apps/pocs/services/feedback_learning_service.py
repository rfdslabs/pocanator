"""
Feedback Learning Service for PoC Generation

This service analyzes user feedback to improve future PoC generations
through template optimization and prompt engineering.
"""
import logging
import re
from collections import Counter
from django.db.models import Avg, Count
from apps.pocs.models import ProofOfConcept, PoCTemplate, PoCFeedbackAnalysis

logger = logging.getLogger(__name__)

class PoCFeedbackLearningService:
    """
    Service for analyzing feedback and improving PoC generation through learning.
    """
    
    # Common feedback categories
    FEEDBACK_CATEGORIES = {
        'environment_setup': [
            'setup', 'environment', 'install', 'configuration', 'dependencies', 
            'prerequisite', 'requirements', 'version'
        ],
        'code_accuracy': [
            'doesn\'t work', 'not working', 'incorrect', 'error', 'bug', 'fails', 
            'wrong', 'issue', 'problem', 'fix'
        ],
        'clarity': [
            'unclear', 'confusing', 'complex', 'hard to understand', 'difficult', 
            'complicated', 'explain', 'explanation'
        ],
        'completeness': [
            'missing', 'incomplete', 'lacks', 'need more', 'additional', 'omitted',
            'forgotten', 'left out'
        ],
        'security': [
            'security', 'warning', 'caution', 'dangerous', 'risk', 'unsafe', 
            'protection', 'safety'
        ]
    }
    
    def __init__(self):
        """Initialize the feedback learning service."""
        pass
    
    def process_new_feedback(self, poc_id):
        """
        Process new feedback for a PoC and update learning models.
        
        Args:
            poc_id: ID of the ProofOfConcept that received feedback
            
        Returns:
            Boolean indicating success
        """
        try:
            poc = ProofOfConcept.objects.get(id=poc_id)
            
            # Only process if we have feedback
            if not poc.user_feedback:
                return False
            
            # Categorize the feedback
            feedback_categories = self.categorize_feedback(poc.user_feedback)
            poc.feedback_categories = feedback_categories
            poc.save()
            
            # Update template metrics if a template was used
            if poc.template_used:
                poc.template_used.update_metrics(
                    effectiveness_score=poc.effectiveness_score, 
                    worked=poc.worked_as_expected
                )
                
            # Update feedback analysis models
            vuln_type = self.determine_vulnerability_type(poc)
            self.update_feedback_analysis(vuln_type, feedback_categories, poc.user_feedback)
            
            return True
            
        except ProofOfConcept.DoesNotExist:
            logger.error(f"PoC {poc_id} not found for feedback processing")
            return False
        except Exception as e:
            logger.error(f"Error processing feedback for PoC {poc_id}: {str(e)}")
            return False
    
    def categorize_feedback(self, feedback_text):
        """
        Categorize feedback text into predefined categories.
        
        Args:
            feedback_text: The user's feedback text
            
        Returns:
            Dictionary with categories as keys and confidence scores as values
        """
        feedback_lower = feedback_text.lower()
        categories = {}
        
        for category, keywords in self.FEEDBACK_CATEGORIES.items():
            # Count keyword occurrences
            matches = sum(feedback_lower.count(keyword) for keyword in keywords)
            
            if matches > 0:
                # Calculate a simple confidence score based on matches
                confidence = min(1.0, matches / 10)  # Cap at 1.0
                categories[category] = round(confidence, 2)
        
        return categories
    
    def determine_vulnerability_type(self, poc):
        """
        Determine the vulnerability type for a PoC.
        
        Args:
            poc: ProofOfConcept object
            
        Returns:
            String with the vulnerability type
        """
        # Check if the PoC has a template with a vuln type
        if poc.template_used:
            return poc.template_used.vulnerability_type
            
        # Otherwise try to detect from the analysis or advisory
        analysis = poc.analysis
        
        # First check if the analysis has a vuln_type field
        if hasattr(analysis, 'vuln_type') and analysis.vuln_type:
            vuln_type = analysis.vuln_type.lower()
            if 'rce' in vuln_type or 'remote code execution' in vuln_type:
                return 'RCE'
            elif 'xss' in vuln_type or 'cross-site scripting' in vuln_type:
                return 'XSS'
            elif 'sqli' in vuln_type or 'sql injection' in vuln_type:
                return 'SQLI'
            elif 'ssrf' in vuln_type or 'server-side request forgery' in vuln_type:
                return 'SSRF'
            elif 'path traversal' in vuln_type or 'directory traversal' in vuln_type:
                return 'PATH_TRAVERSAL'
            elif 'deserialization' in vuln_type:
                return 'DESERIALIZATION'
            elif 'command injection' in vuln_type:
                return 'COMMAND_INJECTION'
            elif 'file upload' in vuln_type:
                return 'FILE_UPLOAD'
            elif 'idor' in vuln_type or 'insecure direct object reference' in vuln_type:
                return 'IDOR'
                
        return 'DEFAULT'
    
    def update_feedback_analysis(self, vuln_type, feedback_categories, feedback_text):
        """
        Update feedback analysis models with new insights.
        
        Args:
            vuln_type: The vulnerability type
            feedback_categories: Dictionary of feedback categories and confidence scores
            feedback_text: The original feedback text
        """
        for category, confidence in feedback_categories.items():
            # Only process categories with reasonable confidence
            if confidence < 0.3:
                continue
                
            # Get or create feedback analysis for this type and category
            analysis, created = PoCFeedbackAnalysis.objects.get_or_create(
                vulnerability_type=vuln_type,
                feedback_category=category,
                defaults={
                    'common_issues': 'Initial feedback collection',
                    'suggested_improvements': 'Collecting data for improvements',
                    'affected_prompt_sections': [],
                    'sample_size': 0,
                    'confidence_score': 0.0
                }
            )
            
            # Extract key phrases from feedback that might help identify issues
            key_phrases = self.extract_key_phrases(feedback_text, category)
            
            # Update the analysis
            analysis.sample_size += 1
            
            # If we have enough samples, update the common issues
            if analysis.sample_size >= 3:
                if created or analysis.sample_size <= 5:
                    # For new or small sample analyses, just set the common issues
                    analysis.common_issues = self.summarize_feedback(key_phrases, category)
                else:
                    # For established analyses, merge with existing insights
                    analysis.common_issues = self.merge_insights(
                        analysis.common_issues, 
                        self.summarize_feedback(key_phrases, category)
                    )
                
                # Identify affected prompt sections
                analysis.affected_prompt_sections = self.identify_affected_sections(category)
                
                # Generate suggested improvements
                analysis.suggested_improvements = self.generate_improvement_suggestions(
                    category, vuln_type, key_phrases
                )
            
            # Update confidence score based on sample size
            analysis.confidence_score = min(0.95, (analysis.sample_size / 20) + (confidence / 2))
            
            analysis.save()
    
    def extract_key_phrases(self, feedback_text, category):
        """
        Extract key phrases from feedback related to a specific category.
        
        Args:
            feedback_text: The feedback text
            category: The feedback category
            
        Returns:
            List of key phrases
        """
        phrases = []
        
        # Convert to lowercase for consistent processing
        feedback_lower = feedback_text.lower()
        
        # Get keywords for this category
        keywords = self.FEEDBACK_CATEGORIES.get(category, [])
        
        # Find sentences containing these keywords
        sentences = re.split(r'[.!?]+', feedback_lower)
        
        for sentence in sentences:
            if any(keyword in sentence for keyword in keywords):
                # Clean up the sentence
                clean_sentence = sentence.strip()
                if clean_sentence:
                    phrases.append(clean_sentence)
        
        return phrases
    
    def summarize_feedback(self, key_phrases, category):
        """
        Summarize feedback phrases into common issues.
        
        Args:
            key_phrases: List of key phrases from feedback
            category: The feedback category
            
        Returns:
            String with summarized common issues
        """
        if not key_phrases:
            return f"No specific {category} issues identified yet."
            
        # Simple summary for now - in real application this could use more NLP
        summary = f"Common {category} issues:\n\n"
        
        for i, phrase in enumerate(key_phrases[:5], 1):
            summary += f"{i}. \"{phrase.capitalize()}\"\n"
            
        if len(key_phrases) > 5:
            summary += f"\nPlus {len(key_phrases) - 5} additional related comments."
            
        return summary
    
    def merge_insights(self, existing_insights, new_insights):
        """
        Merge new insights with existing ones.
        
        Args:
            existing_insights: Existing insights text
            new_insights: New insights text
            
        Returns:
            Merged insights text
        """
        # Skip header from new insights to avoid duplication
        new_content = new_insights.split('\n\n', 1)[1] if '\n\n' in new_insights else new_insights
        
        # Simple approach: keep existing and add new with a separator
        return f"{existing_insights}\n\n--- Updated with new feedback ---\n\n{new_content}"
    
    def identify_affected_sections(self, category):
        """
        Identify which sections of the prompt are affected by this feedback category.
        
        Args:
            category: The feedback category
            
        Returns:
            List of affected prompt sections
        """
        # Map feedback categories to prompt sections
        section_mapping = {
            'environment_setup': ['setup_instructions', 'prerequisites'],
            'code_accuracy': ['code_skeleton', 'exploitation_approach'],
            'clarity': ['explanation', 'code_comments'],
            'completeness': ['prompt_context', 'vulnerability_details'],
            'security': ['security_warnings', 'ethical_guidelines']
        }
        
        return section_mapping.get(category, ['general_prompt'])
    
    def generate_improvement_suggestions(self, category, vuln_type, key_phrases):
        """
        Generate suggestions for improving prompts based on feedback.
        
        Args:
            category: The feedback category
            vuln_type: The vulnerability type
            key_phrases: Key phrases from feedback
            
        Returns:
            String with improvement suggestions
        """
        # Basic suggestions based on category
        suggestions = {
            'environment_setup': [
                "Provide more detailed setup steps with explicit versions",
                "Include prerequisites more prominently",
                "Add troubleshooting guidance for common setup issues",
                "Structure setup instructions as numbered steps",
                "Include verification steps to confirm environment is correct"
            ],
            'code_accuracy': [
                "Improve input validation in template code",
                "Be more explicit about which parts of the code need customization",
                "Add more comprehensive error handling",
                "Provide alternative approaches for different scenarios",
                "Include testing steps to verify the exploit works"
            ],
            'clarity': [
                "Simplify explanations with more examples",
                "Break down complex concepts into simpler steps",
                "Include diagrams or visual representations where helpful",
                "Add more comments in code sections",
                "Use consistent terminology throughout"
            ],
            'completeness': [
                "Expand context provided about the vulnerability",
                "Include more details from the advisory and patch",
                "Add references to related vulnerabilities",
                "Provide more comprehensive explanation of impact",
                "Cover edge cases and variations of the exploit"
            ],
            'security': [
                "Strengthen security warnings with specific risks",
                "Add more containment advice",
                "Include a section on potential legal implications",
                "Provide cleanup instructions",
                "Add warnings about unintended consequences"
            ]
        }
        
        # Get basic suggestions for this category
        basic_suggestions = suggestions.get(category, ["Improve prompt quality and accuracy"])
        
        # Add vulnerability-specific suggestions
        if vuln_type == 'RCE' and category == 'code_accuracy':
            basic_suggestions.append("Ensure command execution detection is reliable across different environments")
            basic_suggestions.append("Add payload encoding options for different target systems")
            
        elif vuln_type == 'XSS' and category == 'code_accuracy':
            basic_suggestions.append("Include variants for different browser contexts")
            basic_suggestions.append("Add WAF bypass techniques where appropriate")
            
        # Format the suggestions
        formatted = f"Suggested improvements for {category} in {vuln_type} templates:\n\n"
        
        for i, suggestion in enumerate(basic_suggestions[:5], 1):
            formatted += f"{i}. {suggestion}\n"
            
        return formatted
    
    def select_template_for_vulnerability(self, vuln_type, target_os=None, target_language=None):
        """
        Select the best template for a given vulnerability type based on performance metrics.
        
        Args:
            vuln_type: The vulnerability type
            target_os: Optional target OS for more specific matching
            target_language: Optional target language for more specific matching
            
        Returns:
            PoCTemplate object or None if no suitable template is found
        """
        # First try to find a highly effective template for this specific vulnerability type
        high_performing = PoCTemplate.objects.filter(
            vulnerability_type=vuln_type,
            is_active=True,
            usage_count__gte=5,  # Ensure we have enough usage data
            average_effectiveness__gte=7.0  # High effectiveness threshold
        ).order_by('-average_effectiveness', '-success_count')
        
        if high_performing.exists():
            return high_performing.first()
            
        # If no high-performing template, just get the best available
        templates = PoCTemplate.objects.filter(
            vulnerability_type=vuln_type,
            is_active=True
        ).order_by('-average_effectiveness', '-success_count')
        
        if templates.exists():
            return templates.first()
            
        # If no template for this vuln type, fall back to DEFAULT
        if vuln_type != 'DEFAULT':
            default_templates = PoCTemplate.objects.filter(
                vulnerability_type='DEFAULT',
                is_active=True
            ).order_by('-average_effectiveness', '-success_count')
            
            if default_templates.exists():
                return default_templates.first()
                
        return None
    
    def apply_feedback_improvements(self, template):
        """
        Apply learned feedback improvements to a template.
        
        Args:
            template: PoCTemplate object to improve
            
        Returns:
            Boolean indicating whether improvements were made
        """
        # Skip if template has been used too little
        if template.usage_count < 5:
            return False
            
        try:
            # Get all relevant feedback analyses for this vulnerability type
            analyses = PoCFeedbackAnalysis.objects.filter(
                vulnerability_type=template.vulnerability_type,
                confidence_score__gte=0.5  # Only use analyses with decent confidence
            )
            
            if not analyses.exists():
                return False
                
            has_changes = False
            
            # Process each feedback category
            for analysis in analyses:
                # Check which prompt sections are affected
                for section in analysis.affected_prompt_sections:
                    if section == 'system_prompt' and self.enhance_system_prompt(template, analysis):
                        has_changes = True
                    elif section in ['code_skeleton', 'code_comments'] and template.code_skeleton and self.enhance_code_skeleton(template, analysis):
                        has_changes = True
                    elif section in ['prompt_context', 'explanation', 'vulnerability_details', 'setup_instructions', 'prerequisites', 'security_warnings', 'ethical_guidelines'] and self.enhance_user_prompt(template, analysis, section):
                        has_changes = True
            
            if has_changes:
                template.save()
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error applying feedback improvements to template {template.id}: {str(e)}")
            return False
    
    def enhance_system_prompt(self, template, analysis):
        """
        Enhance the system prompt based on feedback analysis.
        
        Args:
            template: PoCTemplate to enhance
            analysis: PoCFeedbackAnalysis with improvement suggestions
            
        Returns:
            Boolean indicating whether changes were made
        """
        # Extract key suggestions from the analysis
        suggestions = analysis.suggested_improvements.split('\n')
        key_suggestions = [s.strip() for s in suggestions if s.strip() and s.strip().startswith(('1.', '2.', '3.'))]
        
        if not key_suggestions:
            return False
            
        # Parse the first suggestion to use
        suggestion = key_suggestions[0]
        if suggestion.startswith('1.'):
            suggestion = suggestion[2:].strip()
            
        category = analysis.feedback_category
        
        # Different enhancements based on feedback category
        if category == 'clarity':
            # Add clarity instruction if not already present
            clarity_hint = f"Break down complex concepts into simpler steps. {suggestion}"
            if clarity_hint not in template.system_prompt:
                template.system_prompt += f"\n\nIMPORTANT: {clarity_hint}"
                return True
                
        elif category == 'code_accuracy':
            # Add code accuracy instruction if not already present
            accuracy_hint = f"Ensure code is accurate and well-tested. {suggestion}"
            if accuracy_hint not in template.system_prompt:
                template.system_prompt += f"\n\nIMPORTANT: {accuracy_hint}"
                return True
                
        elif category == 'completeness':
            # Add completeness instruction if not already present
            completeness_hint = f"Be comprehensive in your approach. {suggestion}"
            if completeness_hint not in template.system_prompt:
                template.system_prompt += f"\n\nIMPORTANT: {completeness_hint}"
                return True
                
        return False
    
    def enhance_code_skeleton(self, template, analysis):
        """
        Enhance the code skeleton based on feedback analysis.
        
        Args:
            template: PoCTemplate to enhance
            analysis: PoCFeedbackAnalysis with improvement suggestions
            
        Returns:
            Boolean indicating whether changes were made
        """
        if not template.code_skeleton:
            return False
            
        category = analysis.feedback_category
        
        if category == 'code_accuracy':
            # Add more error handling and comments
            if '# Error handling' not in template.code_skeleton:
                improved_skeleton = template.code_skeleton.replace(
                    '# Main exploit code',
                    '# Main exploit code\n# Add appropriate error handling for robustness'
                )
                template.code_skeleton = improved_skeleton
                return True
                
        elif category == 'clarity':
            # Add more explanatory comments
            if '# Step-by-step explanation:' not in template.code_skeleton:
                template.code_skeleton = f"# Step-by-step explanation:\n# 1. First, we...\n# 2. Then, we...\n\n{template.code_skeleton}"
                return True
                
        return False
    
    def enhance_user_prompt(self, template, analysis, section):
        """
        Enhance a section of the user prompt template based on feedback.
        
        Args:
            template: PoCTemplate to enhance
            analysis: PoCFeedbackAnalysis with improvement suggestions
            section: The section to enhance
            
        Returns:
            Boolean indicating whether changes were made
        """
        # Map sections to typical placeholders in the template
        section_placeholders = {
            'setup_instructions': '## Setup Instructions',
            'prerequisites': '## Prerequisites',
            'vulnerability_details': '## Vulnerability Information',
            'security_warnings': '## Security Warnings',
            'ethical_guidelines': '## Ethical Guidelines'
        }
        
        placeholder = section_placeholders.get(section)
        if not placeholder or placeholder not in template.user_prompt_template:
            return False
            
        # Extract enhancement based on the section and category
        enhancement = None
        category = analysis.feedback_category
        
        if section == 'setup_instructions' and category == 'environment_setup':
            enhancement = "\nProvide DETAILED, step-by-step setup instructions with explicit version requirements."
            
        elif section == 'prerequisites' and category == 'environment_setup':
            enhancement = "\nList ALL required dependencies and their versions."
            
        elif section == 'vulnerability_details' and category == 'completeness':
            enhancement = "\nExplain the vulnerability comprehensively, including impact and attack vectors."
            
        elif section == 'security_warnings' and category == 'security':
            enhancement = "\nInclude specific risks, containment advice, and clean-up instructions."
            
        # Apply the enhancement if we have one and it's not already present
        if enhancement and enhancement not in template.user_prompt_template:
            # Find the section placeholder and add the enhancement
            parts = template.user_prompt_template.split(placeholder)
            if len(parts) >= 2:
                template.user_prompt_template = parts[0] + placeholder + enhancement + parts[1]
                return True
                
        return False
    
    def generate_improved_template_from_success(self, poc_id):
        """
        Generate an improved template from a successful PoC.
        
        Args:
            poc_id: ID of a successful ProofOfConcept to learn from
            
        Returns:
            New PoCTemplate object or None if creation failed
        """
        try:
            poc = ProofOfConcept.objects.get(id=poc_id)
            
            # Only consider successful, well-rated PoCs
            if not poc.worked_as_expected or not poc.effectiveness_score or poc.effectiveness_score < 8:
                return None
                
            # Determine vulnerability type
            vuln_type = self.determine_vulnerability_type(poc)
            
            # Check if we already have a similar template
            existing_templates = PoCTemplate.objects.filter(
                vulnerability_type=vuln_type
            ).count()
            
            # Create a name for the new template
            template_name = f"{vuln_type} Template #{existing_templates + 1} (Learned)"
            
            # Extract a system prompt - this is simplified and would be more sophisticated in production
            system_prompt = "You are an expert security researcher specializing in vulnerability exploitation.\n"
            system_prompt += f"Your task is to create a proof-of-concept exploit for {vuln_type} vulnerabilities.\n"
            system_prompt += "Focus on creating minimal, clear code that proves the vulnerability exists.\n"
            
            if poc.use_deep_thinking:
                system_prompt += "\nTake a step-by-step approach:\n"
                system_prompt += "1. First analyze the vulnerability and affected code thoroughly\n"
                system_prompt += "2. Identify the precise mechanism of exploitation\n"
                system_prompt += "3. Design an exploitation strategy accounting for all constraints\n"
                system_prompt += "4. Implement the strategy with minimal, focused code\n"
                system_prompt += "5. Review your solution for correctness and effectiveness"
            
            # Create a user prompt template based on what worked well
            user_prompt = "## Vulnerability Information\n"
            user_prompt += "{advisory_description}\n\n"
            user_prompt += "## Patch Analysis\n"
            user_prompt += "{patch_analysis}\n\n"
            user_prompt += "## Technical Details\n"
            user_prompt += f"- Vulnerability Type: {vuln_type}\n"
            user_prompt += "- Target OS: {target_os}\n"
            user_prompt += "- Target Environment: {target_language_version}\n"
            user_prompt += "- Exploitation Goal: {exploitation_goal}\n"
            user_prompt += "{additional_context_section}\n\n"
            user_prompt += "## Your Task\n"
            user_prompt += "1. Create a proof-of-concept exploit that demonstrates this vulnerability\n"
            user_prompt += "2. Include detailed comments explaining how the exploit works\n"
            user_prompt += "3. Provide setup instructions to replicate the vulnerable environment\n"
            user_prompt += "4. Add security warnings and responsible use guidelines\n"
            
            # Extract code skeleton if available
            code_skeleton = None
            if poc.code:
                # Extract a simplified version with core structure and comments
                lines = poc.code.split('\n')
                
                # Keep only structural and comment lines
                skeleton_lines = []
                for line in lines:
                    if line.strip().startswith('#') or line.strip().startswith('//'):
                        skeleton_lines.append(line)
                    elif line.strip().startswith(('import ', 'from ', 'include', 'require', 'using')):
                        skeleton_lines.append(line)
                    elif line.strip().startswith(('def ', 'function ', 'class ', 'void ', 'int ')):
                        skeleton_lines.append(line)
                        
                if skeleton_lines:
                    code_skeleton = '\n'.join(skeleton_lines)
            
            # Create the new template
            template = PoCTemplate.objects.create(
                vulnerability_type=vuln_type,
                name=template_name,
                description=f"Auto-generated template based on successful {vuln_type} PoC #{poc.id}",
                system_prompt=system_prompt,
                user_prompt_template=user_prompt,
                code_skeleton=code_skeleton,
                usage_count=1,
                success_count=1,
                average_effectiveness=float(poc.effectiveness_score) if poc.effectiveness_score else 8.0
            )
            
            return template
            
        except ProofOfConcept.DoesNotExist:
            logger.error(f"PoC {poc_id} not found for template learning")
            return None
        except Exception as e:
            logger.error(f"Error generating template from PoC {poc_id}: {str(e)}")
            return None