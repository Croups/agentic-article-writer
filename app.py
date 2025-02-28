import streamlit as st
from openai import OpenAI
import json
import os
from dotenv import load_dotenv

# Import article generation and search modules
from article_generator import ArticleParameters, article_writer, generate_subqueries
from search_service import ContentSearchService

# Load environment variables and initialize OpenAI client
load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=api_key)

# Initialize search service with the API key
search_service = ContentSearchService(api_key)

def update_article(article_index, new_content):
    """Update an article in session state."""
    if 0 <= article_index < len(st.session_state.generated_articles):
        st.session_state.generated_articles[article_index] = new_content
                

def chat_with_ai(message, chat_history, article_index=None, current_article=None):
    """
    Send the user's message plus history to OpenAI, handle 'ARTICLE_UPDATE:' logic,
    and return the assistant's response.
    """
    system_prompt = (
        "You are an AI assistant specialized in helping users refine and improve their articles. "
        "When the user requests changes to the article, provide the complete updated version of the article. "
        "Start your response with 'ARTICLE_UPDATE:' when providing an updated version. "
        "Be constructive, specific, and friendly in your responses."
        "Ask questions to clarify the user's intent and provide helpful suggestions if you don't understand."
        "Don't change the general structure if not requested."
    )
    
    if current_article:
        system_prompt += f"\nHere is the current article:\n{current_article}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        *chat_history,
        {"role": "user", "content": message}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.3,  # Add some creativity while maintaining consistency
        presence_penalty=0.6,  # Encourage diverse responses
        frequency_penalty=0.5 # Reduce repetition
    )
    response_content = response.choices[0].message.content
    
    # If the response contains an article update, update the article in session state
    if "ARTICLE_UPDATE:" in response_content:
        update_parts = response_content.split("ARTICLE_UPDATE:", 1)
        new_article = update_parts[1].strip()
        if article_index is not None:
            update_article(article_index, new_article)
        return update_parts[0].strip() + "\n\nArticle has been updated."
    
    return response_content


def main():
    st.set_page_config(page_title="AI Article Generator", page_icon="📝", layout="wide")
    
    # Inject custom CSS for better chat styling, including an animation for article-updated messages
    st.markdown(
        """
        <style>
        /* Container for each message block */
        .message-block {
            padding: 1rem;
            border-radius: 15px;
            margin-bottom: 1rem;
            max-width: 85%;
            word-wrap: break-word;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .message-block:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
        }

        /* User messages */
        .user-message {
            background: linear-gradient(135deg, #6B8EFF, #4C6FFF);
            border: none;
            color: white;
        }

        /* Assistant messages */
        .assistant-message {
            background: white;
            border: 2px solid #EEF2FF;
            color: #2D3748;
        }

        /* Animate from success state to normal */
        @keyframes ephemeralHighlight {
            0% { 
                background: linear-gradient(135deg, #84E1BC, #4FD1C5);
                transform: scale(1.02);
            }
            100% { 
                background: white;
                transform: scale(1);
            }
        }

        /* Article updated animation */
        .article-updated {
            animation: ephemeralHighlight 1.5s cubic-bezier(0.4, 0, 0.2, 1) forwards;
            border: 2px solid #4FD1C5 !important;
            color: #234E52 !important;
        }

        /* Message containers */
        .assistant-container {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            padding: 0.5rem 1rem;
        }
        .user-container {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            padding: 0.5rem 1rem;
        }

        /* Add typing indicator for assistant messages */
        .assistant-message::after {
            content: '';
            display: inline-block;
            width: 4px;
            height: 4px;
            margin-left: 4px;
            background: #4C6FFF;
            border-radius: 50%;
            vertical-align: middle;
            animation: typing 1s infinite;
        }

        @keyframes typing {
            0%, 100% { opacity: 0; }
            50% { opacity: 1; }
        }

        /* Add some flair to strong tags within messages */
        .message-block strong {
            font-weight: 600;
            position: relative;
        }
        .user-message strong {
            color: #FFFFFF;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }
        .assistant-message strong {
            color: #4C6FFF;
        }

        /* Responsive adjustments */
        @media (max-width: 768px) {
            .message-block {
                max-width: 95%;
                margin-bottom: 0.8rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )    
    # Initialize session state variables if they are not already set
    if 'generated_articles' not in st.session_state:
        st.session_state.generated_articles = []
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'chat_input_field' not in st.session_state:
        st.session_state.chat_input_field = ""
    
    
    # Create two tabs: one for Article Generation and another for the ChatGPT-like Clone
    tab1, tab2 = st.tabs(["Article Generator", "ChatGPT-like Clone"])
    
    # --- Tab 1: Article Generator ---
    with tab1:
        st.title("AI Article Generator Dashboard")
        
        # Input fields for article generation
        topic = st.text_input("Article Topic", help="Enter the main topic of your article.")
        language_style = st.selectbox(
            "Article Style",
            options=["Daily Language", "Casual Language", "Business Language", "Technical", "Academic"],
            help="Select the writing style for your article."
        )
        keywords = st.text_area("Target Keywords", help="Enter each keyword on a new line.")
        num_articles = st.slider("Number of Articles", min_value=1, max_value=10, value=1)
        sources = st.text_area("Additional Source Links", help="Enter additional source URLs, one per line.")
        
        if st.button("Generate Articles"):
            if not topic or not keywords:
                st.error("Please enter both a topic and target keywords!")
            else:
                keyword_list = [k.strip() for k in keywords.split("\n") if k.strip()]
                source_list = [s.strip() for s in sources.split("\n") if s.strip()]
                default_sources = ["cheshirelife.co.uk", "theonlinelettingagents.co.uk","theguardian.com", "landlordzone.co.uk/news"]
                source_list.extend(default_sources)
                print("Source List: ", source_list)
                st.session_state.generated_articles = []  # Reset articles
                
                for i in range(num_articles):
                    st.write(f"### Generating Article {i+1}...")
                    
                    # 1. Create article parameters
                    article_params = ArticleParameters(
                        topic=topic,
                        language_style=language_style,
                        target_keywords=keyword_list,
                        sources=source_list
                    )
                    
                    # 2. Generate subqueries for the topic
                    sub_queries = generate_subqueries(topic)
                    try:
                        data = json.loads(sub_queries)
                        queries = data.get("queries", [])
                    except Exception as e:
                        st.error("Error parsing subqueries: " + str(e))
                        queries = []
                    
                    # 3. Use the search engine to extract context from the web
                    search_results = search_service.search_and_extract(queries, source_list, topic)
                    
                    # 4. Update article parameters with the retrieved context
                    updated_article_params = article_params.model_copy(update={"retrieved_content": search_results})

                user_prompt = (
                    "Write a comprehensive and engaging article that provides valuable information to readers. "
                    "IMPORTANT: Only mention information that is factually supported by the retrieved sources. "
                    "When citing information, explicitly mention the source (e.g., 'According to [Source]...'). "
                    "Do not include any source attribution in the text if the information wasn't retrieved from "
                    "an actual source. Avoid making up facts or statistics. If there's not enough information "
                    "on a specific point, acknowledge the limitation rather than inventing details."
                )
                    
                    # 5. Generate the article using the agent
                    response = article_writer.run_sync(
                        user_prompt=user_prompt,
                        deps=updated_article_params
                    )
                    article_content = response.data.content
                    article_sources = response.data.sources
                    article_title = response.data.title
                    st.session_state.generated_articles.append(article_content)
                    
                    st.markdown(f"## {article_title}")
                    st.markdown(article_content)
                    st.markdown("**Sources:**")
                    st.markdown(article_sources)
                    st.markdown("---")
                    st.markdown("---")
                
                st.success("Articles generated successfully!")
    
    # --- Tab 2: ChatGPT-like Clone for Article Modification ---
    with tab2:
        # Header section with clear button
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🗑️ Clear Chat"):
                st.session_state.chat_history = []
                st.rerun()

    # Rest of the chat display code...        
        # Sidebar: Select an article to modify
        with st.sidebar:
            st.header("Select Article to Modify")
            if st.session_state.generated_articles:
                article_options = {f"Article {i+1}": article for i, article in enumerate(st.session_state.generated_articles)}
                article_options["No Article"] = None
                selected_article_key = st.selectbox("Choose an article:", list(article_options.keys()))
                if selected_article_key != "No Article":
                    current_article = article_options[selected_article_key]
                    article_index = int(selected_article_key.split()[1]) - 1
                    st.markdown("### Selected Article:")
                    st.markdown(current_article)
                else:
                    current_article = None
                    article_index = None
            else:
                st.info("No articles available. Please generate an article first.")
                current_article = None
                article_index = None
        
        # Display chat history
        st.subheader("Chat History")
        for message in st.session_state.chat_history:
            role = message["role"]
            content = message["content"]
            
            # Determine if it's a user or assistant message
            if role == "user":
                # User container
                st.markdown(
                    f"""
                    <div class="user-container">
                        <div class="message-block user-message">
                            <strong>User:</strong> {content}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                # Assistant container
                if "Article has been updated." in content:
                    # This triggers the ephemeral green highlight animation
                    st.markdown(
                        f"""
                        <div class="assistant-container">
                            <div class="message-block assistant-message article-updated">
                                <strong>Assistant:</strong> {content}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"""
                        <div class="assistant-container">
                            <div class="message-block assistant-message">
                                <strong>Assistant:</strong> {content}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
        
        # Chat input + Send button
        user_input = st.text_input("Your message")
        if st.button("Send"):
            # If there's user input, append it and get the AI response
            if user_input.strip():
                # 1. Add the user message to chat history
                st.session_state.chat_history.append({"role": "user", "content": user_input.strip()})
                # 2. Get AI response
                ai_response = chat_with_ai(
                    user_input.strip(),
                    st.session_state.chat_history[:-1],
                    article_index,
                    current_article
                )
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                # 3. Clear the input field
                
                # # 4. Rerun so the chat updates immediately
                st.rerun()

if __name__ == "__main__":
    main()
