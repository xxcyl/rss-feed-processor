# 在 rss_processor.py 中

# ...其他代碼保持不變...

if __name__ == "__main__":
    rss_sources = {
        "Ear Hear": "https://pubmed.ncbi.nlm.nih.gov/rss/journals/8005585/?limit=15&name=Ear%20Hear&utm_campaign=journals",
        "Hear Res": "https://pubmed.ncbi.nlm.nih.gov/rss/journals/7900445/?limit=15&name=Hear%20Res&utm_campaign=journals"
    }
    
    data = process_rss_sources(rss_sources)
    json_data = json.dumps(data, ensure_ascii=False, indent=4)

    # GitHub 集成
    github_token = os.environ.get("PAT")  # 或者使用 "RSS_GITHUB_TOKEN"
    github_repo = "your_username/your_repo_name"
    file_path = "rss_data.json"
    commit_message = "Update RSS data"

    update_github_file(github_token, github_repo, file_path, json_data, commit_message)
    print("RSS data has been processed and pushed to GitHub")
