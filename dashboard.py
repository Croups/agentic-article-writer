# FIRST VERSION


import streamlit as st
from openai import OpenAI
import json
from dotenv import load_dotenv
import os
import requests

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=api_key)


def create_sample_article(topic, language_style, target_keywords):
    system_prompt = f"""
    You are a journalist. You are given a topic and you need to create a sample article about it.
    The article should be 100 words long and should be written in a way that is easy to understand.
    The article should be written in a way that is engaging and interesting to read.
    The article should be written in a way that is easy to understand.
    Here is the topic: {topic}
    Here is the language style: {language_style}
    Here is the target keywords: {target_keywords}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",  # Changed from gpt-4o to gpt-4
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": topic},
        ]
    )
    return response.choices[0].message.content

def update_article(article_index, new_content):
    if 0 <= article_index < len(st.session_state.generated_articles):
        st.session_state.generated_articles[article_index] = new_content

def chat_with_ai(message, chat_history, article_index=None, current_article=None):
    system_prompt = """
    You are an AI assistant specialized in helping users refine and improve their articles.
    When the user requests changes to the article, provide the complete updated version of the article.
    Start your response with 'ARTICLE_UPDATE:' when providing an updated version.
    Be constructive, specific, and friendly in your responses.
    """
    
    if current_article:
        system_prompt += f"\nHere is the current article:\n{current_article}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        *chat_history,
        {"role": "user", "content": message}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )
    response_content = response.choices[0].message.content
    
    # Check if response contains article update
    if "ARTICLE_UPDATE:" in response_content:
        update_parts = response_content.split("ARTICLE_UPDATE:", 1)
        new_article = update_parts[1].strip()
        if article_index is not None:
            update_article(article_index, new_article)
        return update_parts[0].strip() + "\n\nArticle has been updated."
    
    return response_content

def main():
    st.set_page_config(page_title="AI Article Generator", page_icon="📝", layout="wide")
    
    # Initialize session state for chat history
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'generated_articles' not in st.session_state:
        st.session_state.generated_articles = []

    # Create tabs
    tab1, tab2 = st.tabs(["Article Generator", "ChatGPT-like clone"])
    
    with tab1:
        st.title("AI Article Generator Dashboard")
        
        # Sidebar for configuration
        st.sidebar.header("Configuration")
        
        # Target Keywords Input
        st.subheader("Target Keywords")
        keywords = st.text_area(
            "Enter your target keywords (one per line)",
            help="Enter each keyword in a new line"
        )
        
        # Article Language Style
        st.subheader("Article Style")
        language_style = st.selectbox(
            "Choose article language style",
            options=["Daily Language", "Casual Language", "Business Language"],
            help="Select the tone and style of your article"
        )
        
        # Topic Input
        st.subheader("Article Topic")
        topic = st.text_input(
            "Enter your article topic",
            help="Provide the main topic or subject of your article"
        )
        
        # Number of Articles
        st.subheader("Number of Articles")
        num_articles = st.slider(
            "Select number of articles to generate",
            min_value=1,
            max_value=10,
            value=1,
            help="Choose how many articles you want to generate"
        )
        
        # Extra Source Links
        st.subheader("Additional Sources")
        source_links = st.text_area(
            "Enter additional source links (one per line)",
            help="Add external sources to enhance article generation"
        )
        
        # Update the generation part to store articles in session state
        if st.button("Generate Articles", type="primary"):
            if not keywords or not topic:
                st.error("Please enter both keywords and topic!")
            else:
                keyword_list = [k.strip() for k in keywords.split('\n') if k.strip()]
                source_list = [s.strip() for s in source_links.split('\n') if s.strip()]
                
                st.session_state.generated_articles = []  # Reset articles
                
                with st.spinner("Generating your articles..."):
                    for i in range(num_articles):
                        st.subheader(f"Article {i+1}")
                        try:
                            article = create_sample_article(
                                topic=topic,
                                language_style=language_style,
                                target_keywords=", ".join(keyword_list)
                            )
                            st.session_state.generated_articles.append(article)
                            st.write(article)
                            st.markdown("---")
                        except Exception as e:
                            st.error(f"Error generating article {i+1}: {str(e)}")
                    
                    st.success(f"""
                    Successfully generated {num_articles} articles with:
                    - Keywords: {', '.join(keyword_list)}
                    - Style: {language_style}
                    - Topic: {topic}
                    - Additional sources: {len(source_list)}
                    """)
    
    with tab2:
        st.title("ChatGPT-like clone")
        
        # Add article selection to sidebar
        with st.sidebar:
            st.header("Article Selection")
            
            if st.session_state.generated_articles:
                # Add article selector
                article_options = {f"Article {i+1}": article 
                                for i, article in enumerate(st.session_state.generated_articles)}
                article_options["No Article"] = None
                
                selected_article_key = st.selectbox(
                    "Select which article to discuss:",
                    options=list(article_options.keys()),
                    key="article_selector"
                )
                
                # Display selected article
                if selected_article_key != "No Article":
                    with st.expander("View Selected Article", expanded=True):
                        st.markdown(article_options[selected_article_key])
                
                # Add clear chat button
                if st.button("Clear Chat History"):
                    st.session_state.messages = []
                    st.rerun()
            else:
                st.info("No articles generated yet. Please generate articles in the Article Generator tab first.")

        # Add custom CSS for chat interface

        # Initialize messages in session state
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Main chat container
        chat_container = st.container()
        
        # Chat input at the bottom
        prompt = st.chat_input("Send a message")
        
        # Display messages in the container
        with chat_container:
            st.markdown('<div class="main-chat-container">', unsafe_allow_html=True)
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
            st.markdown('</div>', unsafe_allow_html=True)

        # Handle new messages
        if prompt:
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Get selected article and index
            current_article = None
            article_index = None
            if 'article_selector' in st.session_state and st.session_state.article_selector != "No Article":
                article_index = int(st.session_state.article_selector.split()[1]) - 1
                current_article = article_options[st.session_state.article_selector]
            
            # Get AI response
            response = chat_with_ai(
                prompt,
                [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[:-1]],
                article_index,
                current_article
            )
            
            # Add assistant response
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            # Rerun to update the chat
            st.rerun()

if __name__ == "__main__":
    main()
