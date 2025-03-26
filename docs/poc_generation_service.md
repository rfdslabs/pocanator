# PoC Generation System: Generation Service

## Overview

The PoC Generation Service is responsible for coordinating the generation of proof-of-concept code based on vulnerability information. It manages the workflow from prompt creation to OpenAI API interaction to result processing.

## Core Components

### PoCGenerationService

The `PoCGenerationService` class handles the end-to-end process of generating a PoC.

```python
class PoCGenerationService:
    def __init__(self, poc_request):
        self.poc_request = poc_request
        self.prompt_service = PoCPromptService(poc_request)
        self.openai_client = OpenAIClient()
        
    async def generate(self):
        """Asynchronously generate the PoC"""
        # Update status to processing
        self.poc_request.status = 'processing'
        self.poc_request.save()
        
        start_time = time.time()
        
        try:
            # Generate prompt
            prompt = self.prompt_service.generate_prompt()
            
            # Call OpenAI with appropriate parameters
            if self.poc_request.use_deep_thinking:
                response = await self._call_openai_with_deep_thinking(prompt)
            else:
                response = await self._call_openai(prompt)
                
            # Process and parse the response
            self._process_response(response)
            
            # Calculate completion time
            completion_time = int(time.time() - start_time)
            self.poc_request.completion_time = completion_time
            
            # Update status to completed
            self.poc_request.status = 'completed'
            self.poc_request.save()
            
        except Exception as e:
            # Handle errors
            self.poc_request.status = 'failed'
            self.poc_request.save()
            logger.error(f"PoC generation failed: {str(e)}")
            raise
```

## OpenAI Interaction

The service interacts with OpenAI using different strategies based on the complexity of the task and user preferences.

### Standard Generation

```python
async def _call_openai(self, prompt):
    """Call OpenAI with standard parameters"""
    messages = [
        {"role": "system", "content": "You are an expert security researcher..."},
        {"role": "user", "content": prompt}
    ]
    
    response = await self.openai_client.chat_completion(
        model="gpt-4o",
        messages=messages,
        temperature=0.2,  # Low temperature for more deterministic output
        max_tokens=2500
    )
    
    # Track token usage
    self.poc_request.tokens_used = response["tokens"]["total_tokens"]
    self.poc_request.save()
    
    return response
```

### Deep Thinking Mode

```python
async def _call_openai_with_deep_thinking(self, prompt):
    """Call OpenAI with parameters optimized for deep thinking"""
    messages = [
        {"role": "system", "content": "You are an expert security researcher..."},
        {"role": "user", "content": prompt}
    ]
    
    response = await self.openai_client.chat_completion(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,  # Higher temperature for more creative solutions
        max_tokens=4000,  # More tokens for detailed reasoning
    )
    
    # Track token usage
    self.poc_request.tokens_used = response["tokens"]["total_tokens"]
    self.poc_request.save()
    
    return response
```

## Response Processing

The service parses the AI's response to extract structured components.

```python
def _process_response(self, response):
    """Extract structured information from the AI response"""
    content = response["content"]
    
    # Extract code section
    code_match = re.search(r'```(?:\w+)?\s*([\s\S]*?)\s*```', content)
    if code_match:
        self.poc_request.code = code_match.group(1).strip()
    
    # Extract explanation section
    explanation_match = re.search(r'EXPLANATION:\s*([\s\S]*?)(?:\d+\.|SETUP INSTRUCTIONS:)', content)
    if explanation_match:
        self.poc_request.explanation = explanation_match.group(1).strip()
    
    # Extract setup instructions
    setup_match = re.search(r'SETUP INSTRUCTIONS:\s*([\s\S]*?)(?:\d+\.|SECURITY WARNINGS:)', content)
    if setup_match:
        self.poc_request.setup_instructions = setup_match.group(1).strip()
    
    # Extract security warnings
    warnings_match = re.search(r'SECURITY WARNINGS:\s*([\s\S]*?)(?:\d+\.|$)', content)
    if warnings_match:
        self.poc_request.security_warnings = warnings_match.group(1).strip()
    
    self.poc_request.save()
```

## Asynchronous Processing

For better performance and user experience, the PoC generation is handled asynchronously.

```python
# In views.py
@login_required
def request_poc(request, analysis_id):
    """View to handle PoC generation requests"""
    if request.method == 'POST':
        form = PoCRequestForm(request.POST)
        if form.is_valid():
            analysis = get_object_or_404(Analysis, pk=analysis_id)
            
            # Create a new PoC request
            poc_request = ProofOfConcept.objects.create(
                analysis=analysis,
                user=request.user,
                target_os=form.cleaned_data['target_os'],
                target_language_version=form.cleaned_data['target_language_version'],
                exploitation_goal=form.cleaned_data['exploitation_goal'],
                use_deep_thinking=form.cleaned_data['use_deep_thinking'],
                additional_context=form.cleaned_data['additional_context'],
                status='requested'
            )
            
            # Trigger asynchronous generation
            generate_poc.delay(poc_request.id)
            
            return redirect('poc_status', poc_id=poc_request.id)
```

```python
# In tasks.py
@shared_task
def generate_poc(poc_request_id):
    """Celery task for asynchronous PoC generation"""
    poc_request = ProofOfConcept.objects.get(id=poc_request_id)
    
    service = PoCGenerationService(poc_request)
    try:
        # Run the generation asynchronously
        service.generate()
    except Exception as e:
        logger.error(f"Error generating PoC {poc_request_id}: {str(e)}")
        # Update status to failed
        poc_request.status = 'failed'
        poc_request.save()
```

## Status Monitoring

To keep users informed of progress, a status monitoring endpoint is provided.

```python
# In views.py
def poc_status_api(request, poc_id):
    """API endpoint for checking PoC generation status"""
    poc = get_object_or_404(ProofOfConcept, pk=poc_id)
    
    data = {
        'status': poc.status,
        'created_at': poc.created_at,
        'updated_at': poc.updated_at,
    }
    
    if poc.status == 'completed':
        data['completion_time'] = poc.completion_time
    
    return JsonResponse(data)
```

## Error Handling

The service includes robust error handling to manage various failure scenarios.

```python
try:
    # Generate prompt and call OpenAI
    # ...
except openai.OpenAIError as e:
    # Handle OpenAI-specific errors
    logger.error(f"OpenAI API error: {str(e)}")
    self.poc_request.status = 'failed'
    self.poc_request.save()
    raise
except Exception as e:
    # Handle general errors
    logger.error(f"Unexpected error during PoC generation: {str(e)}")
    self.poc_request.status = 'failed'
    self.poc_request.save()
    raise
```

## Future Enhancements

1. **Multi-Step Generation**: Break complex PoCs into multiple generation steps
2. **Iterative Refinement**: Automatically refine generated PoCs based on internal validation
3. **Alternative Models**: Support for different AI models based on the task complexity
4. **Caching**: Cache common prompts and responses to improve performance
5. **Parallel Processing**: Generate multiple PoC variants in parallel for comparison