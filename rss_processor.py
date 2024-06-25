import feedparser
import json
import datetime
import time
import os
from github import Github
from bs4 import BeautifulSoup

def parse_pubdate(pubdate_str):
    try:
        return datetime.datetime.strptime(pubdate_str, "%a, %d %b %Y %H:%M:%S %Z").isoformat()
    except ValueError:
        return datetime.datetime.now().isoformat()

def fetch_rss(url):
    feed = feedparser.parse(url)
    entries = []
    for entry in feed.entries:
        content = entry.get('content', [{}])[0].get('value', '')
        if not content:
            content = entry.get('summary', '')
        
        soup = BeautifulSoup(content, 'html.parser')
        text_content = soup.get_text(separator='\n', strip=True)
        
        entries.append({
            'title': entry.title,
            'link': entry.link,
            'published': parse_pubdate(entry.published),
            'summary': entry.get('summary', ''),
            'full_content': text_content,
        })
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
        "Ear Hear": "https://pubmed.ncbi.nlm.nih.gov/rss/journals/8005585/?limit=15&name=Ear%20Hear&utm_campaign=journals",
        "Hear Res": "https://pubmed.ncbi.nlm.nih.gov/rss/journals/7900445/?limit=15&name=Hear%20Res&utm_campaign=journals"
    }
    
    github_token = os.environ.get("RSS_GITHUB_TOKEN")
    github_repo = "xxcyl/rss-feed-processor"
    file_path = "rss_data.json"

    existing_data = load_existing_data(github_token, github_repo, file_path)
    data = process_rss_sources(rss_sources, existing_data)
    json_data = json.dumps(data, ensure_ascii=False, indent=4)

    commit_message = "Update RSS data"
    update_github_file(github_token, github_repo, file_path, json_data, commit_message)
    print("RSS data has been processed and pushed to GitHub")
