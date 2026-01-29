#!/usr/bin/env python3
"""
Web application for building groundtruth data for PR link ranking.
"""
import csv
import json
import os
import ast
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from urllib.parse import unquote
import io

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# In-memory storage for the current session
current_data = {
    'prs': {},  # pr_id -> {pr_title, pr_url, links: [{link_url, link_text, rank}]}
    'rankings': {}  # pr_id -> {link_url -> rank}
}


def load_csv_data(filepath):
    """Load PR and link data from CSV file.
    
    Args:
        filepath: Path to CSV file with columns: uid, pr_link, repo, pr_title, media_type, isGithub, links, link_count
                  links column can be in JSON, Python literal, or comma-separated format
    
    Returns:
        Dictionary mapping pr_link to PR data with links
        
    Raises:
        KeyError: If required columns are missing
        UnicodeDecodeError: If file encoding is not UTF-8
    """
    prs = {}
    required_columns = {'uid', 'pr_link', 'repo', 'pr_title', 'media_type', 'isGithub', 'links', 'link_count'}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Validate required columns exist
        if not required_columns.issubset(set(reader.fieldnames or [])):
            missing = required_columns - set(reader.fieldnames or [])
            raise KeyError(f"Missing required columns: {', '.join(missing)}")
        
        for row in reader:
            pr_link = row['pr_link']
            
            if pr_link not in prs:
                # Parse links - handle multiple formats
                links_str = row['links'].strip()
                links_list = []
                
                if links_str:
                    try:
                        # Try to parse as JSON first
                        import json as json_module
                        links_data = json_module.loads(links_str)
                        if isinstance(links_data, list):
                            links_list = links_data
                        else:
                            links_list = [links_data] if isinstance(links_data, dict) else []
                    except:
                        try:
                            # Try to parse as Python literal (e.g., ['url1', 'url2'])
                            links_data = ast.literal_eval(links_str)
                            if isinstance(links_data, list):
                                links_list = links_data
                            else:
                                links_list = [links_data] if links_data else []
                        except:
                            # Fall back to comma-separated
                            links_list = [link.strip() for link in links_str.split(',') if link.strip()]
                
                prs[pr_link] = {
                    'uid': row['uid'],  # Use UID from CSV
                    'pr_link': pr_link,
                    'pr_id': pr_link,  # Keep for backward compatibility with frontend
                    'repo': row['repo'],
                    'pr_title': row['pr_title'],
                    'media_type': row['media_type'],
                    'isGithub': row['isGithub'],
                    'link_count': row['link_count'],
                    'links': []
                }
                
                # Add parsed links
                for idx, link in enumerate(links_list):
                    if isinstance(link, dict):
                        # If link is already a dict with url and text
                        prs[pr_link]['links'].append({
                            'link_url': link.get('url', link.get('link_url', '')),
                            'link_text': link.get('text', link.get('link_text', '')),
                            'rank': None
                        })
                    else:
                        # If link is just a URL string
                        prs[pr_link]['links'].append({
                            'link_url': str(link),
                            'link_text': f'Link {idx + 1}',
                            'rank': None
                        })
    
    return prs


def load_ranking_csv_data(filepath):
    """Load PR data with pre-populated rankings from ranking CSV file.
    
    Supports two formats:
    1. New format: uid, pr_link, repo, pr_title, media_type, isGithub, link_count, links, ranks
       (links and ranks are comma-separated values)
    2. Old format: uid, pr_link, repo, pr_title, media_type, isGithub, link_count, link_url, link_text, rank
       (one row per link)
    
    Returns:
        Tuple of (prs dict, rankings dict)
        
    Raises:
        KeyError: If required columns are missing
        UnicodeDecodeError: If file encoding is not UTF-8
    """
    prs = {}
    rankings = {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        
        # Determine format based on available columns
        is_new_format = 'links' in fieldnames and 'ranks' in fieldnames
        is_old_format = 'link_url' in fieldnames and 'rank' in fieldnames
        
        if not is_new_format and not is_old_format:
            raise KeyError("CSV must contain either (links, ranks) columns or (link_url, rank) columns")
        
        if 'uid' not in fieldnames or 'pr_link' not in fieldnames:
            raise KeyError("Missing required columns: uid, pr_link")
        
        for row in reader:
            pr_link = row['pr_link']
            
            if pr_link not in prs:
                prs[pr_link] = {
                    'uid': row['uid'],
                    'pr_link': pr_link,
                    'pr_id': pr_link,
                    'repo': row.get('repo', ''),
                    'pr_title': row.get('pr_title', ''),
                    'media_type': row.get('media_type', ''),
                    'isGithub': row.get('isGithub', ''),
                    'link_count': row.get('link_count', ''),
                    'links': []
                }
                rankings[pr_link] = {}
            
            if is_new_format:
                # Parse new format with combined links and ranks
                links_str = row.get('links', '').strip()
                ranks_str = row.get('ranks', '').strip()
                
                if links_str:
                    links_list = [link.strip() for link in links_str.split(',') if link.strip()]
                    ranks_list = [r.strip() for r in ranks_str.split(',') if r.strip() or True]  # Keep empty strings
                    
                    # Split ranks to match links
                    if ranks_str:
                        ranks_list = ranks_str.split(',')
                    else:
                        ranks_list = ['' for _ in links_list]
                    
                    for idx, link_url in enumerate(links_list):
                        rank = None
                        rank_str = ranks_list[idx].strip() if idx < len(ranks_list) else ''
                        
                        if rank_str and rank_str.lower() != 'none':
                            try:
                                rank = int(rank_str)
                            except ValueError:
                                pass
                        
                        prs[pr_link]['links'].append({
                            'link_url': link_url,
                            'link_text': f'Link {idx + 1}',
                            'rank': rank
                        })
                        
                        if rank is not None:
                            rankings[pr_link][link_url] = rank
            else:
                # Parse old format with one row per link
                link_url = row['link_url']
                rank_str = row.get('rank', '').strip()
                
                rank = None
                if rank_str and rank_str.lower() != 'none':
                    try:
                        rank = int(rank_str)
                    except ValueError:
                        pass
                
                prs[pr_link]['links'].append({
                    'link_url': link_url,
                    'link_text': row.get('link_text', f'Link'),
                    'rank': rank
                })
                
                if rank is not None:
                    rankings[pr_link][link_url] = rank
    
    return prs, rankings


@app.route('/')
def index():
    """Render main page."""
    return render_template('index.html')


@app.route('/api/load', methods=['POST'])
def load_data():
    """Load data from uploaded CSV file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
    
    filepath = None
    try:
        # Save file temporarily
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Load data
        current_data['prs'] = load_csv_data(filepath)
        current_data['rankings'] = {}
        
        return jsonify({
            'success': True,
            'pr_count': len(current_data['prs'])
        })
    except Exception as e:
        return jsonify({'error': 'Failed to load CSV file'}), 500
    finally:
        # Always clean up the uploaded file
        if filepath and os.path.exists(filepath):
            os.remove(filepath)


@app.route('/api/load_sample', methods=['POST'])
def load_sample():
    """Load sample data."""
    try:
        sample_path = os.path.join(os.path.dirname(__file__), 'sample_data.csv')
        current_data['prs'] = load_csv_data(sample_path)
        current_data['rankings'] = {}
        
        return jsonify({
            'success': True,
            'pr_count': len(current_data['prs'])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/load_ranking', methods=['POST'])
def load_ranking():
    """Load data from ranking CSV file with pre-populated ranks."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
    
    filepath = None
    try:
        # Save file temporarily
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Load ranking data
        prs_data, rankings_data = load_ranking_csv_data(filepath)
        current_data['prs'] = prs_data
        current_data['rankings'] = rankings_data
        
        return jsonify({
            'success': True,
            'pr_count': len(current_data['prs'])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Always clean up the uploaded file
        if filepath and os.path.exists(filepath):
            os.remove(filepath)


@app.route('/api/prs', methods=['GET'])
def get_prs():
    """Get list of all PRs."""
    prs_list = list(current_data['prs'].values())
    
    # Add ranking status
    for pr in prs_list:
        pr_id = pr['pr_id']
        if pr_id in current_data['rankings']:
            pr['ranked'] = len(current_data['rankings'][pr_id]) == len(pr['links'])
        else:
            pr['ranked'] = False
    
    return jsonify(prs_list)


@app.route('/api/pr/<path:pr_id>', methods=['GET'])
def get_pr(pr_id):
    """Get details of a specific PR including links."""
    pr_id = unquote(pr_id)  # Decode URL-encoded string
    print(f"Debug: Fetching PR {pr_id}, available PRs: {list(current_data['prs'].keys())}")
    
    if pr_id not in current_data['prs']:
        print(f"Debug: PR {pr_id} not found")
        return jsonify({'error': 'PR not found'}), 404
    
    pr = current_data['prs'][pr_id].copy()
    
    # Add current rankings if they exist
    if pr_id in current_data['rankings']:
        for link in pr['links']:
            link_url = link['link_url']
            if link_url in current_data['rankings'][pr_id]:
                link['rank'] = current_data['rankings'][pr_id][link_url]
    
    return jsonify(pr)


@app.route('/api/rank', methods=['POST'])
def save_ranking():
    """Save ranking for a PR's links."""
    data = request.json
    pr_id = data.get('pr_id')
    rankings = data.get('rankings')  # {link_url: rank}
    
    if not pr_id or not rankings:
        return jsonify({'error': 'Missing pr_id or rankings'}), 400
    
    if pr_id not in current_data['prs']:
        return jsonify({'error': 'PR not found'}), 404
    
    # Save rankings
    current_data['rankings'][pr_id] = rankings
    
    return jsonify({'success': True})


@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    """Export rankings as CSV with combined ranks."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['uid', 'pr_link', 'repo', 'pr_title', 'media_type', 'isGithub', 'link_count', 'links', 'ranks'])
    
    # Write data - one row per PR with combined links and ranks
    for pr_id, pr in current_data['prs'].items():
        rankings = current_data['rankings'].get(pr_id, {})
        
        # Collect links and their corresponding ranks
        links_list = []
        ranks_list = []
        
        for link in pr['links']:
            links_list.append(link['link_url'])
            rank = rankings.get(link['link_url'], '')
            ranks_list.append(str(rank) if rank != '' else '')
        
        # Join links and ranks as comma-separated values
        links_str = ','.join(links_list)
        ranks_str = ','.join(ranks_list)
        
        writer.writerow([
            pr.get('uid', ''),
            pr.get('pr_link', pr_id),
            pr.get('repo', ''),
            pr['pr_title'],
            pr.get('media_type', ''),
            pr.get('isGithub', ''),
            pr.get('link_count', len(pr['links'])),
            links_str,
            ranks_str
        ])
    
    # Create response
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='rankings.csv'
    )


@app.route('/api/export/json', methods=['GET'])
def export_json():
    """Export rankings as JSON."""
    result = []
    
    for pr_id, pr in current_data['prs'].items():
        rankings = current_data['rankings'].get(pr_id, {})
        
        pr_data = {
            'uid': pr.get('uid'),
            'pr_link': pr.get('pr_link', pr_id),
            'pr_id': pr_id,
            'repo': pr.get('repo', ''),
            'pr_title': pr['pr_title'],
            'media_type': pr.get('media_type', ''),
            'isGithub': pr.get('isGithub', ''),
            'link_count': pr.get('link_count', len(pr['links'])),
            'links': []
        }
        
        for link in pr['links']:
            pr_data['links'].append({
                'link_url': link['link_url'],
                'link_text': link['link_text'],
                'rank': rankings.get(link['link_url'], None)
            })
        
        result.append(pr_data)
    
    # Create response
    json_str = json.dumps(result, indent=2)
    return send_file(
        io.BytesIO(json_str.encode('utf-8')),
        mimetype='application/json',
        as_attachment=True,
        download_name='rankings.json'
    )


if __name__ == '__main__':
    # Get debug mode from environment, default to False for production safety
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.environ.get('FLASK_PORT', 5000))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
