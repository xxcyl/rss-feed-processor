# rss_processor.py

import feedparser
import json
import datetime
import time
import os
from github import Github

def parse_pubdate(pubdate_str):
    try:
        return datetime.datetime.strptime(pubdate_str, "%a, %d %b %Y %H:%M:%S %Z").isoformat()
    except ValueError:
        return datetime.datetime.now().isoformat()

def fetch_rss(url):
    feed = feedparser.parse(url)
    entries = []
    for entry in feed.entries:
        entries.append({
            'title': entry.title,
            'link': entry.link,
            'published': parse_pubdate(entry.published),
            'summary': entry.summary
        })
    return {
        'feed_title': feed.feed.title,
        'feed_link': feed.feed.link,
        'feed_updated': feed.feed.updated if 'updated' in feed.feed else datetime.datetime.now().isoformat(),
        'entries': entries
    }

def process_rss_sources(sources):
    result = {}
    for name, url in sources.items():
        result[name] = fetch_rss(url)
    return result

def update_github_file(token, repo_name, file_path, content, commit_message):
    g = Github(token)
    repo = g.get_repo(repo_name)
    
    try:
        file = repo.get_contents(file_path)
        repo.update_file(file_path, commit_message, content, file.sha)
    except:
        repo.create_file(file_path, commit_message, content)

if __name__ == "__main__":
    rss_sources = {
        "Ear Hear": "https://pubmed.ncbi.nlm.nih.gov/rss/journals/8005585/?limit=15&name=Ear%20Hear&utm_campaign=journals",
        "Hear Res": "https://pubmed.ncbi.nlm.nih.gov/rss/journals/7900445/?limit=15&name=Hear%20Res&utm_campaign=journals"
    }
    
    data = process_rss_sources(rss_sources)
    json_data = json.dumps(data, ensure_ascii=False, indent=4)

    # GitHub integration
    github_token = os.environ.get("GITHUB_TOKEN")
    github_repo = "your_username/your_repo_name"
    file_path = "rss_data.json"
    commit_message = "Update RSS data"

    update_github_file(github_token, github_repo, file_path, json_data, commit_message)
    print("RSS data has been processed and pushed to GitHub")
