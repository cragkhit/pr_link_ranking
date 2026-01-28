#!/usr/bin/env python3
"""
Web application for building groundtruth data for PR link ranking.
"""
import csv
import json
import os
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
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
        filepath: Path to CSV file with columns: pr_id, pr_title, pr_url, link_url, link_text
    
    Returns:
        Dictionary mapping pr_id to PR data with links
        
    Raises:
        KeyError: If required columns are missing
        UnicodeDecodeError: If file encoding is not UTF-8
    """
    prs = {}
    required_columns = {'pr_id', 'pr_title', 'pr_url', 'link_url', 'link_text'}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Validate required columns exist
        if not required_columns.issubset(set(reader.fieldnames or [])):
            missing = required_columns - set(reader.fieldnames or [])
            raise KeyError(f"Missing required columns: {', '.join(missing)}")
        
        for row in reader:
            pr_id = row['pr_id']
            
            if pr_id not in prs:
                prs[pr_id] = {
                    'pr_id': pr_id,
                    'pr_title': row['pr_title'],
                    'pr_url': row['pr_url'],
                    'links': []
                }
            
            # Add link to PR
            prs[pr_id]['links'].append({
                'link_url': row['link_url'],
                'link_text': row['link_text'],
                'rank': None  # Will be set by user
            })
    
    return prs


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


@app.route('/api/pr/<pr_id>', methods=['GET'])
def get_pr(pr_id):
    """Get details of a specific PR including links."""
    if pr_id not in current_data['prs']:
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
    """Export rankings as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['pr_id', 'pr_title', 'pr_url', 'link_url', 'link_text', 'rank'])
    
    # Write data
    for pr_id, pr in current_data['prs'].items():
        rankings = current_data['rankings'].get(pr_id, {})
        
        for link in pr['links']:
            rank = rankings.get(link['link_url'], '')
            writer.writerow([
                pr_id,
                pr['pr_title'],
                pr['pr_url'],
                link['link_url'],
                link['link_text'],
                rank
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
            'pr_id': pr_id,
            'pr_title': pr['pr_title'],
            'pr_url': pr['pr_url'],
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
