// background.js - Service Worker

const API_BASE = 'http://127.0.0.1:5000';
let _cachedToken = null;

async function getToken() {
    if (_cachedToken) return _cachedToken;
    try {
        const res = await fetch(`${API_BASE}/ping`);
        if (res.ok) {
            const data = await res.json();
            _cachedToken = data.token || '';
            return _cachedToken;
        }
    } catch (e) {
        console.warn('Token alınamadı, anahtarsız deneniyor:', e.message);
    }
    return '';
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'download') {
        const { videoUrl, format, formatType, videoTitle } = request;
        console.log(`Background: ${format} (${formatType}) - "${videoTitle}"`);

        (async () => {
            try {
                const token = await getToken();
                const headers = { 'Content-Type': 'application/json' };
                if (token) headers['X-API-Key'] = token;

                const res = await fetch(`${API_BASE}/download`, {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({ videoUrl, format, formatType, videoTitle }),
                });

                if (!res.ok) {
                    const text = await res.text();
                    // Token expired — retry once with fresh token
                    if (res.status === 401) {
                        _cachedToken = null;
                    }
                    throw new Error(`HTTP ${res.status}: ${text}`);
                }

                const data = await res.json();
                console.log('İndirme isteği gönderildi:', data);

                chrome.notifications.create({
                    type: 'basic',
                    iconUrl: 'icons/download.svg',
                    title: 'İndirme Başladı',
                    message: `"${videoTitle}" indiriliyor...`,
                    priority: 2
                });

                sendResponse({ status: 'success', data });
            } catch (err) {
                console.error('İndirme hatası:', err);
                chrome.notifications.create({
                    type: 'basic',
                    iconUrl: 'icons/download.svg',
                    title: 'İndirme Hatası',
                    message: err.message.substring(0, 100),
                    priority: 2
                });
                sendResponse({ status: 'error', message: err.message });
            }
        })();

        return true; // Asenkron yanıt için
    }
});
