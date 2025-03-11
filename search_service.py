__all__ = ['search_and_filter']


import time
from pydantic import BaseModel
import requests
import openai
import json
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from typing import List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

# Configuration
class Config:
    SEARCH_API_URL = "http://44.221.64.85:8080/search"
    SERPER_API_URL = "https://google.serper.dev/search"
    SERPER_API_KEY = "0fbfb008b1822bd4e5433669a48429219b64b44c"  # In production, this should be in env vars
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    DEFAULT_TIMEOUT = 10
    MIN_PARAGRAPH_LENGTH = 50
    MAX_RELEVANT_RESULTS = 10  # Maximum number of relevant results to return

# Data Models
@dataclass
class SearchResult:
    title: str
    url: str
    content: Optional[str] = None
    extracted_content: Optional[str] = None

class RelevantResult(BaseModel):
    title: str
    url: str
    
class RelevantResults(BaseModel):
    results: List[RelevantResult]

# Search Client
class SearchClient:
    def __init__(self):
        self.headers = {"User-Agent": Config.USER_AGENT}
    
    def search(self, query: str, sources: List[str] = None) -> List[dict]:
        results = []
        for source in sources or [""]:
            search_query = f"{query} site:{source.strip()}" if source else query
            params = {
                "q": search_query,
                "format": "json",
                "engines": "google"
            }
            
            try:
                response = requests.get(
                    Config.SEARCH_API_URL,
                    params=params,
                    headers=self.headers,
                    timeout=Config.DEFAULT_TIMEOUT
                )
                response.raise_for_status()
                data = response.json()
                results.extend(data.get("results", []))
            except Exception as e:
                print(f"Search error for '{search_query}': {e}")
        
        return results
    
    def search_serper(self, query: str, sources: List[str] = None) -> List[dict]:
        """Backup search method using Serper API"""
        results = []
        
        for source in sources or [""]:
            try:
                search_query = f"{query} site:{source.strip()}" if source else query
                
                # Prepare the request to Serper API
                payload = json.dumps({
                    "q": search_query
                })
                
                headers = {
                    'X-API-KEY': Config.SERPER_API_KEY,
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(
                    Config.SERPER_API_URL, 
                    headers=headers, 
                    data=payload,
                    timeout=Config.DEFAULT_TIMEOUT
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Extract relevant results from Serper API response
                # Serper API has a different response format, so we need to transform it
                organic_results = data.get("organic", [])
                
                for item in organic_results:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", "")
                    })
                
                print(f"Serper API backup search for '{search_query}' found {len(organic_results)} results")
                
            except Exception as e:
                print(f"Serper API search error for '{query}': {e}")
        
        return results

# Content Extractor
class ContentExtractor:
    def __init__(self):
        self.headers = {"User-Agent": Config.USER_AGENT}
    
    def extract_paragraphs(self, url: str) -> str:
        try:
            response = requests.get(url, headers=self.headers, timeout=Config.DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            paragraphs = soup.find_all("p")
            
            content = "\n\n".join(
                p.get_text(strip=True) 
                for p in paragraphs 
                if len(p.get_text(strip=True)) > Config.MIN_PARAGRAPH_LENGTH
            )
            return content
            
        except Exception as e:
            print(f"Extraction error for {url}: {e}")
            return ""

# LLM Filter
class LLMFilter:
 
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
    
    def filter_relevant(self, topic: str, results: List[dict]) -> List[dict]:
        minimal_results = [
            {'title': result.get('title', ''), 'url': result.get('url', '')}
            for result in results 
            if result.get('title') and result.get('url')
        ]
        
        print(f"Minimal results: {minimal_results}")
        
        try:
            response = self.client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a search result filter. Analyze the search results and return ONLY the most relevant results.
                        Important rules:
                        1. Return maximum {Config.MAX_RELEVANT_RESULTS} results
                        2. Sort by relevance (most relevant first)
                        3. Only include highly relevant results"""
                    },
                    {
                        "role": "user",
                        "content": f"Topic: {topic}\nResults: {json.dumps(minimal_results)}"
                    }
                ],
                temperature=0.0,
                response_format=RelevantResults 
            )
            
            result = response.choices[0].message.parsed
            
            # Convert RelevantResult objects to minimal_result format dictionaries
            filtered_results = [{'title': item.title, 'url': item.url} for item in result.results]
            print(f"filtered_results: {filtered_results}")
            
            return filtered_results
        
            
        except Exception as e:
            print(f"LLM filtering error: {e}")
            return minimal_results

# Main Service
class ContentSearchService:
    def __init__(self, openai_api_key: str):
        self.search_client = SearchClient()
        self.content_extractor = ContentExtractor()
        self.llm_filter = LLMFilter(openai_api_key)
    
    def search_and_extract(self, queries: List[str], sources: List[str], topic: str) -> str:
        # 1. Search with primary method
        all_results = []
        for query in queries:
            results = self.search_client.search(query, sources)
            all_results.extend(results)
        
        # If primary search returns no results, use backup Serper API
        if not all_results:
            print("Primary search returned no results. Using Serper API as backup.")
            for query in queries:
                backup_results = self.search_client.search_serper(query, sources)
                all_results.extend(backup_results)
                
            print(f"Serper API backup search found {len(all_results)} results")
        
        # 2. Filter
        filtered_results = self.llm_filter.filter_relevant(topic, all_results)
        
        # 3. Extract content
        final_results = []
        for result in filtered_results:
            url = result.get("url", "")
            content = self.content_extractor.extract_paragraphs(url)
            result["extracted_content"] = content
            final_results.append(result)
        
        # 4. Format output
        return self._format_markdown(topic, final_results)
    
    def _format_markdown(self, topic: str, results: List[dict]) -> str:
        lines = [
            "# Search and Extracted Content\n",
            f"**Topic:** {topic or 'Not specified'}\n",
            "## Relevant Search Results\n"
        ]
        
        if not results:
            lines.append("No relevant results found.")
            return "\n".join(lines)
        
        for i, result in enumerate(results, 1):
            lines.extend([
                f"### Result {i}: [{result.get('title', 'No Title')}]({result.get('url', '#')})\n",
                "**Extracted Content:**\n",
                "```\n" + (result.get('extracted_content') or "No content extracted.") + "\n```\n"
            ])
        
        return "\n".join(lines)
    
# Example usage
if __name__ == "__main__":
    # Get OpenAI API key from environment variable
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    # Initialize the service
    service = ContentSearchService(OPENAI_API_KEY)
    
    # Define search parameters
    queries = ["openai"]
    sources = ["theguardian.com", "wikipedia.org"]
    topic = "openai"
    
    # Run the search and extraction
    output = service.search_and_extract(queries, sources, topic)
    print(output)
