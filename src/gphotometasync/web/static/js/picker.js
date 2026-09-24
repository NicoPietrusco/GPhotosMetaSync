// Google Photos Picker — local desktop OAuth (server session); no GIS / no Bearer from the browser
let authenticated = false;
/** @type {{ base_url: string, filename: string }[]} */
let loadedPickerItems = [];

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

function itemToPayload(item) {
    const baseUrl =
        item.baseUrl ||
        item.base_url ||
        (item.mediaFile && item.mediaFile.baseUrl) ||
        '';
    const filename =
        item.filename ||
        (item.mediaFile && item.mediaFile.filename) ||
        'photo.jpg';
    return { base_url: baseUrl, filename };
}

/**
 * Google baseUrl includes a transform after "=" (e.g. =s0). Replace with a thumbnail size.
 */
function pickerThumbnailUrl(baseUrl) {
    if (!baseUrl) return '';
    const u = baseUrl.trim();
    const eq = u.lastIndexOf('=');
    if (eq !== -1) {
        return u.slice(0, eq) + '=w400-h300';
    }
    return u + '=w400-h300';
}

/** Same-origin proxy: Picker CDN needs OAuth; <img> cannot send Authorization. */
function pickerImageProxySrc(baseUrl) {
    const u = pickerThumbnailUrl(baseUrl);
    if (!u) return '';
    return `/api/picker-image?url=${encodeURIComponent(u)}`;
}

function setLoadedPickerItems(items) {
    loadedPickerItems = (items || [])
        .map(itemToPayload)
        .filter((x) => x.base_url);
    const btn = document.getElementById('extract-exif-btn');
    if (btn) {
        btn.style.display = loadedPickerItems.length > 0 ? 'inline-flex' : 'none';
        btn.disabled = false;
    }
}

async function extractAllExif() {
    if (!loadedPickerItems.length) {
        showStatus('Load photos first (choose photos, then wait for the list).', 'error');
        return;
    }
    const btn = document.getElementById('extract-exif-btn');
    const includeJson = document.getElementById('google-include-json');
    if (btn) btn.disabled = true;
    showStatus(`Saving metadata for ${loadedPickerItems.length} photo(s)…`, 'info');
    try {
        const r = await fetch('/api/process-google-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: loadedPickerItems,
                include_json: !includeJson || includeJson.checked,
            }),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || data.error || r.statusText);
        if (data.errors && data.errors.length) {
            showStatus(
                `Saved ${data.processed}. ${data.errors.length} couldn’t be saved (see terminal logs for details).`,
                'info'
            );
        }
        if (data.job_url) window.location.href = data.job_url;
    } catch (e) {
        showStatus(`Something went wrong: ${e.message}`, 'error');
        if (btn) btn.disabled = false;
    }
}

function authenticate() {
    showStatus('Opening Google sign-in…', 'info');
    window.location.href = '/auth';
}

async function createSession() {
    const response = await fetch('/api/create-session', {
        method: 'POST',
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to create session');
    }

    return await response.json();
}

async function openPicker() {
    if (!authenticated) {
        showStatus('Sign in with Google first (button above).', 'error');
        return;
    }
    try {
        showStatus("Opening Google's photo picker...", 'info');

        const sessionData = await createSession();

        if (!sessionData.pickerUri) {
            throw new Error('No picker URI returned');
        }

        const messageListener = (event) => {
            console.log('Received message event:', {
                origin: event.origin,
                data: event.data,
                source: event.source,
            });

            const validOrigins = [
                'https://photospicker.googleapis.com',
                'https://www.google.com',
                'https://accounts.google.com',
                'https://photos.google.com',
            ];

            if (!validOrigins.includes(event.origin)) {
                console.log('Message from unexpected origin:', event.origin);
            }

            if (event.data) {
                if (
                    event.data.mediaItems ||
                    event.data.items ||
                    event.data.selectedItems ||
                    event.data.photos
                ) {
                    window.removeEventListener('message', messageListener);
                    handlePickerResponse(event.data);
                } else if (
                    event.data.type === 'PICKER_RESPONSE' ||
                    event.data.action === 'selected'
                ) {
                    window.removeEventListener('message', messageListener);
                    handlePickerResponse(event.data);
                }
            }
        };

        window.addEventListener('message', messageListener);

        const pickerWindow = window.open(
            sessionData.pickerUri,
            'GooglePhotosPicker',
            'width=900,height=700,scrollbars=yes'
        );

        if (!pickerWindow) {
            window.removeEventListener('message', messageListener);
            throw new Error('Popup blocked. Please allow popups for this site.');
        }

        showStatus('Choose photos in the new window, then wait for them to appear here.', 'success');

        pollSessionStatus(sessionData.pollInterval);
    } catch (error) {
        showStatus(`Something went wrong: ${error.message}`, 'error');
    }
}

async function handlePickerResponse(data) {
    console.log('Handling picker response:', data);
    showStatus('Loading your photos…', 'info');

    try {
        const mediaItems = data.mediaItems || [];
        displayPhotos(mediaItems);
    } catch (error) {
        console.error('Error handling picker response:', error);
        showStatus(`Couldn't load photos: ${error.message}`, 'error');
    }
}

function displayPhotos(items) {
    const container = document.getElementById('photos-content');
    document.getElementById('photos-container').classList.add('show');

    if (items.length === 0) {
        setLoadedPickerItems([]);
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📷</div>
                <h3>No photos yet</h3>
                <p>Use “Choose photos”, pick images in the popup, then they’ll show up here.</p>
            </div>
        `;
        document.getElementById('photo-count').textContent = '0 photos';
        showStatus('No photos in this list.', 'info');
        return;
    }

    document.getElementById('photo-count').textContent =
        `${items.length} photo${items.length !== 1 ? 's' : ''}`;

    const grid = document.createElement('div');
    grid.className = 'photos-grid';

    items.forEach((item) => {
        const card = document.createElement('div');
        card.className = 'photo-card';

        const baseUrl = item.baseUrl || itemToPayload(item).base_url || '';
        const imgSrc = pickerImageProxySrc(baseUrl);
        const width = item.mediaMetadata?.width || '?';
        const height = item.mediaMetadata?.height || '?';
        const created = item.mediaMetadata?.creationTime
            ? new Date(item.mediaMetadata.creationTime).toLocaleDateString()
            : 'Unknown';

        const location = item.location || item.mediaMetadata?.location;
        const hasLocation = location && (location.latitude || location.longitude);
        const locationText = hasLocation
            ? `${location.latitude?.toFixed(6)}, ${location.longitude?.toFixed(6)}`
            : null;

        card.innerHTML = `
            ${imgSrc ? `<img src="${imgSrc}" alt="" loading="lazy">` : ''}
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
                    ${
                        locationText
                            ? `
                    <div class="meta-item">
                        <span>📍</span>
                        <span title="Latitude, Longitude">${locationText}</span>
                    </div>
                    `
                            : ''
                    }
                </div>
            </div>
        `;

        grid.appendChild(card);
    });

    container.innerHTML = '';
    container.appendChild(grid);
    setLoadedPickerItems(items);
    showStatus(`Loaded ${items.length} photo${items.length !== 1 ? 's' : ''}.`, 'success');
}

async function pollSessionStatus(pollInterval) {
    const intervalMs = parseInt(pollInterval, 10) * 1000 || 5000;
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
        container.innerHTML =
            '<div class="loading"><div class="spinner"></div><p>Loading your photos…</p></div>';
        document.getElementById('photos-container').classList.add('show');

        const response = await fetch('/api/list-selected');

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || error.error || 'Failed to load photos');
        }

        const data = await response.json();

        if (data.items.length === 0) {
            setLoadedPickerItems([]);
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📷</div>
                    <h3>No photos yet</h3>
                    <p>Use “Choose photos”, pick images in the popup, then they’ll show up here.</p>
                </div>
            `;
            document.getElementById('photo-count').textContent = '0 photos';
            return;
        }

        document.getElementById('photo-count').textContent =
            `${data.count} photo${data.count !== 1 ? 's' : ''}`;

        const grid = document.createElement('div');
        grid.className = 'photos-grid';

        data.items.forEach((item) => {
            const card = document.createElement('div');
            card.className = 'photo-card';

            const baseUrl = item.baseUrl || '';
            const imgSrc = pickerImageProxySrc(baseUrl);
            const width = item.mediaMetadata?.width || '?';
            const height = item.mediaMetadata?.height || '?';
            const created = item.mediaMetadata?.creationTime
                ? new Date(item.mediaMetadata.creationTime).toLocaleDateString()
                : 'Unknown';

            card.innerHTML = `
                ${imgSrc ? `<img src="${imgSrc}" alt="" loading="lazy">` : ''}
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
        setLoadedPickerItems(data.items);
        showStatus(`Loaded ${data.count} photo${data.count !== 1 ? 's' : ''}.`, 'success');
    } catch (error) {
        setLoadedPickerItems([]);
        document.getElementById('photos-content').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <h3>Error</h3>
                <p>${error.message}</p>
            </div>`;
    }
}

window.addEventListener('load', async () => {
    try {
        const response = await fetch('/api/check-auth');
        if (response.ok) {
            authenticated = true;
            const authBtn = document.getElementById('auth-btn');
            authBtn.textContent = 'Signed in';
            authBtn.className = 'btn btn-muted';
            authBtn.disabled = true;
            document.getElementById('picker-btn').disabled = false;
        } else {
            const data = await response.json().catch(() => ({}));
            if (data.reason === 'expired') {
                showStatus('Your Google session expired. Sign in again to choose photos.', 'info');
            }
        }
    } catch {
        // not signed in
    }
});
