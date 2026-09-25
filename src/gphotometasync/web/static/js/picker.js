// Google Photos Picker — local desktop OAuth (server session); no GIS / no Bearer from the browser
let authenticated = false;
/** @type {{ base_url: string, filename: string, type: ?string, mime_type: ?string, create_time: ?string, processing_status: ?string }[]} */
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
    return {
        base_url: baseUrl,
        filename,
        type: item.type || null,
        mime_type: item.mimeType || null,
        create_time: item.mediaMetadata?.creationTime || null,
        processing_status: item.videoProcessingStatus || null,
    };
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

// The selection is exported in small chunks so the page can show progress; the server
// is threaded, so a few chunks run in parallel.
const EXPORT_CHUNK_SIZE = 3;
const EXPORT_PARALLEL_REQUESTS = 3;

function warnBeforeLeaving(event) {
    event.preventDefault();
    event.returnValue = '';
}

function formatRemaining(seconds) {
    if (seconds < 60) return 'less than a minute left';
    const minutes = Math.round(seconds / 60);
    return `about ${minutes} minute${minutes !== 1 ? 's' : ''} left`;
}

function exportProgress(total) {
    const box = document.getElementById('export-progress');
    const bar = document.getElementById('export-progress-bar');
    const label = document.getElementById('export-progress-label');
    const count = document.getElementById('export-progress-count');
    const detail = document.getElementById('export-progress-detail');
    const startedAt = Date.now();
    bar.max = total;
    bar.value = 0;
    label.textContent = 'Saving metadata…';
    count.textContent = `0 of ${total}`;
    detail.textContent = 'Keep this page open until it finishes.';
    box.hidden = false;
    return {
        update(done, failed) {
            bar.value = done;
            count.textContent = `${done} of ${total}`;
            const parts = [];
            if (failed) parts.push(`${failed} couldn’t be saved`);
            if (done >= EXPORT_CHUNK_SIZE && done < total) {
                const perPhoto = (Date.now() - startedAt) / 1000 / done;
                parts.push(formatRemaining(perPhoto * (total - done)));
            }
            parts.push('keep this page open until it finishes');
            const text = parts.join(' · ');
            detail.textContent = text.charAt(0).toUpperCase() + text.slice(1) + '.';
        },
        finish() {
            label.textContent = 'Opening your files…';
            detail.textContent = '';
        },
        hide() {
            box.hidden = true;
        },
    };
}

/** POST one chunk. A 500 that still names the job means only this chunk's photos failed. */
async function exportChunk(chunk, jobId, includeJson) {
    const r = await fetch('/api/process-google-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            items: chunk.items,
            offset: chunk.offset,
            job_id: jobId,
            include_json: includeJson,
        }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok && !data.job_id) throw new Error(data.detail || data.error || r.statusText);
    return data;
}

async function extractAllExif() {
    if (!loadedPickerItems.length) {
        showStatus('Load photos first (choose photos, then wait for the list).', 'error');
        return;
    }
    const btn = document.getElementById('extract-exif-btn');
    const pickerBtn = document.getElementById('picker-btn');
    const includeJsonInput = document.getElementById('metadata-include-json');
    const includeJson = !includeJsonInput || includeJsonInput.checked;
    const items = loadedPickerItems.slice();
    const total = items.length;
    const chunks = [];
    for (let offset = 0; offset < total; offset += EXPORT_CHUNK_SIZE) {
        chunks.push({ offset, items: items.slice(offset, offset + EXPORT_CHUNK_SIZE) });
    }

    if (btn) btn.disabled = true;
    if (pickerBtn) pickerBtn.disabled = true;
    hideStatus();
    const progress = exportProgress(total);
    window.addEventListener('beforeunload', warnBeforeLeaving);

    let done = 0;
    let saved = 0;
    let jobId = null;
    let aborted = false;
    const record = (data, chunk) => {
        done += chunk.items.length;
        saved += data.processed || 0;
        progress.update(done, done - saved);
    };

    try {
        // The first chunk creates the job; the others add to it.
        const first = chunks.shift();
        const firstResult = await exportChunk(first, null, includeJson);
        jobId = firstResult.job_id;
        record(firstResult, first);
        const worker = async () => {
            while (chunks.length && !aborted) {
                const chunk = chunks.shift();
                try {
                    record(await exportChunk(chunk, jobId, includeJson), chunk);
                } catch (e) {
                    aborted = true; // stop the other workers from sending more chunks
                    throw e;
                }
            }
        };
        await Promise.all(Array.from({ length: EXPORT_PARALLEL_REQUESTS }, worker));
    } catch (e) {
        window.removeEventListener('beforeunload', warnBeforeLeaving);
        progress.hide();
        showStatus(`Something went wrong after ${done} of ${total} photos: ${e.message}`, 'error');
        if (btn) btn.disabled = false;
        if (pickerBtn) pickerBtn.disabled = false;
        return;
    }

    window.removeEventListener('beforeunload', warnBeforeLeaving);
    if (saved === 0) {
        progress.hide();
        showStatus('None of the photos could be saved. Check the terminal logs for details.', 'error');
        if (btn) btn.disabled = false;
        if (pickerBtn) pickerBtn.disabled = false;
        return;
    }
    progress.finish();
    const failed = total - saved;
    window.location.href = `/job/${encodeURIComponent(jobId)}${failed ? `?failed=${failed}` : ''}`;
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
