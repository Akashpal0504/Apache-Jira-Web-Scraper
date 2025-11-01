# Apache Jira Web Scraper

## 📌 Overview
This project scrapes issue data from public Apache Jira projects using the Jira REST API and converts it into JSONL format for LLM training.

## Features
- Fetches issues, comments, and metadata (status, priority, assignee, etc.)
- Handles pagination, retries, and HTTP 429/5xx gracefully
- Resumes from last checkpoint if interrupted
- Transforms raw data into JSONL format
- Includes error handling, logging, and rate limiting
- Generates simple derived tasks: summarization, classification, and QnA
- Logs progress and maintains recoverability

## Quick Start
1. Install Python 3.10+
2. Clone this repository:
   ```bash
   git clone <https://github.com/Akashpal0504/Apache-Jira-Scraper.git>
   cd apache-jira-scraper
3. Run scraper.py file.

## File includes:
   - scraper.py
   - requirements.txt
   - README.md
   - data/ contains:
         files (`checkpoints.json`, `hadoop_issues.jsonl`, `spark_issues.jsonl`, `kafka_issues.jsonl`)

## url = https://issues.apache.org/jira/rest/api/2/search?jql=project=HADOOP&startAt=0&maxResults=50

## Folder Structure
apache-jira-scraper/
│
├── scraper.py
├── transformer.py
├── utils.py
├── requirements.txt
├── data/
│   ├── checkpoints.json
│   ├── hadoop_issues.jsonl
│   ├── spark_issues.jsonl
│   └── kafka_issues.jsonl
└── README.md

