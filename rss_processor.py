import feedparser
import json
import datetime
import time
import os
from github import Github
from bs4 import BeautifulSoup
import openai

def parse_pubdate(pubdate_str):
    try:
        return datetime.datetime.strptime(pubdate_str, "%a, %d %b %Y %H:%M:%S %Z").isoformat()
    except ValueError:
        return datetime.datetime.now().isoformat()

def translate_text(text, target_language="zh-TW"):
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": f"You are a translator. Translate the following text to {target_language}."},
            {"role": "user", "content": text}
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
            'summary': entry.get('summary', ''),
            'full_content': text_content,
        }
        
        # Add translations
        entry_data['title_translated'] = translate_text(entry_data['title'])
        entry_data['summary_translated'] = translate_text(entry_data['summary'])
        entry_data['full_content_translated'] = translate_text(entry_data['full_content'])
        
        entries.append(entry_data)
    
    feed_data = {
        'feed_title': feed.feed.title,
        'feed_link': feed.feed.link,
        'feed_updated': feed.feed.updated if 'updated' in feed.feed else datetime.datetime.now().isoformat(),
        'entries': entries
    }
    
    # Add translation for feed title
    feed_data['feed_title_translated'] = translate_text(feed_data['feed_title'])
    
    return feed_data

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
        'feed_title_translated': new_data['feed_title_translated'],
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
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    github_repo = "xxcyl/rss-feed-processor"
    file_path = "rss_data_bilingual.json"
    
    existing_data = load_existing_data(github_token, github_repo, file_path)
    data = process_rss_sources(rss_sources, existing_data)
    json_data = json.dumps(data, ensure_ascii=False, indent=4)
    
    commit_message = "Update bilingual RSS data"
    update_github_file(github_token, github_repo, file_path, json_data, commit_message)
    print("Bilingual RSS data has been processed and pushed to GitHub")
