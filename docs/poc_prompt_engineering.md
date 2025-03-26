# PoC Generation System: Prompt Engineering

## Overview

The Prompt Engineering component is crucial for generating effective PoCs. It transforms the contextual information about a vulnerability into a structured prompt that guides the AI model to produce useful, targeted exploit code.

## Core Components

### PoCPromptService

The `PoCPromptService` class is responsible for constructing prompts tailored to specific vulnerabilities, based on the available context.

```python
class PoCPromptService:
    def __init__(self, poc_request):
        self.poc_request = poc_request
        self.analysis = poc_request.analysis
        self.advisory = poc_request.analysis.advisory
    
    def generate_prompt(self):
        """Build a comprehensive prompt for PoC generation"""
        prompt = self._build_system_prompt()
        prompt += self._include_vulnerability_context()
        prompt += self._include_relevant_code_snippets()
        prompt += self._add_specific_requirements()
        prompt += self._add_safety_guidelines()
        return prompt
```

## Prompt Structure

The prompt for PoC generation consists of several key sections:

### 1. System Prompt

The system prompt sets the tone and context for the AI, establishing its role and the task at hand.

```python
def _build_system_prompt(self):
    """Create the specialized system prompt for PoC generation"""
    vulnerability_type = self.analysis.vuln_type
    
    base_prompt = f"""You are an expert security researcher specializing in {vulnerability_type} vulnerabilities. 
Your task is to create a proof-of-concept exploit that demonstrates the vulnerability described.
Focus on creating minimal, clear code that proves the vulnerability exists.
Include only what's necessary to demonstrate the issue - don't add unnecessary features or complexity."""
    
    if self.poc_request.use_deep_thinking:
        base_prompt += """
Take a step-by-step approach:
1. First analyze the vulnerability and affected code thoroughly
2. Identify the precise mechanism of exploitation
3. Design an exploitation strategy accounting for all constraints
4. Implement the strategy with minimal, focused code
5. Review your solution for correctness and effectiveness"""
    
    return base_prompt
```

### 2. Vulnerability Context

This section includes relevant information from the advisory and analysis.

```python
def _include_vulnerability_context(self):
    """Add relevant info from the advisory and analysis"""
    context = f"""
## VULNERABILITY INFORMATION
Advisory ID: {self.advisory.github_id}
Title: {self.advisory.title}
Severity: {self.advisory.severity}
Vulnerability Type: {self.analysis.vuln_type}

### Description
{self.advisory.description}

### Analysis Summary
{self.analysis.vuln_explanation}

### Impact
{self.analysis.impact_summary}
"""
    return context
```

### 3. Code Snippets

Including relevant code snippets helps the AI understand the context of the vulnerability.

```python
def _include_relevant_code_snippets(self):
    """Extract and include key code from commits"""
    snippets = "\n## AFFECTED CODE\n"
    
    # Get the most relevant commits
    commits = self.advisory.commits.all()
    
    if not commits.exists():
        return snippets + "No specific code commits available.\n"
    
    # Include key file changes that are most likely related to the vulnerability
    for commit in commits:
        snippets += f"\nCommit: {commit.commit_hash[:7]} in {commit.repo_name}\n"
        
        for file_change in commit.file_changes.all()[:3]:  # Limit to 3 most relevant files
            snippets += f"\nFile: {file_change.file_path}\n```\n"
            
            # Include removed lines (vulnerable code)
            for line in file_change.line_changes.filter(change_type='remove')[:10]:  # Limit to 10 lines
                snippets += f"- {line.content}\n"
            
            # Include added lines (fix)
            for line in file_change.line_changes.filter(change_type='add')[:10]:
                snippets += f"+ {line.content}\n"
            
            snippets += "```\n"
    
    return snippets
```

### 4. Specific Requirements

This section specifies the exact requirements for the PoC based on user configuration.

```python
def _add_specific_requirements(self):
    """Add target environment and exploitation goals"""
    return f"""
## POC REQUIREMENTS
Target OS: {self.poc_request.target_os}
Target Language/Framework Version: {self.poc_request.target_language_version}
Exploitation Goal: {self.poc_request.exploitation_goal}

Additional Context: {self.poc_request.additional_context or 'None provided'}

Your PoC should be specifically tailored to these requirements.
"""
```

### 5. Output Format Requirements

This section instructs the AI on how to structure its response.

```python
def _add_output_format_requirements(self):
    """Specify the required format for the output"""
    return """
## OUTPUT FORMAT REQUIREMENTS
Provide your response in the following structure:

1. CODE: 
```language
[Your PoC code here]
```

2. EXPLANATION:
[Step-by-step explanation of how the PoC works and demonstrates the vulnerability]

3. SETUP INSTRUCTIONS:
[Detailed instructions for setting up the environment and running the PoC]

4. SECURITY WARNINGS:
[Important safety precautions and containment advice for running this PoC]
"""
```

### 6. Safety Guidelines

This section includes ethical guidelines and safety considerations.

```python
def _add_safety_guidelines(self):
    """Add safety requirements and constraints"""
    return """
## ETHICAL GUIDELINES
- Create a PoC that demonstrates the vulnerability without causing unnecessary harm
- Focus on minimum viable exploitation, not maximizing damage
- Do not include persistence mechanisms or backdoors
- Do not obfuscate the code or try to evade detection
- Include clear comments explaining the purpose of each component
- Add appropriate safety checks where possible
"""
```

## PoC Generation Examples

Different vulnerability types require different approaches. Here are examples for common types:

### Remote Code Execution (RCE)

```
Your task is to create a proof-of-concept for a remote code execution vulnerability.
The PoC should:
1. Demonstrate command execution in the target environment
2. Use a benign command (like 'id' or 'whoami')
3. Show clear evidence of successful execution
```

### SQL Injection

```
Your task is to create a proof-of-concept for an SQL injection vulnerability.
The PoC should:
1. Demonstrate the ability to extract data through SQL injection
2. Use non-destructive queries (SELECT only, no modifications)
3. Clearly show the vulnerability without damaging the database
```

### Cross-Site Scripting (XSS)

```
Your task is to create a proof-of-concept for an XSS vulnerability.
The PoC should:
1. Demonstrate JavaScript execution in the victim's browser
2. Use a benign payload (like displaying an alert with a specific message)
3. Show clear evidence of successful script execution
```

## Deep Thinking Mode

When deep thinking mode is enabled, the system uses an enhanced prompting strategy:

1. More detailed analysis requirements
2. Chain-of-thought reasoning
3. Multi-step approach to problem-solving
4. Self-critique and refinement
5. Higher token limits for more comprehensive responses

## Future Enhancements

1. **Template Library**: Pre-built templates for common vulnerability types
2. **Adaptive Prompting**: Adjust prompts based on feedback from previously generated PoCs
3. **Vulnerability-Specific Guidance**: Specialized instructions for different vulnerability classes
4. **Fine-Tuning**: Custom models trained specifically for PoC generation