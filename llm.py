
from langchain_groq import ChatGroq
import getpass
import os
from dotenv import load_dotenv

from utils.daily import daily_report
import datetime
from datetime import datetime, timedelta


date = datetime.strptime("2025-06-16", "%Y-%m-%d").replace(hour=8, minute=0, second=0, microsecond=0)
df, _ = daily_report(date)

load_dotenv()

if "GROQ_API_KEY" not in os.environ:
    os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your Groq API key: ")
    

llm = ChatGroq(
    model="deepseek-r1-distill-llama-70b",
    temperature=0,
    max_tokens=None,
    reasoning_format="parsed",
    timeout=None,
    max_retries=2,
    # other params...
)

messages = [
    (
        "system",
        "You are a helpful assistant that makes a short daily report with a pandas dataframe given to you.",
    ),
    (
        "user",  # ✅ Not "human" — use "user" for OpenAI/Groq-style
        f"Here is the data:\n\n{df.to_markdown(index=False)}\n\nPlease summarize it in a short report.",
    ),
]

ai_msg = llm.invoke(messages)
ai_msg


print(ai_msg.content)

