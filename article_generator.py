
from typing import List, Optional
from openai import OpenAI
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from utils.markdown import to_markdown
from dotenv import load_dotenv
import nest_asyncio
import os
import json
from dotenv import load_dotenv
from utils.markdown import to_markdown


# Apply nest_asyncio to allow async code in environments like notebooks.
nest_asyncio.apply()
load_dotenv()

class SubQuery(BaseModel):
    queries: List[str]

def generate_subqueries(topic: str) -> List[str]:
    """
    Generate 3 refined subqueries for a given topic by adding relevant keywords.

    The function sends a prompt to the GPT-4 API asking for subqueries that enhance the search intent.
    It expects a JSON array of strings as output.

    Parameters:
        topic (str): The base topic for which to generate subqueries.

    Returns:
        List[str]: A list of subqueries.
    """
    client = OpenAI()

    messages = [
        {
            "role": "system",
            "content": (
                "You are a creative and insightful search subquery generator. "
                "Given a base topic, your task is to generate 3 refined subqueries by adding relevant keywords "
                "that enhance the search intent. Each subquery should combine the base topic with an associated keyword or phrase. "
                "Return your answer as a JSON array of strings."
            )
        },
        {
            "role": "user",
            "content": (
                f"For the topic '{topic}', generate 3 subqueries by incorporating relevant keywords. "
                "For example, if the topic is 'bitcoin', you might output: "
                "['bitcoin trends 2025', 'bitcoin investment strategies', 'bitcoin market analysis']. "
                "If the topic is 'OpenAI', you might output: "
                "['openai pricing', 'openai employee reviews', 'openai latest research']."
            )
        }
    ]

    
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=messages,
        response_format=SubQuery  # Expected to be a JSON object with a field 'queries' (List[str])
    )

    return completion.choices[0].message.content

class ArticleParameters(BaseModel):
    topic: str
    language_style: str
    target_keywords: List[str]
    sources: Optional[List[str]] = None
    retrieved_content: Optional[str] = None
    
model = OpenAIModel("gpt-4o")


class Article(BaseModel):
    title: str
    content: str
    sources: Optional[List[str]] = None


article_writer = Agent(
    name="Article Writer Agent",
    model=model,
    result_type=Article,
    deps_type=ArticleParameters,
    retries=3,
    system_prompt="""You are an expert AI content creator writing high-quality articles.

    Key Guidelines:
    1. Content Quality:
    - Write engaging and well-structured content
    - Incorporate keywords naturally
    - Maintain consistent style and tone
    - Ensure accuracy and proper citations

    2. Style & Structure:
    - Match specified language style (Daily/Casual/Business/Technical/Academic)
    - Create clear section breaks and logical flow
    - Use engaging headers and subheaders
    - Begin with strong intro, end with clear conclusion

    3. Source & SEO:
    - Integrate source materials effectively
    - Place keywords strategically while maintaining readability
    - Provide proper citations
    - Create SEO-friendly structure

    Always aim for engaging, informative, and well-organized articles that serve their intended purpose."""
)

@article_writer.system_prompt
async def add_article_parameters(ctx: RunContext[ArticleParameters]) -> str:
    # Convert the article parameters into a detailed markdown representation.
    # This provides a clear, formatted description for the article writer model.
    details = (
        f"Topic: {ctx.deps.topic}\n"
        f"Language Style: {ctx.deps.language_style}\n"
        f"Target Keywords: {', '.join(ctx.deps.target_keywords)}\n"
        f"Sources: {ctx.deps.sources}\n"
    )
    if ctx.deps.retrieved_content:
        details += f"Retrieved Content: {ctx.deps.retrieved_content}\n"
    else:
        details += "Retrieved Content: None provided.\n"
    
    # Optionally converting to markdown for enhanced readability.
    deps_md = to_markdown(details)
    return f"Article details:\n{deps_md}"

if __name__ == "__main__":
    sampleArticle = ArticleParameters(
        topic="sustainable energy trends",
        language_style="analytical",
        target_keywords=["renewable energy", "innovation", "environment policy"],
        sources=["bbc.com", "nytimes.com"]
    )

    from search_service import ContentSearchService 
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    service = ContentSearchService(OPENAI_API_KEY)
    
    # Alt sorgular üretme
    user_deadline = "2022-01"
    sub_queries = generate_subqueries(topic=sampleArticle.topic)
    data = json.loads(sub_queries)
    queries = data["queries"]
    print("Generated Subqueries:", queries)
    
    # Arama ve içerik çekme
    search_results = service.search_and_extract(queries, sampleArticle.sources, sampleArticle.topic)
    print("Search Results:", search_results)
    
    # Makale parametrelerini güncelleme
    updatedArticle = sampleArticle.model_copy(update={"retrieved_content": search_results})
    
    # Agent'e makale oluşturma talimatı verme
    user_prompt = "Write a detailed article. Make sure it is interesting and engaging."
    response = article_writer.run_sync(user_prompt=user_prompt, deps=updatedArticle)
    
    print("Generated Article Content:")
    print(response.data.content)