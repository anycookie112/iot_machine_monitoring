
# from langchain_groq import ChatGroq
# import getpass
# import os
# from dotenv import load_dotenv
# import sys
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# import datetime
# from datetime import datetime, timedelta
# from textwrap import fill




# load_dotenv()

# # if "GROQ_API_KEY" not in os.environ:
# #     os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your Groq API key: ")
    

# llm = ChatGroq(
#     model="deepseek-r1-distill-llama-70b",
#     temperature=0,
#     max_tokens=None,
#     reasoning_format="parsed",
#     timeout=None,
#     max_retries=2,
#     # other params...
# )



# def llm_report(date):
#     from utils.daily import daily_report

#     date_transformed = datetime.strptime(date, "%Y-%m-%d").replace(hour=8, minute=0, second=0, microsecond=0)
#     df, _ = daily_report(date_transformed)

#     messages = [
#         (
#             "system",
#             "You are a helpful assistant that makes a short daily report with a pandas dataframe given to you. talk more on total machine stops and total machine downtime in words. Highlight the machines if either they stopped often or stopped for a long time(longer than 5 minutes), else just mention it in the report. if possible also output a version of the report in nepal language and finally output the report in a nice format",
#         ),
#         (
#             "user",  
#             f"Here is the data:\n\n{df.to_markdown(index=False)}\n\nPlease summarize it in a short report.",
#         ),
#     ]

#     ai_msg = llm.invoke(messages)
#     return ai_msg.content


# # def print_llm_report(content: str):
# #     # Optional: wrap text at 100 characters per line
# #     print("\n" + "="*40 + " DAILY MACHINE PERFORMANCE REPORT " + "="*40 + "\n")

# #     sections = content.split("---")
# #     if len(sections) == 2:
# #         english_report = sections[0].strip()
# #         nepali_report = sections[1].strip()

# #         print("[ENGLISH REPORT]\n")
# #         print(fill(english_report, width=100))
# #         print("\n" + "-"*100 + "\n")

# #         print("[NEPALI REPORT]\n")
# #         print(fill(nepali_report, width=100))
# #     else:
# #         print(fill(content, width=100))

# #     print("\n" + "="*100 + "\n")

# # Usage
# ai_msg = llm_report("2025-07-01")
# print(ai_msg)



