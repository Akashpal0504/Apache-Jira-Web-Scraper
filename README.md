# Apache Jira Web Scraper

## 📌 Overview
🚀 A robust, fault-tolerant Python scraper that extracts public issue data from public Apache Jira projects using the Jira REST API and converts it into JSONL format for LLM training.


## URL

url = https://issues.apache.org/jira/rest/api/2/search?jql=project=HADOOP&startAt=0&maxResults=50


## Table of Contents

🌟 Features
⚙️ Quick Start
📁 Folder Structure
🖼️ Example Output
🧾 Sample JSONL Entry
🧠 Key Highlights
📄 File includes

## Features
✅ Fetches issues, comments, and metadata (status, priority, assignee, etc.)
✅ Handles pagination, retries, and HTTP 429/5xx gracefully
✅ Resumes from last checkpoint if interrupted
✅ Transforms raw data into JSONL format
✅ Includes error handling, logging, and rate limiting
✅ Generates simple derived tasks: summarization, classification, and QnA
✅ Logs progress and maintains recoverability


## Quick Start
1. Install Python 3.10+
2. Clone this repository:
   ```bash
   git clone <https://github.com/Akashpal0504/Apache-Jira-Web-Scraper.git>
   cd apache-jira-scraper
3. python -m venv venv
   venv\Scripts\activate  # (Windows)
   source venv/bin/activate  # (Mac/Linux)
4. Run, this code python scraper.py in terminal.

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
│   │── kafka_issues.jsonl
│   └── (Sample 200 issues per project)
└── README.md


## 🖼️ Example Output

Below is an example run of the scraper showing successful completion and generated files.

### ▶️ Terminal Output
![Terminal_Output](https://github.com/Akashpal0504/Apache-Jira-Web-Scraper/blob/main/terminal_run_output.jpg)

### 📁 Generated Files

Checkpoints_output

![Checkpoints_output](https://github.com/Akashpal0504/Apache-Jira-Web-Scraper/blob/main/checkpoints_output_screenshot.jpg)

Hadoop_issues_output
![Hadoop_issues_output](https://github.com/Akashpal0504/Apache-Jira-Web-Scraper/blob/main/hadoop_output_screenshot.jpg)

Spark_issues_output
![Spark_issues_output](https://github.com/Akashpal0504/Apache-Jira-Web-Scraper/blob/main/spark_output_screenshot.jpg)

Kafka_issues_output
![Kafka_issues_output](https://github.com/Akashpal0504/Apache-Jira-Web-Scraper/blob/main/kafka_output_screenshot.jpg)



## Sample JSONL Entry

Each line in `.jsonl` is a separate issue record — clean, structured, and ready for LLM fine-tuning.

```json
{
  "project": "HADOOP",
  "issue_id": "HADOOP-18234",
  "title": "Add support for new configuration parameter",
  "status": "Resolved",
  "priority": "Major",
  "reporter": "John Doe",
  "assignee": "Alice Smith",
  "labels": ["config", "enhancement"],
  "created": "2024-07-10T12:00:00.000+0000",
  "updated": "2024-07-12T10:00:00.000+0000",
  "description": "This issue introduces a new parameter to improve performance.",
  "comments": [
    "Looks good to me.",
    "Merged into the main branch."
  ],
  "derived": {
    "summary": "This issue introduces a new parameter to improve performance.",
    "classification": "configuration",
    "qna": [
      {
        "q": "What is the issue described?",
        "a": "Add support for new configuration parameter - This issue introduces a new parameter to improve performance."
      },
      {
        "q": "What updates or decisions were made in the discussion?",
        "a": "Merged into the main branch."
      }
    ]
  }
}
```

## Key Highlights

| Area               | Design Choice                                | Benefit                               |
| ------------------ | -------------------------------------------- | ------------------------------------- |
| **Retries**        | `tenacity` exponential backoff               | Graceful recovery from network issues |
| **Checkpointing**  | JSON-based progress save                     | Resumable scraping                    |
| **Efficiency**     | Pagination (`maxResults=50`)                 | Controlled server load                |
| **Data Quality**   | `safe_get` + validation                      | Prevents crashes on malformed data    |
| **Transformation** | Derived fields: summary, classification, qna | LLM-ready corpus                      |


## file Includes
   - scraper.py
   - requirements.txt
   - README.md
   - data/  contains:
         files (`checkpoints.json`, `hadoop_issues.jsonl`, `spark_issues.jsonl`, `kafka_issues.jsonl`)





