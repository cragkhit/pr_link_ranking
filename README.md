# PR Link Ranking - Groundtruth Data Builder

A web application for building groundtruth data for pull request link ranking algorithms.

## Features

- 📁 Load PR and link data from CSV files
- 📊 View and review pull requests with their associated links
- 🔢 Rank links by relevance for each PR
- 💾 Export rankings as CSV or JSON format
- 🎨 Clean, intuitive user interface
- 📋 Sample data included for testing

## Installation

1. Install Python 3.7 or higher

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

3. Load data:
   - **Option 1**: Upload your own CSV file with the required format
   - **Option 2**: Click "Load Sample Data" to try the application with example data

4. Review and rank links:
   - Click on each pull request to view its details
   - Assign a rank to each link (1 = highest relevance, higher numbers = lower relevance)
   - Click "Save Rankings" to save your rankings

5. Export results:
   - Click "Export as CSV" or "Export as JSON" to download your rankings

## CSV Format

The input CSV file should have the following columns:

```
pr_id,pr_title,pr_url,link_url,link_text
```

Example:
```csv
pr_id,pr_title,pr_url,link_url,link_text
1,Fix bug in authentication,https://github.com/example/repo/pull/1,https://docs.python.org/3/library/auth.html,Python Auth Documentation
1,Fix bug in authentication,https://github.com/example/repo/pull/1,https://stackoverflow.com/questions/12345/auth-issue,StackOverflow Discussion
2,Add CSV export feature,https://github.com/example/repo/pull/2,https://docs.python.org/3/library/csv.html,CSV Module Documentation
```

Notes:
- Multiple rows can have the same `pr_id` to represent multiple links in the same PR
- Each link should be on a separate row

## Export Format

### CSV Export
The exported CSV includes all PRs and links with their assigned ranks:
```csv
pr_id,pr_title,pr_url,link_url,link_text,rank
1,Fix bug in authentication,https://github.com/example/repo/pull/1,https://docs.python.org/3/library/auth.html,Python Auth Documentation,1
```

### JSON Export
The exported JSON provides a structured format:
```json
[
  {
    "pr_id": "1",
    "pr_title": "Fix bug in authentication",
    "pr_url": "https://github.com/example/repo/pull/1",
    "links": [
      {
        "link_url": "https://docs.python.org/3/library/auth.html",
        "link_text": "Python Auth Documentation",
        "rank": 1
      }
    ]
  }
]
```

## Sample Data

The application includes `sample_data.csv` with example PRs and links for testing purposes.

## Development

The application is built with:
- **Backend**: Flask (Python web framework)
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Storage**: In-memory (session-based)

## Notes

- Rankings are stored in-memory and will be lost when the application restarts
- Maximum file upload size: 16MB
- The application runs on `http://0.0.0.0:5000` by default

## License

MIT