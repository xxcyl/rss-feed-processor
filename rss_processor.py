import feedparser
import json
import datetime
import time
import os
import sys
from github import Github
from bs4 import BeautifulSoup
from openai import OpenAI
import re

def get_openai_api_key():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # 如果環境變量中沒有 API 密鑰，您可以選擇從文件讀取或提示用戶輸入
        # 這裡我們選擇拋出一個異常
        raise ValueError("OPENAI_API_KEY not found in environment variables. Please set the OPENAI_API_KEY environment variable.")
    return api_key

try:
    client = OpenAI(api_key=get_openai_api_key())
except ValueError as e:
    print(f"Error: {e}")
    print("Please make sure to set the OPENAI_API_KEY environment variable before running this script.")
    sys.exit(1)

def parse_pubdate(pubdate_str):
    try:
        return datetime.datetime.strptime(pubdate_str, "%a, %d %b %Y %H:%M:%S %Z").isoformat()
    except ValueError:
        return datetime.datetime.now().isoformat()

def preprocess_content(text):
    # Remove journal name, date, and DOI information at the beginning
    text = re.sub(r'^.*?(?=ABSTRACT|OBJECTIVES)', '', text, flags=re.DOTALL)
    
    # Remove PMID and DOI information at the end
    text = re.sub(r'\s*PMID:.*$', '', text, flags=re.DOTALL)
    
    return text.strip()

def translate_title(text, target_language="zh-TW"):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a translator specializing in academic article titles. Translate the following title to {target_language}. Keep it concise and accurate, maintaining any technical terms."},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in translate_title: {e}")
        return text  # 返回原文，以防翻譯失敗

def translate_content(text, target_language="zh-TW"):
    try:
        preprocessed_text = preprocess_content(text)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"""You are a translator specializing in academic article abstracts across various disciplines. Translate the following content to {target_language}. Follow these guidelines:
                1. Maintain the concise and formal tone typical of academic abstracts.
                2. Preserve technical terms, translating them accurately. Provide the original English term in parentheses on first use for key concepts.
                3. Keep all numerical data and statistical information exactly as they appear in the source text.
                4. Maintain the original structure, typically including objectives, methods, results, and conclusions.
                5. Accurately translate research methodologies and key findings.
                6. Preserve abbreviations, providing a translation of the full term on first use if it's a key concept.
                7. Ensure any cited measurements or scales remain in their original format.
                8. Aim for clarity and precision in conveying the main points of the research."""},
                {"role": "user", "content": preprocessed_text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in translate_content: {e}")
        return text  # 返回原文，以防翻譯失敗

# fetch_rss, merge_feed_data, process_rss_sources, update_github_file, and load_existing_data functions remain the same

if __name__ == "__main__":
    rss_sources = {
        "Ear Hear": "https://pubmed.ncbi.nlm.nih.gov/rss/journals/8005585/?limit=5&name=Ear%20Hear&utm_campaign=journals"
        
    }
    
    github_token = os.environ.get("RSS_GITHUB_TOKEN")
    if not github_token:
        print("Error: RSS_GITHUB_TOKEN not found in environment variables.")
        print("Please set the RSS_GITHUB_TOKEN environment variable before running this script.")
        sys.exit(1)

    github_repo = "xxcyl/rss-feed-processor"
    file_path = "rss_data_bilingual.json"
    
    try:
        existing_data = load_existing_data(github_token, github_repo, file_path)
        data = process_rss_sources(rss_sources, existing_data)
        json_data = json.dumps(data, ensure_ascii=False, indent=4)
        
        commit_message = "Update bilingual RSS data"
        update_github_file(github_token, github_repo, file_path, json_data, commit_message)
        print("Bilingual RSS data has been processed and pushed to GitHub")
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
