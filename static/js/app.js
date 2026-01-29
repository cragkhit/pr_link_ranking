// Global state
let currentPRs = [];
let currentPR = null;

// DOM Elements
const loadSection = document.getElementById('load-section');
const prListSection = document.getElementById('pr-list-section');
const prDetailSection = document.getElementById('pr-detail-section');
const linksViewSection = document.getElementById('links-view-section');
const exportSection = document.getElementById('export-section');

const fileInput = document.getElementById('file-input');
const loadButton = document.getElementById('load-button');
const rankingFileInput = document.getElementById('ranking-file-input');
const loadRankingButton = document.getElementById('load-ranking-button');
const loadStatus = document.getElementById('load-status');

const prStats = document.getElementById('pr-stats');
const prList = document.getElementById('pr-list');
const prDetail = document.getElementById('pr-detail');
const linksView = document.getElementById('links-view');
const backButton = document.getElementById('back-button');
const backToListButton = document.getElementById('back-to-list-button');

const exportCsvButton = document.getElementById('export-csv-button');
const exportJsonButton = document.getElementById('export-json-button');

// Event Listeners
loadButton.addEventListener('click', handleLoadFile);
loadRankingButton.addEventListener('click', handleLoadRankingFile);
backButton.addEventListener('click', showPRList);
backToListButton.addEventListener('click', showPRList);
exportCsvButton.addEventListener('click', () => handleExport('csv'));
exportJsonButton.addEventListener('click', () => handleExport('json'));

// Load File Handler
async function handleLoadFile() {
    const file = fileInput.files[0];
    if (!file) {
        showStatus('Please select a file', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        loadButton.disabled = true;
        showStatus('Loading...', 'info');

        const response = await fetch('/api/load', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.error) {
            showStatus(`Error: ${data.error}`, 'error');
        } else {
            showStatus(`Successfully loaded ${data.pr_count} pull requests`, 'success');
            await loadPRs();
            showPRList();
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    } finally {
        loadButton.disabled = false;
    }
}

// Load Ranking File Handler
async function handleLoadRankingFile() {
    const file = rankingFileInput.files[0];
    if (!file) {
        showStatus('Please select a ranking CSV file', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        loadRankingButton.disabled = true;
        showStatus('Loading ranking data...', 'info');

        const response = await fetch('/api/load_ranking', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.error) {
            showStatus(`Error: ${data.error}`, 'error');
        } else {
            showStatus(`Successfully loaded ${data.pr_count} pull requests with rankings`, 'success');
            await loadPRs();
            showPRList();
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    } finally {
        loadRankingButton.disabled = false;
    }
}

// Load PRs from API
async function loadPRs() {
    try {
        const response = await fetch('/api/prs');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        currentPRs = await response.json();
        console.log('Loaded PRs:', currentPRs);
    } catch (error) {
        console.error('Error loading PRs:', error);
    }
}

// Show Status Message
function showStatus(message, type) {
    loadStatus.textContent = message;
    loadStatus.className = `status-message ${type}`;
    loadStatus.style.display = 'block';
}

// Show PR List View
function showPRList() {
    prListSection.classList.remove('hidden');
    prDetailSection.classList.add('hidden');
    linksViewSection.classList.add('hidden');
    exportSection.classList.remove('hidden');

    renderStats();
    renderPRList();
}

// Render Stats
function renderStats() {
    const rankedCount = currentPRs.filter(pr => pr.ranked).length;
    const totalCount = currentPRs.length;

    prStats.innerHTML = `
        <strong>Progress:</strong> ${rankedCount} of ${totalCount} PRs ranked
    `;
}

// Render PR List
function renderPRList() {
    prList.innerHTML = '';

    const table = document.createElement('table');
    table.className = 'pr-table';
    
    // Create header
    const thead = document.createElement('thead');
    thead.innerHTML = `
        <tr>
            <th>UID</th>
            <th>PR Title</th>
            <th>Links</th>
            <th>Status</th>
            <th>Action</th>
        </tr>
    `;
    table.appendChild(thead);
    
    // Create body
    const tbody = document.createElement('tbody');
    currentPRs.forEach((pr, index) => {
        console.log(`PR ${index}:`, pr);
        const tr = document.createElement('tr');
        tr.className = pr.ranked ? 'ranked' : 'unranked';
        
        const uidValue = pr.uid !== undefined ? pr.uid : (index + 1);
        tr.innerHTML = `
            <td class="uid-cell">${uidValue}</td>
            <td class="title-cell">${escapeHtml(pr.pr_title)}</td>
            <td class="links-cell">${pr.links.length}</td>
            <td class="status-cell">
                <span class="pr-status ${pr.ranked ? 'ranked' : 'unranked'}">
                    ${pr.ranked ? '✓ Ranked' : 'Not Ranked'}
                </span>
            </td>
            <td class="action-cell">
                <button class="btn btn-small action-btn" data-pr-id="${pr.pr_id}">
                    ${pr.ranked ? 'View' : 'Rank'}
                </button>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    
    prList.appendChild(table);
    
    // Add event listeners to action buttons
    document.querySelectorAll('.action-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const prId = this.dataset.prId;
            console.log('Clicked PR ID:', prId);
            showLinksView(prId);
        });
    });
}

// Show PR Detail View
async function showPRDetail(prId) {
    try {
        console.log('Fetching PR for ranking:', prId);
        const encodedPrId = encodeURIComponent(prId);
        const response = await fetch(`/api/pr/${encodedPrId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        currentPR = await response.json();

        prListSection.classList.add('hidden');
        prDetailSection.classList.remove('hidden');
        linksViewSection.classList.add('hidden');
        exportSection.classList.add('hidden');

        renderPRDetail();
    } catch (error) {
        console.error('Error loading PR detail:', error);
        alert('Error loading PR details');
    }
}

// Render PR Detail
function renderPRDetail() {
    prDetail.innerHTML = `
        <div class="pr-detail-header">
            <div class="pr-id">PR #${currentPR.uid || currentPR.pr_id}</div>
            <h2 class="pr-detail-title">${escapeHtml(currentPR.pr_title)}</h2>
            <div class="pr-detail-meta">
                <div><strong>Repository:</strong> ${escapeHtml(currentPR.repo)}</div>
                <div><strong>Link:</strong> <a href="${escapeHtml(currentPR.pr_link)}" target="_blank" class="pr-detail-url">${escapeHtml(currentPR.pr_link)}</a></div>
                <div><strong>Media Type:</strong> ${escapeHtml(currentPR.media_type)}</div>
                <div><strong>GitHub:</strong> ${currentPR.isGithub}</div>
                <div><strong>Link Count:</strong> ${currentPR.link_count}</div>
            </div>
        </div>

        <div class="links-container">
            <h3>Rank the Links (1 = highest relevance)</h3>
            <div id="links-list"></div>
            <button id="save-ranking-btn" class="btn btn-primary save-ranking-button">
                Save Rankings
            </button>
            <div id="ranking-status"></div>
        </div>
    `;

    const linksList = document.getElementById('links-list');
    currentPR.links.forEach((link, index) => {
        const linkItem = document.createElement('div');
        linkItem.className = 'link-item';

        linkItem.innerHTML = `
            <div class="link-header">
                <div class="rank-input-group">
                    <label>Rank:</label>
                    <input 
                        type="number" 
                        class="rank-input" 
                        min="1" 
                        value="${link.rank || ''}"
                        data-link-url="${escapeHtml(link.link_url)}"
                        placeholder="Enter rank"
                    >
                </div>
                <div class="link-text">${escapeHtml(link.link_text)}</div>
            </div>
            <a href="${escapeHtml(link.link_url)}" target="_blank" class="link-url-display">
                ${escapeHtml(link.link_url)}
            </a>
        `;

        linksList.appendChild(linkItem);
    });

    document.getElementById('save-ranking-btn').addEventListener('click', saveRanking);
}

// Show Links View Page
async function showLinksView(prId) {
    try {
        console.log('Fetching PR details for:', prId);
        const encodedPrId = encodeURIComponent(prId);
        const response = await fetch(`/api/pr/${encodedPrId}`);
        
        if (!response.ok) {
            const errorData = await response.text();
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorData}`);
        }
        
        currentPR = await response.json();
        console.log('Loaded PR:', currentPR);

        prListSection.classList.add('hidden');
        prDetailSection.classList.add('hidden');
        linksViewSection.classList.remove('hidden');
        exportSection.classList.add('hidden');

        renderLinksView();
    } catch (error) {
        console.error('Error loading PR detail:', error);
        alert(`Error loading PR details: ${error.message}`);
    }
}

// Render Links View
function renderLinksView() {
    linksView.innerHTML = `
        <div class="links-view-header">
            <div class="pr-id">PR #${currentPR.uid || currentPR.pr_id}</div>
            <h2 class="pr-title">${escapeHtml(currentPR.pr_title)}</h2>
            <div class="pr-info">
                <div><strong>Repository:</strong> ${escapeHtml(currentPR.repo)}</div>
                <div><strong>Links to Review:</strong> ${currentPR.links.length}</div>
            </div>
            <div class="drag-hint">💡 Tip: You can drag and drop links to reorder them</div>
        </div>

        <div class="links-view-container">
            <h3>Original PR Link</h3>
            <div class="pr-link-display">
                <a href="${escapeHtml(currentPR.pr_link)}" target="_blank" class="pr-link-url">
                    ${escapeHtml(currentPR.pr_link)}
                </a>
            </div>

            <h3 style="margin-top: 30px;">Links Associated with this PR</h3>
            <p class="ranking-instruction">Drag and drop to rank links (top = highest relevance)</p>
            <div id="links-display-list"></div>
            <div class="links-view-actions">
                <button id="save-links-ranking-btn" class="btn btn-primary">
                    Save Rankings
                </button>
            </div>
            <div id="links-ranking-status"></div>
            <div id="links-report" class="links-report"></div>
        </div>
    `;

    const linksDisplayList = document.getElementById('links-display-list');
    currentPR.links.forEach((link, index) => {
        const linkItem = document.createElement('div');
        linkItem.className = 'link-display-item';
        linkItem.draggable = true;
        linkItem.dataset.linkIndex = index;

        linkItem.innerHTML = `
            <div class="link-display-number">Link ${index + 1}</div>
            <div class="link-display-header">
                <span class="drag-handle">⋮⋮</span>
                <span class="link-display-text">${escapeHtml(link.link_text)}</span>
            </div>
            <a href="${escapeHtml(link.link_url)}" target="_blank" class="link-display-url">
                ${escapeHtml(link.link_url)}
            </a>
            ${link.rank ? `<div class="current-rank">Current Rank: <strong>${link.rank}</strong></div>` : ''}
        `;

        // Drag event listeners
        linkItem.addEventListener('dragstart', handleLinkDragStart);
        linkItem.addEventListener('dragover', handleLinkDragOver);
        linkItem.addEventListener('drop', handleLinkDrop);
        linkItem.addEventListener('dragend', handleLinkDragEnd);
        linkItem.addEventListener('dragenter', handleLinkDragEnter);
        linkItem.addEventListener('dragleave', handleLinkDragLeave);

        linksDisplayList.appendChild(linkItem);
    });

    document.getElementById('save-links-ranking-btn').addEventListener('click', saveLinkRankings);
}

// Save Link Rankings based on drag and drop order
async function saveLinkRankings() {
    const rankings = {};
    
    // Assign ranks based on current order (1 = top/highest relevance)
    currentPR.links.forEach((link, index) => {
        rankings[link.link_url] = index + 1;
    });
    
    try {
        const response = await fetch('/api/rank', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                pr_id: currentPR.pr_id,
                rankings: rankings
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            const statusDiv = document.getElementById('links-ranking-status');
            statusDiv.className = 'ranking-saved';
            statusDiv.textContent = '✓ Rankings saved successfully!';

            // Update the PR list data
            await loadPRs();

            // Fetch updated PR to get ranks and render report below
            try {
                const encodedPrId = encodeURIComponent(currentPR.pr_id);
                const prResp = await fetch(`/api/pr/${encodedPrId}`);
                if (prResp.ok) {
                    const updatedPR = await prResp.json();
                    // update currentPR and render report
                    currentPR = updatedPR;
                    renderReport(updatedPR);
                } else {
                    console.warn('Could not fetch updated PR for report');
                }
            } catch (err) {
                console.error('Error fetching updated PR for report:', err);
            }
        } else {
            alert('Error saving rankings');
        }
    } catch (error) {
        console.error('Error saving ranking:', error);
        alert('Error saving rankings');
    }
}

// Drag and drop handlers
let draggedElement = null;
let draggedIndex = null;

function handleLinkDragStart(e) {
    draggedElement = this;
    draggedIndex = parseInt(this.dataset.linkIndex);
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleLinkDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleLinkDragEnter(e) {
    if (this !== draggedElement) {
        this.classList.add('drag-over');
    }
}

function handleLinkDragLeave(e) {
    this.classList.remove('drag-over');
}

function handleLinkDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    
    if (this !== draggedElement) {
        const droppedIndex = parseInt(this.dataset.linkIndex);
        
        // Reorder the links array
        const draggedLink = currentPR.links[draggedIndex];
        currentPR.links.splice(draggedIndex, 1);
        currentPR.links.splice(droppedIndex, 0, draggedLink);
        
        // Re-render with new order
        renderLinksView();
    }
    
    return false;
}

function handleLinkDragEnd(e) {
    document.querySelectorAll('.link-display-item').forEach(item => {
        item.classList.remove('dragging', 'drag-over');
    });
}

// Save Ranking
async function saveRanking() {
    const rankInputs = document.querySelectorAll('.rank-input');
    const rankings = {};

    let hasError = false;
    rankInputs.forEach(input => {
        const linkUrl = input.dataset.linkUrl;
        const rank = parseInt(input.value);

        if (!rank || rank < 1) {
            hasError = true;
        } else {
            rankings[linkUrl] = rank;
        }
    });

    if (hasError) {
        alert('Please enter a valid rank (positive number) for all links');
        return;
    }

    try {
        const response = await fetch('/api/rank', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                pr_id: currentPR.pr_id,
                rankings: rankings
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            const statusDiv = document.getElementById('ranking-status');
            statusDiv.className = 'ranking-saved';
            statusDiv.textContent = '✓ Rankings saved successfully!';

            // Update the PR in the list
            await loadPRs();

            setTimeout(() => {
                showPRList();
            }, 1500);
        } else {
            alert('Error saving rankings');
        }
    } catch (error) {
        console.error('Error saving ranking:', error);
        alert('Error saving rankings');
    }
}

// Render report table for a PR below the links view
function renderReport(pr) {
    const container = document.getElementById('links-report');
    if (!container) return;

    // Build table
    const table = document.createElement('table');
    table.className = 'pr-report-table';

    const thead = document.createElement('thead');
    thead.innerHTML = `
        <tr>
            <th>UID</th>
            <th>PR Title</th>
            <th>Link</th>
            <th>Rank</th>
        </tr>
    `;
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    // Create a sorted copy of links by numeric rank (ascending). Unranked links go to the end.
    const sortedLinks = (pr.links || []).slice().sort((a, b) => {
        const ra = a.rank === undefined || a.rank === null || a.rank === '' ? Infinity : Number(a.rank);
        const rb = b.rank === undefined || b.rank === null || b.rank === '' ? Infinity : Number(b.rank);
        return ra - rb;
    });

    sortedLinks.forEach(link => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="uid-cell">${pr.uid || ''}</td>
            <td class="title-cell">${escapeHtml(pr.pr_title)}</td>
            <td class="link-cell"><a href="${escapeHtml(link.link_url)}" target="_blank">${escapeHtml(link.link_url)}</a></td>
            <td class="rank-cell">${link.rank !== undefined && link.rank !== null && link.rank !== '' ? link.rank : ''}</td>
        `;
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    // Clear and append
    container.innerHTML = '';
    container.appendChild(table);

    // Add Back to PR List button below the report
    const backDiv = document.createElement('div');
    backDiv.className = 'report-actions';
    backDiv.innerHTML = `
        <button id="report-back-button" class="btn btn-secondary" style="margin-top:12px;">Back to PR List</button>
    `;
    container.appendChild(backDiv);

    // Wire up back button
    const backBtn = document.getElementById('report-back-button');
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            showPRList();
        });
    }
}

// Export Handler
async function handleExport(format) {
    try {
        const response = await fetch(`/api/export/${format}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const blob = await response.blob();

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `rankings.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Error exporting:', error);
        alert('Error exporting data');
    }
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
