// Google Photos Picker JavaScript
let authenticated = false;
let sessionId = null;

function showStatus(message, type) {
    const el = document.getElementById('status');
    el.textContent = message;
    el.className = `status ${type}`;
    el.style.display = 'block';

    if (type === 'success') {
        setTimeout(() => {
            el.style.display = 'none';
        }, 5000);
    }
}

function hideStatus() {
    document.getElementById('status').style.display = 'none';
}

async function authenticate() {
    showStatus('🔄 Redirecting to Google...', 'info');
    window.location.href = '/auth';
}

async function createSession() {
    const response = await fetch('/api/create-session', {
        method: 'POST'
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create session');
    }

    return await response.json();
}

async function openPicker() {
    try {
        showStatus('🔄 Opening photo picker...', 'info');

        const sessionData = await createSession();

        if (!sessionData.pickerUri) {
            throw new Error('No picker URI returned');
        }

        // Set up message listener for picker response
        const messageListener = (event) => {
            // Log ALL messages to debug
            console.log('Received message event:', {
                origin: event.origin,
                data: event.data,
                source: event.source
            });

            // Try to handle messages from various origins
            // Google might use different domains
            const validOrigins = [
                'https://photospicker.googleapis.com',
                'https://www.google.com',
                'https://accounts.google.com',
                'https://photos.google.com'
            ];

            // Log even if origin doesn't match, for debugging
            if (!validOrigins.includes(event.origin)) {
                console.log('Message from unexpected origin:', event.origin);
                // Still try to process it for debugging
            }

            // Try different possible data structures
            if (event.data) {
                console.log('Message data type:', typeof event.data);
                console.log('Message data keys:', Object.keys(event.data));

                // Check for various possible response formats
                if (event.data.mediaItems || 
                    event.data.items || 
                    event.data.selectedItems ||
                    event.data.photos) {
                    window.removeEventListener('message', messageListener);
                    handlePickerResponse(event.data);
                } else if (event.data.type === 'PICKER_RESPONSE' || 
                           event.data.action === 'selected') {
                    console.log('Detected picker response type');
                    window.removeEventListener('message', messageListener);
                    handlePickerResponse(event.data);
                }
            }
        };

        window.addEventListener('message', messageListener);
        console.log('Message listener attached, waiting for picker response...');

        // Open Google's Photo Picker
        const pickerWindow = window.open(
            sessionData.pickerUri,
            'GooglePhotosPicker',
            'width=900,height=700,scrollbars=yes'
        );

        if (!pickerWindow) {
            window.removeEventListener('message', messageListener);
            throw new Error('Popup blocked. Please allow popups for this site.');
        }

        showStatus('✅ Select your photos in the popup window', 'success');
        document.getElementById('refresh-btn').style.display = 'inline-flex';

        // Also keep polling as backup
        pollSessionStatus(sessionData.sessionId, sessionData.pollInterval);

    } catch (error) {
        showStatus(`❌ ${error.message}`, 'error');
    }
}

async function handlePickerResponse(data) {
    console.log('Handling picker response:', data);
    showStatus('🔄 Loading selected photos...', 'info');
    
    try {
        const mediaItems = data.mediaItems || [];
        displayPhotos(mediaItems);
    } catch (error) {
        console.error('Error handling picker response:', error);
        showStatus(`❌ Error loading photos: ${error.message}`, 'error');
    }
}

function displayPhotos(items) {
    const container = document.getElementById('photos-content');
    document.getElementById('photos-container').classList.add('show');

    if (items.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📷</div>
                <h3>No photos selected</h3>
                <p>Click "Select Photos" to choose photos from your library</p>
            </div>
        `;
        document.getElementById('photo-count').textContent = '0 photos';
        showStatus('No photos selected', 'info');
        return;
    }

    // Update count
    document.getElementById('photo-count').textContent =
        `${items.length} photo${items.length !== 1 ? 's' : ''}`;

    // Display photos
    const grid = document.createElement('div');
    grid.className = 'photos-grid';

    items.forEach(item => {
        const card = document.createElement('div');
        card.className = 'photo-card';

        const baseUrl = item.baseUrl || '';
        const thumbnail = baseUrl ? `${baseUrl}=w400-h300` : '';
        const width = item.mediaMetadata?.width || '?';
        const height = item.mediaMetadata?.height || '?';
        const created = item.mediaMetadata?.creationTime ?
            new Date(item.mediaMetadata.creationTime).toLocaleDateString() : 'Unknown';
        
        // Extract location if available
        const location = item.location || item.mediaMetadata?.location;
        const hasLocation = location && (location.latitude || location.longitude);
        const locationText = hasLocation 
            ? `${location.latitude?.toFixed(6)}, ${location.longitude?.toFixed(6)}`
            : null;

        card.innerHTML = `
            ${thumbnail ? `<img src="${thumbnail}" alt="${item.filename || 'Photo'}" loading="lazy">` : ''}
            <div class="photo-info">
                <h3 title="${item.filename || 'Untitled'}">${item.filename || 'Untitled'}</h3>
                <div class="photo-meta">
                    <div class="meta-item">
                        <span>📐</span>
                        <span>${width} × ${height}</span>
                    </div>
                    <div class="meta-item">
                        <span>📅</span>
                        <span>${created}</span>
                    </div>
                    <div class="meta-item">
                        <span>📄</span>
                        <span>${item.mimeType?.split('/')[1]?.toUpperCase() || 'Unknown'}</span>
                    </div>
                    ${locationText ? `
                    <div class="meta-item">
                        <span>📍</span>
                        <span title="Latitude, Longitude">${locationText}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;

        grid.appendChild(card);
    });

    container.innerHTML = '';
    container.appendChild(grid);
    showStatus(`✅ Loaded ${items.length} photo${items.length !== 1 ? 's' : ''}`, 'success');
}

async function pollSessionStatus(sessionId, pollInterval) {
    const intervalMs = parseInt(pollInterval) * 1000 || 5000;
    let pollCount = 0;
    const maxPolls = 60;

    const checkStatus = setInterval(async () => {
        try {
            pollCount++;

            const response = await fetch('/api/session-status');
            if (response.ok) {
                const status = await response.json();

                if (status.mediaItemsSet) {
                    clearInterval(checkStatus);
                    hideStatus();
                    await loadSelectedPhotos();
                }
            }

            if (pollCount >= maxPolls) {
                clearInterval(checkStatus);
                hideStatus();
            }

        } catch (error) {
            console.error('Polling error:', error);
        }
    }, intervalMs);
}

async function loadSelectedPhotos() {
    try {
        const container = document.getElementById('photos-content');
        container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading photos...</p></div>';
        document.getElementById('photos-container').classList.add('show');

        const response = await fetch('/api/list-selected');

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to load photos');
        }

        const data = await response.json();

        if (data.items.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📷</div>
                    <h3>No photos selected</h3>
                    <p>Click "Select Photos" to choose photos from your library</p>
                </div>
            `;
            document.getElementById('photo-count').textContent = '0 photos';
            return;
        }

        // Update count
        document.getElementById('photo-count').textContent =
            `${data.count} photo${data.count !== 1 ? 's' : ''}`;

        // Display photos
        const grid = document.createElement('div');
        grid.className = 'photos-grid';

        data.items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'photo-card';

            const baseUrl = item.baseUrl || '';
            const thumbnail = baseUrl ? `${baseUrl}=w400-h300` : '';
            const width = item.mediaMetadata?.width || '?';
            const height = item.mediaMetadata?.height || '?';
            const created = item.mediaMetadata?.creationTime ?
                new Date(item.mediaMetadata.creationTime).toLocaleDateString() : 'Unknown';

            card.innerHTML = `
                ${thumbnail ? `<img src="${thumbnail}" alt="${item.filename || 'Photo'}" loading="lazy">` : ''}
                <div class="photo-info">
                    <h3 title="${item.filename || 'Untitled'}">${item.filename || 'Untitled'}</h3>
                    <div class="photo-meta">
                        <div class="meta-item">
                            <span>📐</span>
                            <span>${width} × ${height}</span>
                        </div>
                        <div class="meta-item">
                            <span>📅</span>
                            <span>${created}</span>
                        </div>
                        <div class="meta-item">
                            <span>📄</span>
                            <span>${item.mimeType?.split('/')[1]?.toUpperCase() || 'Unknown'}</span>
                        </div>
                    </div>
                </div>
            `;

            grid.appendChild(card);
        });

        container.innerHTML = '';
        container.appendChild(grid);
        showStatus(`✅ Loaded ${data.count} photo${data.count !== 1 ? 's' : ''}`, 'success');

    } catch (error) {
        document.getElementById('photos-content').innerHTML =
            `<div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <h3>Error</h3>
                <p>${error.message}</p>
            </div>`;
    }
}

// Check auth on load
window.addEventListener('load', async () => {
    try {
        const response = await fetch('/api/check-auth');
        if (response.ok) {
            authenticated = true;
            document.getElementById('auth-btn').textContent = '✅ Signed In';
            document.getElementById('auth-btn').disabled = true;
            document.getElementById('picker-btn').disabled = false;
        }
    } catch {
        // Not authenticated
    }
});
