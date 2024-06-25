import feedparser
import json
import datetime
import time
import os
from github import Github
from bs4 import BeautifulSoup
from openai import OpenAI
import re

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": f"You are a translator specializing in academic article titles. Translate the following title to {target_language}. Keep it concise and accurate, maintaining any technical terms."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content.strip()

def translate_content(text, target_language="zh-TW"):
    # Preprocess the content first
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

def fetch_rss(url):
    feed = feedparser.parse(url)
    entries = []
    for entry in feed.entries:
        content = entry.get('content', [{}])[0].get('value', '')
        if not content:
            content = entry.get('summary', '')
        
        soup = BeautifulSoup(content, 'html.parser')
        text_content = soup.get_text(separator='\n', strip=True)
        
        entry_data = {
            'title': entry.title,
            'link': entry.link,
            'published': parse_pubdate(entry.published),
            'full_content': text_content,
        }
        
        # Add translations with preprocessing
        entry_data['title_translated'] = translate_title(entry_data['title'])
        entry_data['full_content_translated'] = translate_content(entry_data['full_content'])
        
        entries.append(entry_data)
    
    return {
        'feed_title': feed.feed.title,
        'feed_link': feed.feed.link,
        'feed_updated': feed.feed.updated if 'updated' in feed.feed else datetime.datetime.now().isoformat(),
        'entries': entries
    }

# The rest of the code (merge_feed_data, process_rss_sources, update_github_file, load_existing_data) remains the same

if __name__ == "__main__":
    rss_sources = {
        "Ear Hear": "https://pubmed.ncbi.nlm.nih.gov/rss/journals/8005585/?limit=5&name=Ear%20Hear&utm_campaign=journals"
        
    }
    
    github_token = os.environ.get("RSS_GITHUB_TOKEN")
    github_repo = "xxcyl/rss-feed-processor"
    file_path = "rss_data_bilingual.json"
    
    existing_data = load_existing_data(github_token, github_repo, file_path)
    data = process_rss_sources(rss_sources, existing_data)
    json_data = json.dumps(data, ensure_ascii=False, indent=4)
    
    commit_message = "Update bilingual RSS data"
    update_github_file(github_token, github_repo, file_path, json_data, commit_message)
    print("Bilingual RSS data has been processed and pushed to GitHub")
