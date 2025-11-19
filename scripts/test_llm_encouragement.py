from llm_service import get_llm_service

llm = get_llm_service()
print('Running generate_encouragement (may use fallback if API not available)')
msg = llm.generate_encouragement()
print('Encouragement:', msg)
