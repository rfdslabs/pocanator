"""
PoC Generation Service

This service handles the actual generation of proof-of-concept exploits
using the OpenAI API, based on prompts from the PoCPromptService.
It integrates deep thinking and feedback learning for Phase 4 enhancements.
"""
import logging
import time
import threading
import json
from django.conf import settings
from apps.analysis.openai_compat import OpenAIClient
from apps.pocs.models import ProofOfConcept, PoCTemplate
from .prompt_service import PoCPromptService
from .feedback_learning_service import PoCFeedbackLearningService
from .deep_thinking_service import PoCDeepThinkingService

logger = logging.getLogger(__name__)

class PoCGenerationService:
    """
    Service for generating proofs of concept using OpenAI with
    deep thinking and feedback learning capabilities.
    """
    
    DEFAULT_MODEL = getattr(settings, 'POC_DEFAULT_MODEL', 'gpt-4o')
    FALLBACK_MODEL = getattr(settings, 'POC_FALLBACK_MODEL', 'gpt-3.5-turbo')
    
    def __init__(self, api_key=None):
        """Initialize the generation service."""
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        self.prompt_service = PoCPromptService()
        self.feedback_service = PoCFeedbackLearningService()
        self.deep_thinking_service = PoCDeepThinkingService(api_key=self.api_key)
        
        # Initialize the OpenAI client when needed
        self._client = None
    
    @property
    def client(self):
        """Lazy-load the OpenAI client."""
        if not self._client:
            if not self.api_key:
                raise ValueError('OpenAI API key is required for PoC generation')
            self._client = OpenAIClient(api_key=self.api_key)
        return self._client
    
    def parse_generation_result(self, content):
        """
        Parse the generated content to extract structured information.
        
        Args:
            content: String containing the generated content
            
        Returns:
            Dictionary with code, explanation, setup_instructions, and security_warnings
        """
        result = {
            'code': '',
            'explanation': '',
            'setup_instructions': '',
            'security_warnings': '',
            'language': 'unknown',
        }
        
        # Improved regex for code blocks that handles language specifiers
        import re
        
        # Pattern for markdown code blocks with optional language specifier
        # First try to match ```language\ncode``` format
        code_blocks_with_lang = re.findall(r'```([a-zA-Z0-9_+-]+)\s*\n([\s\S]+?)```', content)
        
        # If that fails, try to match simple ```code``` format
        code_blocks_simple = re.findall(r'```\s*\n([\s\S]+?)```', content) if not code_blocks_with_lang else []
        
        # Also try to match ```code``` without newline after backticks (common mistake in models)
        if not code_blocks_with_lang and not code_blocks_simple:
            code_blocks_simple = re.findall(r'```([\s\S]+?)```', content)
        
        # Extract the code and language
        if code_blocks_with_lang:
            # We have language-specified code blocks
            result['language'] = code_blocks_with_lang[0][0].lower().strip()
            result['code'] = code_blocks_with_lang[0][1].strip()
            
            # If multiple code blocks with same language, append them
            if len(code_blocks_with_lang) > 1:
                for lang, code in code_blocks_with_lang[1:]:
                    if lang.lower().strip() == result['language']:
                        # Use language-specific comment format or no comment for shell commands
                        comment_formats = {
                            'python': '# ',
                            'javascript': '// ',
                            'typescript': '// ',
                            'java': '// ',
                            'c': '// ',
                            'cpp': '// ',
                            'csharp': '// ',
                            'php': '// ',
                            'ruby': '# ',
                            'go': '// ',
                            'rust': '// ',
                            'swift': '// ',
                            'perl': '# ',
                            'r': '# ',
                            'bash': '# ',
                            'shell': '# ',
                            'sh': '# ',
                            'zsh': '# ',
                            'sql': '-- ',
                            'html': '<!-- ',
                            'css': '/* '
                        }
                        
                        # For shell/bash scripts or npm commands, don't add comments that break execution
                        if result['language'] in ['sh', 'bash', 'shell', 'zsh'] or code.strip().startswith(('npm ', 'mkdir ', 'cd ', 'git ')):
                            result['code'] += f"\n\n{code.strip()}"
                        else:
                            comment_prefix = comment_formats.get(result['language'], '# ')
                            result['code'] += f"\n\n{comment_prefix}Additional code segment\n{code.strip()}"
        
        elif code_blocks_simple:
            # We have simple code blocks
            code_content = code_blocks_simple[0].strip()
            result['code'] = code_content
            
            # Special detection for shell scripts without language specifier
            if any(cmd in code_content.lower() for cmd in ['mkdir ', 'cd ', 'npm ', 'git ', 'touch ', 'chmod ']):
                # This looks like a shell script
                result['language'] = 'shell'
            
            # Try to determine language from content
            lang_indicators = {
                'python': ['import ', 'def ', 'class ', 'if __name__', '#!/usr/bin/env python', 'print('],
                'javascript': ['const ', 'let ', 'function(', '=>', 'document.', 'window.', 'console.log'],
                'java': ['public class', 'import java.', 'public static void main'],
                'bash': ['#!/bin/bash', 'echo ', 'grep ', 'awk ', 'sed ', 'chmod ', 'mkdir ', 'cd ', 'rm ', 'cp '],
                'shell': ['#!/bin/sh', 'mkdir ', 'cd ', 'npm ', 'apt-get ', 'yum ', 'touch ', 'chmod ', 'git '],
                'php': ['<?php', '<?=', 'namespace ', 'use '],
                'ruby': ['require ', 'def ', 'class ', 'end', '#!/usr/bin/env ruby'],
                'go': ['package main', 'import (', 'func main()', 'fmt.'],
                'csharp': ['using System;', 'namespace ', 'public class', 'static void Main'],
                'html': ['<!DOCTYPE', '<html', '<head', '<body'],
                'sql': ['SELECT ', 'FROM ', 'WHERE ', 'INSERT INTO', 'UPDATE ', 'DELETE FROM'],
                'c': ['#include <', 'int main(', 'return 0;', 'printf('],
                'cpp': ['#include <', 'std::', 'int main(', 'class ', 'namespace '],
                'typescript': ['interface ', 'type ', 'export class', 'import {', 'const :', 'let :'],
                'powershell': ['Write-Host', 'Get-', 'Set-', '$PSScriptRoot', 'param('],
            }
            
            code = result['code'].lower()
            matched_langs = []
            
            for lang, indicators in lang_indicators.items():
                matches = sum(1 for indicator in indicators if indicator.lower() in code)
                if matches > 0:
                    matched_langs.append((lang, matches))
            
            if matched_langs:
                # Choose the language with the most indicator matches
                result['language'] = max(matched_langs, key=lambda x: x[1])[0]
        
        # Extract sections based on common headers
        sections = {
            'explanation': ['## explanation', '# explanation', '### explanation', 
                            '## how it works', '# how it works', '### how it works',
                            '## overview', '# overview', '### overview'],
            'setup_instructions': ['## setup', '# setup', '### setup', 
                                  '## setup instructions', '# setup instructions',
                                  '## environment setup', '# environment setup',
                                  '## installation', '# installation', '### installation',
                                  '## prerequisites', '# prerequisites', '### prerequisites'],
            'security_warnings': ['## security warning', '# security warning', '### security warning',
                                 '## security warnings', '# security warnings', '### security warnings',
                                 '## warning', '# warning', '### warning',
                                 '## responsible use', '# responsible use',
                                 '## disclaimer', '# disclaimer', '### disclaimer',
                                 '## security considerations', '# security considerations']
        }
        
        content_lower = content.lower()
        
        # Improved section extraction with better boundary detection
        for section_key, headers in sections.items():
            for header in headers:
                if header in content_lower:
                    start_idx = content_lower.find(header)
                    header_end = content.find('\n', start_idx)
                    if header_end == -1:  # No newline found
                        header_end = len(content)
                    start_idx = header_end + 1  # Start after the newline following the header
                    
                    # Find the next header or the end of the content
                    end_idx = len(content)
                    for next_header_pattern in ['## ', '# ', '### ']:
                        pos = start_idx
                        while True:
                            next_header_idx = content.find(next_header_pattern, pos)
                            if next_header_idx == -1:
                                break
                                
                            # Ensure it's a real header (at start of line)
                            if next_header_idx == 0 or content[next_header_idx-1] == '\n':
                                if next_header_idx < end_idx:
                                    end_idx = next_header_idx
                                break
                            pos = next_header_idx + 1
                    
                    section_content = content[start_idx:end_idx].strip()
                    if section_content:
                        # Remove any code blocks from non-code sections to avoid duplication
                        if section_key != 'code':
                            section_content = re.sub(r'```.*?```', '', section_content, flags=re.DOTALL)
                            section_content = section_content.strip()
                        
                        result[section_key] = section_content
                        break  # Found this section, move to the next one
        
        # Additional extraction for common section formats
        if not result['explanation']:
            # Look for explanation outside of explicit headers
            explanation_patterns = [
                r'(?:This PoC|This exploit|This code|The exploit|The PoC)[^.]+works by[^.]+\.',
                r'(?:This|The) proof-of-concept demonstrates[^.]+\.'
            ]
            
            for pattern in explanation_patterns:
                explanation_match = re.search(pattern, content)
                if explanation_match:
                    # Extract a reasonable amount of context
                    match_start = max(0, explanation_match.start() - 100)
                    match_end = min(len(content), explanation_match.end() + 200)
                    result['explanation'] = content[match_start:match_end].strip()
                    break
        
        # Look for security warnings if we didn't find them through headers
        if not result['security_warnings']:
            warning_patterns = [
                r'(?:WARNING|CAUTION|IMPORTANT)[:\s]+[A-Z][^.]+(?:\.[^.]+){0,3}\.', 
                r'[Tt]his (?:code|PoC|exploit) should [^.]+(?:\.[^.]+){0,2}\.',
                r'(?:Only use|Use this|This should be used) [^.]+responsible[^.]+\.'
            ]
            
            for pattern in warning_patterns:
                warning_match = re.search(pattern, content)
                if warning_match:
                    result['security_warnings'] = warning_match.group(0)
                    break
        
        # If we couldn't parse the content into sections, use some fallbacks
        if not result['code']:
            # Look for any content that might be code
            code_indicators = ['(', ')', '{', '}', ';', '=', 'function', 'class', 'def ', 'import ', 'var ', 'let ', 'const ']
            lines = content.split('\n')
            potential_code = []
            
            for line in lines:
                stripped = line.strip()
                if any(indicator in stripped for indicator in code_indicators) and not stripped.startswith('#'):
                    potential_code.append(line)
            
            if potential_code:
                result['code'] = '\n'.join(potential_code)
            else:
                # Last resort, use everything as code
                result['code'] = content
        
        if not result['explanation'] and len(content) < 2000:
            # Use the entire content as the explanation if it's not too long
            # and we didn't find a specific explanation
            result['explanation'] = content
        
        # Ensure we have some security warnings
        if not result['security_warnings']:
            result['security_warnings'] = """
WARNING: This code is provided for educational purposes only and should only be used 
in controlled environments with proper authorization. Using this code against systems 
without explicit permission is illegal and unethical.
""".strip()
            
        # Clean up extra whitespace in all sections
        for key in result:
            if isinstance(result[key], str):
                result[key] = '\n'.join(line.rstrip() for line in result[key].splitlines())
                result[key] = result[key].strip()
        
        return result
    
    def generate_poc(self, poc_id):
        """
        Generate a PoC for the given ID using the OpenAI API.
        Enhanced with deep thinking and feedback learning capabilities.
        
        Args:
            poc_id: The ID of the ProofOfConcept object
            
        Returns:
            Boolean indicating success
        """
        try:
            # Get the PoC object
            poc = ProofOfConcept.objects.get(id=poc_id)
            
            # Update the status to 'processing'
            poc.status = 'processing'
            poc.save()
            
            # Determine vulnerability type for better template selection
            vuln_type = self.feedback_service.determine_vulnerability_type(poc)
            logger.info(f'Determined vulnerability type for PoC {poc_id}: {vuln_type}')
            
            # Find the best template based on past performance (if available)
            template = self.feedback_service.select_template_for_vulnerability(vuln_type, poc.target_os, poc.target_language_version)
            if template:
                logger.info(f'Selected template "{template.name}" for PoC {poc_id}')
                poc.template_used = template
                poc.save()
            
            # Perform deep thinking analysis for complex vulnerabilities
            deep_thinking_results = None
            if poc.use_deep_thinking:
                logger.info(f'Starting deep thinking analysis for PoC {poc_id}')
                deep_thinking_results = self.deep_thinking_service.perform_deep_thinking_analysis(poc_id)
                
                if deep_thinking_results:
                    logger.info(f'Completed deep thinking analysis for PoC {poc_id}')
                    # Integrate the results back into the PoC
                    self.deep_thinking_service.integrate_deep_thinking_results(poc_id, deep_thinking_results)
            
            # Construct the prompt with feedback-enhanced templates if available
            logger.info(f'Constructing prompt for PoC {poc_id}')
            system_prompt, user_prompt = self.prompt_service.construct_prompt(poc)
            
            # Apply deep thinking enhancements to prompts if needed
            if poc.use_deep_thinking:
                system_prompt, user_prompt = self.deep_thinking_service.enhance_prompt_with_deep_thinking(
                    system_prompt, user_prompt, vuln_type
                )
            
            # Prepare messages for the API
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ]
            
            # Settings for deep thinking mode
            temperature = 0.2 if not poc.use_deep_thinking else 0.7
            max_tokens = getattr(settings, 'POC_MAX_TOKENS', 4000)
            if poc.use_deep_thinking:
                max_tokens = getattr(settings, 'POC_DEEP_THINKING_TOKENS', 8000)
            
            # Call the OpenAI API
            logger.info(f'Calling OpenAI API for PoC {poc_id}')
            start_time = time.time()
            try:
                response = self.client.chat_completion(
                    model=self.DEFAULT_MODEL,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # The API call succeeded
                logger.info(f'Successfully generated PoC {poc_id} with {response["tokens"]["total_tokens"]} tokens')
                generation_content = response['content']
                tokens_used = response['tokens']['total_tokens']
                model_used = response['model']
                
            except Exception as e:
                # Try the fallback model if the first one fails
                logger.warning(f'Error with primary model, trying fallback for PoC {poc_id}: {str(e)}')
                try:
                    response = self.client.chat_completion(
                        model=self.FALLBACK_MODEL,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    
                    generation_content = response['content']
                    tokens_used = response['tokens']['total_tokens']
                    model_used = response['model']
                    
                except Exception as fallback_e:
                    logger.error(f'Error generating PoC {poc_id} with fallback model: {str(fallback_e)}')
                    poc.status = 'failed'
                    poc.save()
                    return False
            
            # Parse the generated content
            parsed_result = self.parse_generation_result(generation_content)
            
            # Calculate completion time
            completion_time = int(time.time() - start_time)
            
            # Update the PoC object with the results
            poc.code = parsed_result['code']
            poc.explanation = parsed_result['explanation']
            poc.setup_instructions = parsed_result['setup_instructions']
            poc.security_warnings = parsed_result['security_warnings']
            poc.language = parsed_result['language']
            poc.completion_time = completion_time
            poc.tokens_used = tokens_used
            poc.status = 'completed'
            
            # If we used a template, update its usage metrics
            if template:
                template.usage_count += 1
                template.save()
            
            poc.save()
            
            logger.info(f'Successfully completed PoC {poc_id} in {completion_time} seconds')
            return True
            
        except ProofOfConcept.DoesNotExist:
            logger.error(f'PoC {poc_id} not found')
            return False
        except Exception as e:
            logger.error(f'Error generating PoC {poc_id}: {str(e)}')
            try:
                poc = ProofOfConcept.objects.get(id=poc_id)
                poc.status = 'failed'
                poc.save()
            except:
                pass
            return False
    
    def generate_poc_async(self, poc_id):
        """
        Generate a PoC asynchronously in a separate thread.
        
        Args:
            poc_id: The ID of the ProofOfConcept object
        """
        thread = threading.Thread(target=self.generate_poc, args=(poc_id,))
        thread.daemon = True
        thread.start()
        return thread