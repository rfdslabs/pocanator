"""
Prompt Engineering Service for PoC Generation - Updated
"""
import logging
from apps.analysis.models import Analysis
from apps.pocs.models import ProofOfConcept
from apps.advisories.models import Advisory

logger = logging.getLogger(__name__)

class PoCPromptService:
    """Service for constructing prompts for PoC generation"""
    
    # Educational and research-focused templates
    VULN_TYPE_TEMPLATES = {
        'RCE': {
            'system_prompt': (
                "You are a security researcher focusing on educational content about vulnerabilities. "
                "Your task is to explain how certain code patterns can lead to security issues and "
                "provide educational examples to help developers understand these risks. Your examples "
                "should be clearly labeled as educational material and include proper mitigations."
            ),
            'user_prompt_template': (
                "## Educational Research Context\n"
                "I'm working on educational material about secure coding practices. Please help me create "
                "an educational example that demonstrates the security concepts related to this advisory "
                "in a controlled environment for teaching purposes.\n\n"
                "## Advisory Information\n{advisory_description}\n\n"
                "## Teaching Goals\n"
                "- Demonstrate how this vulnerability works in a controlled test environment\n"
                "- Explain vulnerable code patterns to avoid\n"
                "- Show proper remediation techniques\n"
                "- Help students understand secure coding practices\n\n"
                "Please provide sample code that demonstrates these concepts for a theoretical test environment, "
                "along with explanations of the security principles involved. Include comments explaining each part."
            )
        },
        'XSS': {
            'system_prompt': (
                "You are a web security educator creating learning materials about secure web development. "
                "Your role is to explain potential security issues in web applications and provide "
                "educational examples that help developers understand these concepts. Your examples should "
                "be clearly labeled as educational and include proper security practices."
            ),
            'user_prompt_template': (
                "## Educational Research Context\n"
                "I'm developing a security training module about secure web development. Please help me create "
                "an educational demonstration of the security concepts related to this advisory "
                "for a controlled classroom environment.\n\n"
                "## Advisory Information\n{advisory_description}\n\n"
                "## Teaching Goals\n"
                "- Show how improper input handling can lead to security issues\n"
                "- Demonstrate proper input validation techniques\n"
                "- Explain context-aware output encoding\n"
                "- Help students recognize vulnerable patterns\n\n"
                "Please provide sample code for a theoretical test application that demonstrates these "
                "security concepts, with detailed explanations of the principles involved."
            )
        },
        'SQLI': {
            'system_prompt': (
                "You are a database security educator creating learning materials about secure database interactions. "
                "Your goal is to explain how improper query construction can lead to security issues and provide "
                "educational examples to help developers understand secure coding patterns. Your examples should "
                "be clearly labeled as educational and include proper parameterization techniques."
            ),
            'user_prompt_template': (
                "## Educational Research Context\n"
                "I'm creating a training module on database security. Please help me develop "
                "an educational demonstration of the security concepts related to this advisory "
                "for a controlled classroom environment.\n\n"
                "## Advisory Information\n{advisory_description}\n\n"
                "## Teaching Goals\n"
                "- Illustrate how query construction affects security\n"
                "- Demonstrate the importance of parameterized queries\n"
                "- Show proper input validation techniques\n"
                "- Help students recognize vulnerable patterns\n\n"
                "Please provide sample code for a theoretical test application that demonstrates these "
                "database security concepts, with detailed explanations of the principles involved."
            )
        },
        'DEFAULT': {
            'system_prompt': (
                "You are a security education specialist creating learning materials about secure development. "
                "Your role is to explain potential security vulnerabilities and provide educational examples "
                "that help developers understand these concepts. Your examples should be clearly labeled as "
                "educational and include proper security practices."
            ),
            'user_prompt_template': (
                "## Educational Research Context\n"
                "I'm developing educational materials about secure coding practices. Please help me create "
                "an educational demonstration of the security concepts related to this advisory "
                "for a controlled classroom environment.\n\n"
                "## Advisory Information\n{advisory_description}\n\n"
                "## Teaching Goals\n"
                "- Demonstrate how this vulnerability works in a controlled test environment\n"
                "- Explain vulnerable code patterns to avoid\n"
                "- Show proper remediation techniques\n"
                "- Help students understand secure coding practices\n\n"
                "Please provide sample code for a theoretical test application that demonstrates these "
                "security concepts, with detailed explanations of the principles involved."
            )
        }
    }
    
    # Educational examples focusing on secure coding principles
    EXAMPLE_POCS = {
        'RCE': {
            'python': """
# EDUCATIONAL EXAMPLE: Vulnerable vs Secure Code Pattern
# This example shows how to safely handle external input in Python

# VULNERABLE PATTERN (DO NOT USE IN PRODUCTION)
def vulnerable_function(user_input):
    # This is unsafe as it directly executes user-controlled input
    import os
    result = os.system(f"echo {user_input}")  # VULNERABLE!
    return result

# SECURE PATTERN (RECOMMENDED)
def secure_function(user_input):
    # This uses a safe API that doesn't involve shell interpretation
    import subprocess
    # Use a list of arguments instead of string concatenation
    result = subprocess.run(["echo", user_input], capture_output=True, text=True)
    return result.stdout

# EDUCATIONAL NOTES:
# - Always validate and sanitize user input
# - Use secure APIs that separate code from data
# - Implement proper access controls and principle of least privilege
# - Consider using allowlists rather than blocklists
"""
        },
        'XSS': {
            'web': """
<!-- EDUCATIONAL EXAMPLE: Demonstrating XSS Prevention -->
<!-- This shows how to safely handle user input in a web application -->

<!-- VULNERABLE PATTERN (DO NOT USE IN PRODUCTION) -->
<div>
  <!-- Direct insertion of unescaped user input is dangerous -->
  <span id="vulnerable">Welcome, {{unescaped_user_input}}</span> <!-- VULNERABLE! -->
</div>

<!-- SECURE PATTERN (RECOMMENDED) -->
<div>
  <!-- Properly escaped user input prevents script execution -->
  <span id="secure">Welcome, {{escaped_user_input}}</span> <!-- SECURE -->
</div>

<script>
  // EDUCATIONAL IMPLEMENTATION
  
  // Secure approach - using proper escaping functions
  function secureRender(userInput) {
    // Use a proper HTML escaping function
    const escaped = escapeHTML(userInput);
    document.getElementById('secure').innerHTML = 'Welcome, ' + escaped;
  }
  
  // Helper function to properly escape HTML special characters
  function escapeHTML(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
  
  // EDUCATIONAL NOTES:
  // - Always escape user input before inserting into HTML
  // - Use framework-provided escaping mechanisms when available
  // - Consider Content Security Policy (CSP) as an additional defense
  // - Validate input on both client and server sides
</script>
"""
        },
        'SQLI': {
            'python': """
# EDUCATIONAL EXAMPLE: SQL Injection Prevention
# This demonstrates secure vs vulnerable database query patterns

import sqlite3

# VULNERABLE PATTERN (DO NOT USE IN PRODUCTION)
def vulnerable_query(user_input):
    conn = sqlite3.connect('example.db')
    cursor = conn.cursor()
    
    # Direct string concatenation is vulnerable to SQL injection
    query = f"SELECT * FROM users WHERE username = '{user_input}'"  # VULNERABLE!
    cursor.execute(query)
    
    results = cursor.fetchall()
    conn.close()
    return results

# SECURE PATTERN (RECOMMENDED)
def secure_query(user_input):
    conn = sqlite3.connect('example.db')
    cursor = conn.cursor()
    
    # Parameterized query prevents SQL injection
    query = "SELECT * FROM users WHERE username = ?"  # SECURE
    cursor.execute(query, (user_input,))
    
    results = cursor.fetchall()
    conn.close()
    return results

# EDUCATIONAL NOTES:
# - Always use parameterized queries or prepared statements
# - Never concatenate user input directly into SQL strings
# - Apply the principle of least privilege to database accounts
# - Consider using ORMs with secure defaults
"""
        }
    }
    
    # Educational framework-specific guidance
    FRAMEWORK_SPECIFIC_GUIDANCE = {
        'django': {
            'RCE': """
## Django Security Best Practices - Command Execution

When working with Django applications, consider these security principles:

1. **Avoid `os.system` and direct command execution**
   - Django provides safer alternatives for most system operations
   - Use built-in libraries instead of shell commands when possible

2. **Validate file paths carefully**
   - Use `os.path.abspath()` and check for directory traversal attempts
   - Implement proper validation of user-supplied filenames

3. **Handle template rendering securely**
   - Be cautious with custom template tags that might execute code
   - Avoid passing user input to template rendering contexts that use `{% include %}` with variables

4. **Django-specific recommendations:**
   - Keep `DEBUG = False` in production environments
   - Use Django's built-in functions for path operations
   - Audit uses of custom middleware for security issues
   - Consider Django security packages for additional protection
""",
            'XSS': """
## Django Security Best Practices - Cross-Site Scripting

When working with Django applications, consider these security principles:

1. **Leverage Django's auto-escaping**
   - Django templates automatically escape variables by default
   - Be extremely cautious when using the `|safe` filter or `mark_safe()`

2. **Be careful with custom template tags**
   - Custom template tags might bypass Django's auto-escaping
   - Ensure proper context-aware escaping in custom tags

3. **Handle JSON responses properly**
   - Use `django.core.serializers.json.DjangoJSONEncoder`
   - Set proper Content-Type headers
   - Consider using `json_script` template tag to safely embed JSON

4. **Django-specific recommendations:**
   - Use Django's form system which includes CSRF protection
   - Consider implementing Content Security Policy
   - Be cautious with `HttpResponse` content created from user input
   - Use `escape()` and `escapejs()` helper functions when appropriate
""",
            'SQLI': """
## Django Security Best Practices - SQL Injection

When working with Django applications, consider these security principles:

1. **Trust Django's ORM for query safety**
   - Django's ORM uses parameterized queries that prevent SQL injection
   - Leverage Django's QuerySet API for database operations

2. **Be cautious with raw queries**
   - Avoid `raw()` queries with user input
   - Never use string formatting or concatenation with SQL
   - When raw queries are necessary, use parameterized queries

3. **Special attention to dangerous methods**
   - Be careful with `.extra()` which can introduce vulnerabilities
   - Watch out for custom SQL in `RawSQL` objects
   - Avoid passing user input to `order_by()` without validation

4. **Django-specific recommendations:**
   - Use Django Forms for validation before database operations
   - Apply appropriate database permissions for Django applications
   - Consider using query logging in development to audit SQL
   - Be careful with custom manager methods that might build SQL strings
"""
        },
        'nodejs': {
            'RCE': """
## Node.js Security Best Practices - Command Execution

When working with Node.js applications, consider these security principles:

1. **Avoid dangerous APIs**
   - Use alternatives to `child_process.exec()` when possible
   - If exec is necessary, never pass user-controlled input to it
   - Prefer `child_process.execFile()` or `spawn()` with arrays of arguments

2. **Implement proper input validation**
   - Validate and sanitize all user inputs
   - Use allowlists rather than blocklists for validation
   - Consider using validation libraries like Joi or Yup

3. **Handle dependencies carefully**
   - Keep dependencies updated with `npm audit`
   - Be cautious with packages that use `eval()` or dynamic imports
   - Check for npm scripts that execute commands

4. **Node.js-specific recommendations:**
   - Use Node's `--secure-heap` flag for sensitive operations
   - Implement proper privilege separation
   - Consider containerization to limit exposure
   - Use `helmet` to set secure HTTP headers
""",
            'XSS': """
## Node.js Security Best Practices - Cross-Site Scripting

When working with Node.js applications, consider these security principles:

1. **Sanitize user input properly**
   - Use context-aware encoding for user-generated content
   - Consider libraries like DOMPurify for HTML sanitization
   - Be careful with template literals containing user input

2. **Leverage secure templating engines**
   - Most templating engines (EJS, Pug, Handlebars) escape by default
   - Be cautious with "unescaped" features like `{{{` in Handlebars
   - Maintain separation between code and data

3. **Implement additional browser protections**
   - Set Content-Security-Policy headers
   - Use SameSite cookies and CSRF protection
   - Consider implementing Subresource Integrity for external scripts

4. **Node.js-specific recommendations:**
   - Use `helmet` middleware to set security headers
   - For Express apps, be careful with user input in `res.send()`
   - In React apps, avoid `dangerouslySetInnerHTML`
   - In Vue apps, be cautious with `v-html` directives
""",
            'SQLI': """
## Node.js Security Best Practices - SQL Injection

When working with Node.js applications, consider these security principles:

1. **Use parameterized queries**
   - Never concatenate user input into SQL strings
   - Use parameterized queries or prepared statements
   - Consider using query builders like Knex.js

2. **Implement proper ORM usage**
   - Most ORMs like Sequelize or TypeORM offer protection if used correctly
   - Be cautious with "raw" query options in ORMs
   - Validate user input before using in queries

3. **Handle NoSQL databases properly**
   - NoSQL databases are also vulnerable to injection
   - Be careful with MongoDB query objects with user input
   - Use sanitization and validation for NoSQL operations

4. **Node.js-specific recommendations:**
   - Use environment variables for database credentials
   - Implement query logging in development
   - Consider using database middleware for query sanitization
   - Apply principle of least privilege for database connections
"""
        }
    }
    
    # Deep thinking prompt with educational focus
    DEEP_THINKING_SYSTEM_PROMPT = (
        "You are a security education specialist with a deep understanding of secure coding principles. "
        "Your goal is to create comprehensive educational materials that help developers understand "
        "security vulnerabilities and how to avoid them. Take a methodical approach to explaining security "
        "concepts, always focusing on the educational value and ethical application of this knowledge. "
        "Your explanations should be detailed, clear, and emphasize secure coding practices."
    )
    
    def __init__(self):
        """Initialize the prompt service."""
        pass
    
    def determine_vulnerability_type(self, analysis):
        """Determine vulnerability type"""
        if hasattr(analysis, 'vuln_type') and analysis.vuln_type:
            vuln_type = analysis.vuln_type.lower()
            if 'rce' in vuln_type:
                return 'RCE'
            elif 'xss' in vuln_type:
                return 'XSS'
            elif 'sqli' in vuln_type:
                return 'SQLI'
        return 'DEFAULT'
    
    def extract_database_type(self, analysis):
        """Dummy method for compatibility"""
        return 'Unknown'
    
    def extract_patch_analysis(self, analysis):
        """Extract patch analysis info"""
        if hasattr(analysis, 'patch_analysis') and analysis.patch_analysis:
            return analysis.patch_analysis
        return "No patch analysis available."
    
    def construct_prompt(self, poc):
        """Construct prompt for PoC generation"""
        analysis = poc.analysis
        
        # Determine vulnerability type
        vuln_type = self.determine_vulnerability_type(analysis)
        logger.info(f'Detected vulnerability type: {vuln_type}')
        
        # Get template
        template = self.VULN_TYPE_TEMPLATES.get(vuln_type, self.VULN_TYPE_TEMPLATES['DEFAULT'])
        
        # Extract advisory description
        advisory_description = "No advisory description available"
        if analysis.advisory and hasattr(analysis.advisory, 'description'):
            advisory_description = analysis.advisory.description
        
        # Basic template parameters
        template_params = {
            'advisory_description': advisory_description,
            'patch_analysis': self.extract_patch_analysis(analysis),
            'target_os': poc.target_os,
            'target_language_version': poc.target_language_version,
            'framework': self.determine_framework(poc),
            'exploitation_goal': poc.exploitation_goal,
            'additional_context_section': '',
            'example_poc_section': '',
            'framework_specific_guidance': ''
        }
        
        # Add database type for SQL injection
        if vuln_type == 'SQLI':
            template_params['database_type'] = self.extract_database_type(analysis)
        
        # Format the user prompt
        user_prompt = template['user_prompt_template'].format(**template_params)
        
        # Choose system prompt
        system_prompt = self.DEEP_THINKING_SYSTEM_PROMPT if poc.use_deep_thinking else template['system_prompt']
        
        return system_prompt, user_prompt
    
    def determine_framework(self, poc):
        """Determine target framework"""
        if 'django' in poc.target_language_version.lower():
            return 'django'
        elif 'node' in poc.target_language_version.lower():
            return 'nodejs'
        return 'generic'
    
    def prepare_example_poc_section(self, vuln_type, target_language):
        """Prepare example PoC section"""
        return "Example PoC section"
    
    def prepare_framework_guidance(self, framework, vuln_type):
        """Prepare framework guidance"""
        return "Framework guidance"