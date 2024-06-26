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
    text = re.sub(r'^.*?(?=ABSTRACT|OBJECTIVES)', '', text, flags=re.DOTALL)
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
        return text

def translate_content(text, target_language="zh-TW"):
    try:
        preprocessed_text = preprocess_content(text)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"""You are an expert translator specializing in academic article abstracts. Translate the following content into {target_language}, adhering to these guidelines:

1. Maintain the concise and formal tone typical of academic abstracts.
2. Accurately translate technical terms. For key concepts, provide the original English term in parentheses on first use.
3. Keep all numerical data and statistical information exactly as they appear in the source text.
4. Maintain the original structure, typically including objectives, methods, results, and conclusions.
5. Accurately translate research methodologies and key findings.
6. Preserve abbreviations, providing a translation of the full term on first use if it's a key concept.
7. Ensure any cited measurements or scales remain in their original format.
8. Aim for clarity and precision in conveying the main points of the research.
9. Use the following emojis and Markdown formatting:

🔎 **背景/引言**

[Background content here]

🧪 **方法**

[Methods content here]

📊 **結果**

[Results content here]

🏁 **結論**

[Conclusion content here]

Ensure the translation accurately reflects the original content while optimizing readability in the target language. Follow the exact format provided above, including emojis and Markdown formatting."""},
                {"role": "user", "content": preprocessed_text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in translate_content: {e}")
        return text

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
        
        entry_data['title_translated'] = translate_title(entry_data['title'])
        entry_data['full_content_translated'] = translate_content(entry_data['full_content'])
        
        entries.append(entry_data)
    
    return {
        'feed_title': feed.feed.title,
        'feed_link': feed.feed.link,
        'feed_updated': feed.feed.updated if 'updated' in feed.feed else datetime.datetime.now().isoformat(),
        'entries': entries
    }

def merge_feed_data(old_data, new_data):
    merged_entries = old_data['entries']
    new_entries = new_data['entries']
    
    existing_links = set(entry['link'] for entry in merged_entries)
    
    for entry in new_entries:
        if entry['link'] not in existing_links:
            merged_entries.append(entry)
            existing_links.add(entry['link'])
    
    merged_entries.sort(key=lambda x: x['published'], reverse=True)
    
    return {
        'feed_title': new_data['feed_title'],
        'feed_link': new_data['feed_link'],
        'feed_updated': new_data['feed_updated'],
        'entries': merged_entries
    }

def process_rss_sources(sources, existing_data):
    result = existing_data or {}
    for name, url in sources.items():
        new_feed_data = fetch_rss(url)
        if name in result:
            result[name] = merge_feed_data(result[name], new_feed_data)
        else:
            result[name] = new_feed_data
    return result

def update_github_file(token, repo_name, file_path, content, commit_message):
    g = Github(token)
    repo = g.get_repo(repo_name)
    
    try:
        file = repo.get_contents(file_path)
        repo.update_file(file_path, commit_message, content, file.sha)
    except:
        repo.create_file(file_path, commit_message, content)

def load_existing_data(token, repo_name, file_path):
    g = Github(token)
    repo = g.get_repo(repo_name)
    try:
        file = repo.get_contents(file_path)
        content = file.decoded_content.decode('utf-8')
        return json.loads(content)
    except:
        return None

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
