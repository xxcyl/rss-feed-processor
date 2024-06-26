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
    """從環境變量中獲取OpenAI API密鑰"""
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

def preprocess_content(text):
    """預處理文本內容，移除不必要的部分"""
    text = re.sub(r'^.*?(?=ABSTRACT|OBJECTIVES)', '', text, flags=re.DOTALL)
    text = re.sub(r'\s*PMID:.*$', '', text, flags=re.DOTALL)
    return text.strip()

def translate_title(text, target_language="zh-TW"):
    """使用OpenAI API翻譯文章標題"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"""You are a translator specializing in academic article titles. Translate the following title to {target_language}. Ensure the translation is concise and accurate, maintaining any technical terms. Use Traditional Chinese (Taiwan) and avoid using Simplified Chinese."""},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in translate_title: {e}")
        return text

def generate_tldr(text, target_language="zh-TW"):
    """使用OpenAI API生成文章的TL;DR摘要"""
    try:
        preprocessed_text = preprocess_content(text)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"""You are an expert in summarizing academic research. Create an extremely concise TL;DR (Too Long; Didn't Read) summary in {target_language} of the following academic abstract. Follow these guidelines:

1. Summarize the entire abstract in 3-4 short, clear sentences.
2. Focus only on the most crucial information: the main objective, key method, and primary finding or conclusion.
3. Use simple, clear language while maintaining academic accuracy.
4. Start the summary with the emoji 💡 followed by "TL;DR: ".
5. Do not use separate headings or multiple paragraphs.
6. Ensure the summary is written in Traditional Chinese (Taiwan) and avoid using Simplified Chinese.

Ensure the summary captures the essence of the research while being extremely concise."""},
                {"role": "user", "content": preprocessed_text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in generate_tldr: {e}")
        return text

def fetch_rss(url):
    """獲取並解析RSS feed的內容"""
    feed = feedparser.parse(url)
    entries = []
    for entry in feed.entries:
        content = entry.get('content', [{}])[0].get('value', '')
        if not content:
            content = entry.get('summary', '')
        
        soup = BeautifulSoup(content, 'html.parser')
        text_content = soup.get_text(separator='\n', strip=True)
        
        # 從 guid 中提取 PMID
        pmid = entry['guid'].split(':')[-1] if 'guid' in entry else None
        
        # 使用正確的 'dc:date'，如果不存在則使用當前時間
        published = entry.get('dc:date', datetime.datetime.now().isoformat())
        
        entry_data = {
            'title': entry.title,
            'link': entry.link,
            'published': published,
            'full_content': text_content,
            'pmid': pmid
        }
        
        entry_data['title_translated'] = translate_title(entry_data['title'])
        entry_data['tldr'] = generate_tldr(entry_data['full_content'])
        
        entries.append(entry_data)
    
    return {
        'feed_title': feed.feed.title,
        'feed_link': feed.feed.link,
        'feed_updated': feed.feed.updated if 'updated' in feed.feed else datetime.datetime.now().isoformat(),
        'entries': entries
    }
    
def merge_feed_data(old_data, new_data):
    """合併新舊feed數據，避免重複條目"""
    merged_entries = old_data['entries']
    new_entries = new_data['entries']
    
    existing_pmids = set(entry.get('pmid') for entry in merged_entries if 'pmid' in entry)
    
    for entry in new_entries:
        pmid = entry.get('pmid')
        if pmid and pmid not in existing_pmids:
            merged_entries.append(entry)
            existing_pmids.add(pmid)
    
    merged_entries.sort(key=lambda x: x['published'], reverse=True)
    
    return {
        'feed_title': new_data['feed_title'],
        'feed_link': new_data['feed_link'],
        'feed_updated': new_data['feed_updated'],
        'entries': merged_entries
    }

def process_rss_sources(sources, existing_data):
    """處理所有RSS來源並合併數據"""
    result = existing_data or {}
    for name, url in sources.items():
        new_feed_data = fetch_rss(url)
        if name in result:
            result[name] = merge_feed_data(result[name], new_feed_data)
        else:
            result[name] = new_feed_data
    return result

def update_github_file(token, repo_name, file_path, content, commit_message):
    """更新GitHub倉庫中的文件"""
    g = Github(token)
    repo = g.get_repo(repo_name)
    
    try:
        file = repo.get_contents(file_path)
        repo.update_file(file_path, commit_message, content, file.sha)
    except:
        repo.create_file(file_path, commit_message, content)

def load_existing_data(token, repo_name, file_path):
    """從GitHub倉庫加載現有的JSON數據"""
    g = Github(token)
    repo = g.get_repo(repo_name)
    try:
        file = repo.get_contents(file_path)
        content = file.decoded_content.decode('utf-8')
        return json.loads(content)
    except:
        return None

def load_rss_sources(file_path='rss_sources.json'):
    """從JSON文件加載RSS來源"""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: RSS sources file '{file_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in RSS sources file '{file_path}'.")
        sys.exit(1)

if __name__ == "__main__":
    # 主程序
    rss_sources = load_rss_sources()
    
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
