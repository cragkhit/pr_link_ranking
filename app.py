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
        filepath: Path to CSV file with columns: uid, pr_link, repo, pr_title, link, label_word, link_count
                  Optional: media_type, isGithub
                  link and label_word columns can be in JSON, Python literal, or comma-separated format
    
    Returns:
        Dictionary mapping pr_link to PR data with links
        
    Raises:
        KeyError: If required columns are missing
        UnicodeDecodeError: If file encoding is not UTF-8
    """
    prs = {}
    required_columns = {'uid', 'pr_link', 'repo', 'pr_title'}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Validate required columns exist
        if not required_columns.issubset(set(reader.fieldnames or [])):
            missing = required_columns - set(reader.fieldnames or [])
            raise KeyError(f"Missing required columns: {', '.join(missing)}")
        
        # Check if optional columns exist
        has_label_word = 'label_word' in (reader.fieldnames or [])
        has_link_column = 'link' in (reader.fieldnames or [])
        has_links_column = 'links' in (reader.fieldnames or [])
        
        for row in reader:
            pr_link = row['pr_link']
            
            if pr_link not in prs:
                # Parse links - handle both 'link' and 'links' column names
                links_str = ''
                if has_link_column:
                    links_str = row.get('link', '').strip()
                elif has_links_column:
                    links_str = row.get('links', '').strip()
                else:
                    links_str = ''
                    
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
                
                # Parse label_word if present
                label_words = []
                if has_label_word:
                    label_words_str = row.get('label_word', '').strip()
                    if label_words_str:
                        try:
                            # Try to parse as Python literal (e.g., ['#32347', 'MIGRATION.MD'])
                            label_words = ast.literal_eval(label_words_str)
                            if not isinstance(label_words, list):
                                label_words = [label_words]
                        except:
                            # Fall back to comma-separated
                            label_words = [lw.strip() for lw in label_words_str.split(',') if lw.strip()]
                
                prs[pr_link] = {
                    'uid': row.get('uid', ''),
                    'pr_link': pr_link,
                    'pr_id': pr_link,  # Keep for backward compatibility with frontend
                    'repo': row['repo'],
                    'pr_title': row['pr_title'],
                    'media_type': row.get('media_type', ''),
                    'isGithub': row.get('isGithub', ''),
                    'link_count': row.get('link_count', len(links_list)),
                    'links': []
                }
                
                # Add parsed links with matching labels
                for idx, link in enumerate(links_list):
                    # Get corresponding label for this link index
                    label_text = label_words[idx] if idx < len(label_words) else ''
                    
                    if isinstance(link, dict):
                        # If link is already a dict with url and text
                        prs[pr_link]['links'].append({
                            'link_url': link.get('url', link.get('link_url', '')),
                            'link_text': label_text or link.get('text', link.get('link_text', '')),
                            'label_word': label_text,
                            'rank': None
                        })
                    else:
                        # If link is just a URL string
                        prs[pr_link]['links'].append({
                            'link_url': str(link),
                            'link_text': label_text or f'Link {idx + 1}',
                            'label_word': label_text,
                            'rank': None
                        })
    
    return prs


def load_ranking_csv_data(filepath):
    """Load PR data with pre-populated rankings from ranking CSV file.
    
    Supports multiple formats:
    1. New format with labels: uid, pr_link, repo, pr_title, media_type, isGithub, link_count, link, label_word, link_index, rank
       (one row per link with label matching)
    2. Combined format: uid, pr_link, repo, pr_title, media_type, isGithub, link_count, links, label_word, ranks
       (links, label_word, ranks are comma-separated or list formats)
    3. Old format: uid, pr_link, repo, pr_title, media_type, isGithub, link_count, link_url, link_text, rank
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
        has_labels = 'label_word' in fieldnames
        has_link_index = 'link_index' in fieldnames
        is_new_format_labels = has_labels and has_link_index and 'link' in fieldnames
        is_new_format = 'links' in fieldnames and 'ranks' in fieldnames
        is_old_format = 'link_url' in fieldnames and 'rank' in fieldnames
        
        if not (is_new_format_labels or is_new_format or is_old_format):
            raise KeyError("CSV must contain either (link, label_word, link_index), (links, ranks), or (link_url, rank) columns")
        
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
            
            if is_new_format_labels:
                # Parse new format with link, label_word, and rank
                link_url = row.get('link', '').strip()
                label_word = row.get('label_word', '').strip()
                rank_str = row.get('rank', '').strip()
                
                rank = None
                if rank_str and rank_str.lower() != 'none':
                    try:
                        rank = int(rank_str)
                    except ValueError:
                        pass
                
                prs[pr_link]['links'].append({
                    'link_url': link_url,
                    'link_text': label_word or f'Link',
                    'label_word': label_word,
                    'rank': rank
                })
                
                if rank is not None:
                    rankings[pr_link][link_url] = rank
                    # also store by index if provided
                    try:
                        link_index = int(row.get('link_index', '').strip())
                        rankings[pr_link][str(link_index)] = rank
                    except Exception:
                        pass
            elif is_new_format:
                # Parse new format with combined links and ranks
                links_str = row.get('links', '').strip()
                label_words_str = row.get('label_word', '').strip()
                ranks_str = row.get('ranks', '').strip()
                
                if links_str:
                    # Parse links
                    links_list = []
                    try:
                        links_data = ast.literal_eval(links_str)
                        links_list = links_data if isinstance(links_data, list) else [links_data]
                    except:
                        links_list = [link.strip() for link in links_str.split(',') if link.strip()]
                    
                    # Parse label_words
                    label_words = []
                    if label_words_str:
                        try:
                            label_data = ast.literal_eval(label_words_str)
                            label_words = label_data if isinstance(label_data, list) else [label_data]
                        except:
                            label_words = [lw.strip() for lw in label_words_str.split(',') if lw.strip()]
                    
                    # Parse ranks
                    ranks_list = []
                    if ranks_str:
                        ranks_list = ranks_str.split(',')
                    else:
                        ranks_list = ['' for _ in links_list]
                    
                    # Split ranks to match links and labels
                    for idx, link_url in enumerate(links_list):
                        label_word = label_words[idx] if idx < len(label_words) else ''
                        rank = None
                        rank_str = ranks_list[idx].strip() if idx < len(ranks_list) else ''
                        
                        if rank_str and rank_str.lower() != 'none':
                            try:
                                rank = int(rank_str)
                            except ValueError:
                                pass
                        
                        prs[pr_link]['links'].append({
                            'link_url': link_url,
                            'link_text': label_word or f'Link {idx + 1}',
                            'label_word': label_word,
                            'rank': rank
                        })
                        
                        if rank is not None:
                            rankings[pr_link][link_url] = rank
                            # also set index-keyed mapping
                            rankings[pr_link][str(idx)] = rank
            else:
                # Parse old format with one row per link
                link_url = row['link_url']
                rank_str = row.get('rank', '').strip()
                label_text = row.get('link_text', f'Link')
                
                rank = None
                if rank_str and rank_str.lower() != 'none':
                    try:
                        rank = int(rank_str)
                    except ValueError:
                        pass
                
                prs[pr_link]['links'].append({
                    'link_url': link_url,
                    'link_text': label_text,
                    'label_word': label_text,
                    'rank': rank
                })
                
                if rank is not None:
                    rankings[pr_link][link_url] = rank
                    # no index information in old format
    
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
        print(f"Error loading CSV: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to load CSV file: {str(e)}'}), 500
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
        # Normalize rankings into structure with by_index and by_url
        normalized = {}
        for pr_link, rk in rankings_data.items():
            normalized[pr_link] = {
                'by_index': {},
                'by_url': {}
            }
            for key, val in rk.items():
                # If the key is an integer (index), put into by_index, otherwise by_url
                try:
                    ik = int(key)
                    normalized[pr_link]['by_index'][ik] = int(val)
                except Exception:
                    normalized[pr_link]['by_url'][str(key)] = val

        current_data['rankings'] = normalized
        
        return jsonify({
            'success': True,
            'pr_count': len(current_data['prs'])
        })
    except Exception as e:
        print(f"Error loading ranking CSV: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to load ranking CSV: {str(e)}'}), 500
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
        ranked = False
        if pr_id in current_data['rankings']:
            rk = current_data['rankings'][pr_id]
            by_index = rk.get('by_index', {})
            by_url = rk.get('by_url', {})

            # Count how many links have a recorded rank either by index or by URL
            count = 0
            for idx, link in enumerate(pr['links']):
                if (isinstance(by_index, dict) and (idx in by_index or str(idx) in by_index)) or (link.get('link_url') in by_url):
                    count += 1

            ranked = (count == len(pr['links']))
        pr['ranked'] = ranked
    
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

    # Add current rankings if they exist (support both index- and URL-keyed rankings)
    if pr_id in current_data['rankings']:
        rk = current_data['rankings'][pr_id]
        by_index = rk.get('by_index', {})
        by_url = rk.get('by_url', {})

        for idx, link in enumerate(pr['links']):
            link_url = link.get('link_url')
            
            # Preference: URL mapping first (from user drag/drop), then index mapping (from CSV load)
            if link_url in by_url:
                link['rank'] = by_url[link_url]
                continue
                
            if isinstance(by_index, dict):
                if idx in by_index:
                    link['rank'] = by_index[idx]
                    continue
                if str(idx) in by_index:
                    try:
                        link['rank'] = int(by_index[str(idx)])
                        continue
                    except:
                        pass
    
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
    
    # Normalize incoming rankings: keys may be link indices (string/int) or URLs
    by_index = {}
    by_url = {}
    for k, v in rankings.items():
        # try integer index
        try:
            ik = int(k)
            by_index[ik] = int(v)
            continue
        except Exception:
            pass

        # otherwise treat as URL
        by_url[str(k)] = v

    # Merge with existing URL-keyed rankings so we don't lose previously-loaded ranks
    existing = current_data['rankings'].get(pr_id, {'by_index': {}, 'by_url': {}})
    existing_by_url = existing.get('by_url', {}) if isinstance(existing, dict) else {}

    # final by_url: start from existing, then override with any incoming URL mappings
    final_by_url = dict(existing_by_url)
    for k, v in by_url.items():
        final_by_url[str(k)] = v

    current_data['rankings'][pr_id] = {
        'by_index': by_index,
        'by_url': final_by_url
    }
    return jsonify({'success': True})


@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    """Export rankings as CSV with combined ranks and labels."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header - uid as first column
    writer.writerow(['uid', 'pr_link', 'repo', 'pr_title', 'media_type', 'isGithub', 'link_count', 'link', 'label_word', 'link_index', 'rank'])
    
    # Write data - one row per link with label_word matching
    for pr_id, pr in current_data['prs'].items():
        rk = current_data['rankings'].get(pr_id, {'by_index': {}, 'by_url': {}})
        by_index = rk.get('by_index', {})
        by_url = rk.get('by_url', {})

        # Write one row per link with its matching label
        for link_idx, link in enumerate(pr['links']):
            # Prefer URL-keyed rank (from user drag/drop save), fallback to index-keyed rank (from CSV load)
            rank = ''
            link_url = link.get('link_url', '')
            if link_url in by_url:
                rank = by_url.get(link_url, '')
            elif isinstance(by_index, dict) and (link_idx in by_index or str(link_idx) in by_index):
                rank = by_index.get(link_idx, by_index.get(str(link_idx), ''))

            label_word = link.get('label_word', '')
            
            writer.writerow([
                pr.get('uid', ''),
                pr.get('pr_link', pr_id),
                pr.get('repo', ''),
                pr['pr_title'],
                pr.get('media_type', ''),
                pr.get('isGithub', ''),
                pr.get('link_count', len(pr['links'])),
                link['link_url'],
                label_word,
                link_idx,
                str(rank) if rank != '' else ''
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
    """Export rankings as JSON with label matching."""
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
        
        rk = current_data['rankings'].get(pr_id, {'by_index': {}, 'by_url': {}})
        by_index = rk.get('by_index', {})
        by_url = rk.get('by_url', {})

        for idx, link in enumerate(pr['links']):
            # Determine rank preferring URL mapping (from user drag/drop save), fallback to index mapping
            rank_val = None
            link_url = link.get('link_url')
            if link_url in by_url:
                rank_val = by_url.get(link_url)
            elif isinstance(by_index, dict) and (idx in by_index or str(idx) in by_index):
                rank_val = by_index.get(idx, by_index.get(str(idx), None))

            pr_data['links'].append({
                'link_url': link['link_url'],
                'link_text': link.get('link_text'),
                'label_word': link.get('label_word', ''),
                'link_index': idx,
                'rank': rank_val
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
