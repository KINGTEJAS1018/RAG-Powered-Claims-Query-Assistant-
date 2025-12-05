import pandas as pd
import json
import os
import random
from pathlib import Path
from datetime import date, timedelta
from dotenv import load_dotenv

# --- AI IMPORTS ---
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document 
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain_core.prompts import ChatPromptTemplate

# 1. SETUP ENVIRONMENT
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Define Paths
PROJECT_ROOT = Path(__file__).parent.resolve()
CSV_PATH = PROJECT_ROOT / "medical_claims.csv"
POLICIES_PATH = PROJECT_ROOT / "policies.json"

# 2. ROBUST DATA GENERATOR (Kept your logic)
def generate_sample_csv(path: Path = CSV_PATH, n: int = 2000) -> bool:
    if path.exists():
        return False
    
    print("Generating new CSV...")
    conds = ["Diabetes", "Cardiology", "Respiratory", "Hypertension", "Orthopedic"]
    denial_reasons = ["eligibility", "medical_necessity", "pre-auth_missing", "coding_error", ""]
    rows = []
    start = date(2023, 1, 1)
    
    for i in range(n):
        svc = start + timedelta(days=random.randint(0, 900))
        status = random.choices(["approved", "denied", "pended"], weights=[0.7, 0.25, 0.05])[0]
        amount = round(max(10, random.gauss(500, 800)), 2)
        reason = random.choice(denial_reasons) if status == "denied" else ""
        
        rows.append({
            "claim_id": f"C{100000 + i}",
            "patient_id": f"P{1000 + (i % 500)}",
            "provider_id": f"D{200 + (i % 150)}",
            "service_date": svc.isoformat(),
            "submission_date": (svc + timedelta(days=random.randint(0, 60))).isoformat(),
            "status": status,
            "denial_reason": reason if reason else None,
            "amount": amount,
            "condition": random.choice(conds)
        })
    pd.DataFrame(rows).to_csv(path, index=False)
    return True

# Ensure CSV exists
generate_sample_csv()

# 3. ROBUST CSV LOADER
# We load the dataframe globally so the agent can access it
try:
    df = pd.read_csv(CSV_PATH)
    # Basic cleanup
    if "service_date" in df.columns:
        df["service_date"] = pd.to_datetime(df["service_date"], errors='coerce')
    print(f"[Backend] Loaded {len(df)} rows.")
except Exception as e:
    df = pd.DataFrame()
    print(f"[Backend] Error loading CSV: {e}")

# 4. INITIALIZE AI MODELS
# We only initialize AI if the Key exists. If not, the app will warn the user.
llm = None
embeddings = None
pandas_agent = None
vector_store = None

if GROQ_API_KEY:
    try:
        llm = ChatGroq(temperature=0, model_name="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # --- TOOL 1: PANDAS AGENT ---
        pandas_agent = create_pandas_dataframe_agent(
            llm,
            df,
            verbose=True,
            allow_dangerous_code=True,
            handle_parsing_errors=True
        )

        # --- TOOL 2: POLICY RAG ---
        # Load JSON
        if POLICIES_PATH.exists():
            with open(POLICIES_PATH, "r") as f:
                policy_data = json.load(f)
            
            docs = [Document(page_content=p['rule'], metadata={"source": "policies.json"}) for p in policy_data]
            vector_store = FAISS.from_documents(docs, embeddings)
            
    except Exception as e:
        print(f"AI Setup Error: {e}")

# 5. EXECUTION FUNCTIONS

def run_data_tool(query):
    """Uses the Pandas Agent to calculate answers."""
    if not pandas_agent:
        return "⚠️ AI Agent not initialized. Check API Key."
    
    prompt = (
        f"You are a data analyst. The dataframe 'df' is loaded. "
        f"Do NOT assume the data is only 5 rows. Calculate the answer using pandas code. "
        f"Question: {query}"
    )
    try:
        return pandas_agent.invoke(prompt)['output']
    except Exception as e:
        return f"Analysis Error: {e}"

def run_policy_tool(query):
    """Uses RAG to find policy rules."""
    if not vector_store:
        return "⚠️ Policy database not loaded."
    
    docs = vector_store.similarity_search(query)
    context = "\n".join([d.page_content for d in docs])
    
    rag_prompt = f"Context: {context}\n\nQuestion: {query}\n\nAnswer based on context:"
    return llm.invoke(rag_prompt).content

def route_query(query):
    """Decides if the question is about DATA or POLICY."""
    if not llm:
        return "DATA" # Default fallback
        
    prompt = ChatPromptTemplate.from_template(
        """
        Classify the user question into 'DATA' or 'POLICY'.
        - DATA: Questions about counting, math, amounts, trends, statistics, or 'how many'.
        - POLICY: Questions about rules, definitions, regulations, reasons, or text explanation.
        
        Return ONLY the word "DATA" or "POLICY".
        Question: {question}
        """
    )
    chain = prompt | llm
    return chain.invoke({"question": query}).content.strip().upper()

# 6. MAIN API FUNCTION
def ask_bot(user_input):
    if not GROQ_API_KEY:
        return "❌ GROQ_API_KEY not found. Please set it in your .env file."
        
    try:
        # Step 1: Route
        intent = route_query(user_input)
        
        # Step 2: Execute
        if "DATA" in intent:
            return run_data_tool(user_input)
        else:
            return run_policy_tool(user_input)
            
    except Exception as e:
        return f"System Error: {str(e)}"