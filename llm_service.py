"""LLM service for keyword expansion using OpenAI."""
import json
from typing import List, Dict
from openai import OpenAI
import config


class LLMKeywordService:
    """Service for generating and expanding keywords using LLM."""
    
    def __init__(self, api_key: str = None):
        """Initialize OpenAI client."""
        self.client = OpenAI(api_key=api_key or config.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"  # Cost-effective model
    
    def expand_keywords(self, 
                       job_title: str,
                       company: str,
                       description: str,
                       current_keywords: List[Dict],
                       user_reaction: str) -> List[Dict]:
        """
        Generate keyword suggestions based on job feedback.
        
        Args:
            job_title: Title of the job
            company: Company name
            description: Job description (truncated)
            current_keywords: List of current keywords with weights and polarity
            user_reaction: 'like' or 'dislike'
            
        Returns:
            List of keyword suggestions with format:
            [{"keyword": str, "sentiment": str, "rationale": str}, ...]
        """
        # Truncate description to save tokens
        desc_preview = description[:500] if description else ""
        
        # Format current keywords
        kw_list = []
        for kw in current_keywords[:config.TOP_K]:
            polarity = "negative" if kw.get('is_negative') else "positive"
            kw_list.append(f"{kw['keyword']} (weight: {kw['weight']:.2f}, {polarity})")
        
        kw_summary = "\n".join(kw_list) if kw_list else "None yet"
        
        prompt = f"""You are helping to build an adaptive job recommendation profile for a user.

The user just {user_reaction}d this job:
- Title: {job_title}
- Company: {company}
- Description preview: {desc_preview}

Their current top keywords are:
{kw_summary}

Based on this {user_reaction}, suggest 8-10 keywords that should be added or reinforced in their profile. 
For each keyword:
- Common words that are used for searching jobs
- Extract skills, technologies, roles, industries, or job attributes
- Assign sentiment: "positive" (user wants this) or "negative" (user avoids this)
- Provide a brief rationale

Return ONLY a valid JSON array with this format:
[
  {{"keyword": "python", "sentiment": "positive", "rationale": "Job requires Python skills"}},
  {{"keyword": "entry level", "sentiment": "negative", "rationale": "User dislikes junior roles"}}
]

Focus on concrete, searchable terms. Avoid overly generic words."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a job recommendation assistant that extracts searchable keywords from job postings."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            # Try to find JSON array in response
            if content.startswith('['):
                result = json.loads(content)
            else:
                # Try to extract JSON from markdown code blocks
                start = content.find('[')
                end = content.rfind(']') + 1
                if start != -1 and end > start:
                    result = json.loads(content[start:end])
                else:
                    print(f"Could not parse LLM response: {content}")
                    return []
            
            # Validate and clean results
            validated = []
            for item in result:
                if isinstance(item, dict) and 'keyword' in item and 'sentiment' in item:
                    validated.append({
                        'keyword': str(item['keyword']).lower().strip(),
                        'sentiment': str(item['sentiment']).lower(),
                        'rationale': str(item.get('rationale', '')).strip()
                    })
            
            return validated
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Response content: {content}")
            return []
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return []
    
    def explain_recommendation(self, 
                             job_title: str,
                             matched_keywords: List[str]) -> str:
        """
        Generate explanation for why a job was recommended.
        
        Args:
            job_title: Job title
            matched_keywords: Keywords that matched
            
        Returns:
            Brief explanation string
        """
        if not matched_keywords:
            return "New opportunity in your field"
        
        kw_str = ", ".join(matched_keywords[:3])
        if len(matched_keywords) > 3:
            kw_str += f" (+{len(matched_keywords) - 3} more)"
        
        return f"Matches your interests: {kw_str}"


# Global service instance
_service = None

def get_llm_service() -> LLMKeywordService:
    """Get global LLM service instance."""
    global _service
    if _service is None:
        _service = LLMKeywordService()
    return _service
