# ReportGPT - GitHub Security Advisory Analysis and PoC Generation Platform

ReportGPT is a comprehensive platform for analyzing GitHub security advisories, extracting commits, generating vulnerability reports, and creating educational proof-of-concept code examples. It leverages OpenAI to analyze vulnerabilities, understand patches, and generate security educational content.

## Features

- Fetch GitHub security advisories based on search queries
- Extract commit information associated with security advisories
- Generate interactive HTML reports of advisories with commits
- Filter advisories to focus only on those with commits (more useful for PoC generation)
- Analyze individual advisories with OpenAI to determine vulnerability type, severity, and PoC feasibility
- Generate detailed advisory reports with PoC feasibility assessments
- Create educational proof-of-concept code examples with advanced prompt engineering
- Provide framework-specific security best practices and guidance

### Enhanced PoC Generation Features

The PoC generation system uses advanced prompt engineering techniques:

1. **Multi-stage Prompting**: Breaks down PoC generation into distinct stages:
   - Vulnerability Understanding
   - Exploitation Design
   - Code Implementation
   - Documentation

2. **Example-guided Generation**: Includes concrete code examples for different vulnerability types:
   - Remote Code Execution (RCE) examples
   - Cross-Site Scripting (XSS) examples
   - SQL Injection (SQLI) examples

3. **Framework-specific Security Guidance**: Provides specialized guidance for:
   - Django framework security
   - Node.js framework security
   - And other popular frameworks

## Installation

### Command-line Tool (Original)

1. Clone the repository
2. Install the required packages:
   ```
   pip install requests beautifulsoup4 lxml openai python-dotenv
   ```
3. Create a `.env` file with your OpenAI API key (for analysis functionality):
   ```
   openaikey=your_openai_api_key_here
   ```

### Full Web Platform (Docker)

1. Clone the repository
2. Create and configure the environment file:
   ```
   cp .env.example .env
   # Edit .env with your configurations including OpenAI API key
   ```
3. Start the application with Docker Compose:
   ```
   docker-compose up -d
   ```
4. Access the application at http://localhost:8000

## Usage

### Command-line Tool

#### Generate HTML Report of Advisories

```
python reportgpt.py [--pages N] [--only-with-commits] [--query "custom search query"]
```

Options:
- `--pages N`: Number of GitHub advisory pages to fetch (1-50)
- `--only-with-commits`: Only process advisories that have associated commits
- `--query`: Custom search query to use instead of the default "rce type:reviewed rce"

If run without arguments, you'll be prompted for the number of pages to fetch and whether to filter by commits.

#### Analyze Individual Advisory with OpenAI

```
python reportgpt.py --gpthack https://github.com/advisories/GHSA-xxxx-xxxx-xxxx
```

This will:
1. Fetch the advisory information
2. Check for related commits
3. Fetch patch diffs for up to 3 commits
4. Send the information to OpenAI for analysis
5. Generate a detailed report including:
   - Vulnerability explanation
   - Patch analysis
   - Impact summary
   - Patch effectiveness score
   - PoC feasibility analysis
   - Summary table with key metrics

### Web Platform

The web platform provides a comprehensive UI for managing advisories, analyses, and educational PoC generation:

1. **Advisory Management**
   - Import advisories from GitHub
   - Browse and search advisories
   - View detailed advisory information

2. **Analysis Creation**
   - Generate AI-powered analyses of vulnerabilities
   - View detailed reports with patch analysis
   - Understand vulnerability mechanics and impact

3. **Educational PoC Generation**
   - Request educational code examples for vulnerabilities
   - Specify target environment, language, and framework
   - Receive detailed explanations of security concepts
   - Learn about vulnerable code patterns and secure alternatives

4. **Security Best Practices**
   - Access framework-specific security guidance
   - Learn about proper input validation, secure APIs, and more
   - Understand security principles with concrete examples

## Why Filter by Commits?

Filtering advisories by commits is particularly useful when:

1. Generating PoCs: Advisories with commits provide concrete code changes that fix vulnerabilities, giving valuable insight for PoC development
2. Training AI models: Having both vulnerability descriptions and patch diffs creates better training data
3. Research efficiency: Focusing only on advisories with available code changes can save significant time
4. Better analysis: OpenAI can provide more accurate and useful analysis when it has access to patch information

## Output Files

- `github_advisory_report.html`: Interactive HTML report with all fetched advisories and their commits
- `GHSA-xxxx-xxxx-xxxx_analysis.md`: Markdown file with detailed analysis (when using --gpthack)

## Example

```
python reportgpt.py --pages 5 --only-with-commits --query "sql injection type:reviewed"
```

This will:
1. Fetch 5 pages of GitHub security advisories related to SQL injection
2. Filter to only include advisories with commits
3. Generate an HTML report with all discovered advisories and their commits