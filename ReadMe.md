
Projeyi uv ile çalıştırdım, paket çakışması olmasın diye, pip ile de yapabilirsin.

#install uv
pip install uv

#venv

uv venv .venv
#activate it

#requirements

uv pip install streamlit openai pydantic pydantic-ai python-dotenv requests beautifulsoup4

HOW TO RUN :

uv run streamlit run app.py