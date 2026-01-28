// Global state
let currentPRs = [];
let currentPR = null;

// DOM Elements
const loadSection = document.getElementById('load-section');
const prListSection = document.getElementById('pr-list-section');
const prDetailSection = document.getElementById('pr-detail-section');
const exportSection = document.getElementById('export-section');

const fileInput = document.getElementById('file-input');
const loadButton = document.getElementById('load-button');
const loadSampleButton = document.getElementById('load-sample-button');
const loadStatus = document.getElementById('load-status');

const prStats = document.getElementById('pr-stats');
const prList = document.getElementById('pr-list');
const prDetail = document.getElementById('pr-detail');
const backButton = document.getElementById('back-button');

const exportCsvButton = document.getElementById('export-csv-button');
const exportJsonButton = document.getElementById('export-json-button');

// Event Listeners
loadButton.addEventListener('click', handleLoadFile);
loadSampleButton.addEventListener('click', handleLoadSample);
backButton.addEventListener('click', showPRList);
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

// Load Sample Data Handler
async function handleLoadSample() {
    try {
        loadSampleButton.disabled = true;
        showStatus('Loading sample data...', 'info');

        const response = await fetch('/api/load_sample', {
            method: 'POST'
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
        loadSampleButton.disabled = false;
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

    currentPRs.forEach(pr => {
        const prItem = document.createElement('div');
        prItem.className = 'pr-item';
        prItem.onclick = () => showPRDetail(pr.pr_id);

        prItem.innerHTML = `
            <div class="pr-item-header">
                <span class="pr-id">PR #${pr.pr_id}</span>
                <span class="pr-status ${pr.ranked ? 'ranked' : 'unranked'}">
                    ${pr.ranked ? '✓ Ranked' : 'Not Ranked'}
                </span>
            </div>
            <div class="pr-title">${escapeHtml(pr.pr_title)}</div>
            <div class="pr-url">${escapeHtml(pr.pr_url)}</div>
            <div class="link-count">${pr.links.length} link(s)</div>
        `;

        prList.appendChild(prItem);
    });
}

// Show PR Detail View
async function showPRDetail(prId) {
    try {
        const response = await fetch(`/api/pr/${prId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        currentPR = await response.json();

        prListSection.classList.add('hidden');
        prDetailSection.classList.remove('hidden');
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
            <div class="pr-id">PR #${currentPR.pr_id}</div>
            <h2 class="pr-detail-title">${escapeHtml(currentPR.pr_title)}</h2>
            <a href="${escapeHtml(currentPR.pr_url)}" target="_blank" class="pr-detail-url">
                ${escapeHtml(currentPR.pr_url)}
            </a>
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
