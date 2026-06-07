// background.js — Universal Downloader Companion Service Worker

const API_BASE        = 'http://127.0.0.1:5000';
const DL_FOLDER       = 'YDL İndirilenler'; // Subfolder in browser's downloads directory
const NM_HOST_NAME    = 'com.youtube_indirici.host';
let _cachedToken      = null;
let _activeDownloads  = 0;
let _flaskAvailable   = null;   // null=unknown, true, false
let _flaskCheckTs     = 0;      // timestamp of last check
const FLASK_CHECK_TTL = 15000;  // 15 s cache

// ─── Helpers ──────────────────────────────────────────────────────────────────

function sanitizeFilename(str) {
    return (str || 'download')
        .replace(/[\\/:*?"<>|]/g, '_')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 120);
}

function extFromMime(mimeType) {
    if (!mimeType) return 'mp4';
    if (mimeType.includes('webm'))  return 'webm';
    if (mimeType.includes('ogg'))   return 'ogg';
    if (mimeType.includes('mp3') || mimeType.includes('mpeg')) return 'mp3';
    if (mimeType.includes('mp4'))   return 'mp4';
    if (mimeType.includes('m4a'))   return 'm4a';
    return 'mp4';
}

// ─── Token ────────────────────────────────────────────────────────────────────

async function getToken() {
    if (_cachedToken) return _cachedToken;
    try {
        const res = await fetch(`${API_BASE}/ping`);
        if (res.ok) {
            const d = await res.json();
            _cachedToken = d.token || '';
            return _cachedToken;
        }
    } catch {}
    return '';
}

// ─── Badge ────────────────────────────────────────────────────────────────────

function updateBadge() {
    if (_activeDownloads > 0) {
        chrome.action.setBadgeText({ text: String(_activeDownloads) });
        chrome.action.setBadgeBackgroundColor({ color: '#0078D4' });
    } else {
        chrome.action.setBadgeText({ text: '' });
    }
}

function bumpBadge(ms = 60000) {
    _activeDownloads++;
    updateBadge();
    setTimeout(() => { _activeDownloads = Math.max(0, _activeDownloads - 1); updateBadge(); }, ms);
}

// ─── Flask Availability Check ────────────────────────────────────────────────

async function checkFlaskAvailable() {
    const now = Date.now();
    if (_flaskAvailable !== null && (now - _flaskCheckTs) < FLASK_CHECK_TTL) {
        return _flaskAvailable;
    }
    try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 2000);
        const res = await fetch(`${API_BASE}/health`, { signal: ctrl.signal });
        clearTimeout(t);
        _flaskAvailable = res.ok;
    } catch {
        _flaskAvailable = false;
    }
    _flaskCheckTs = Date.now();
    return _flaskAvailable;
}

// ─── Native Messaging Download (masaüstü uygulaması kapalıyken) ───────────────

function doNativeDownload(url, formatType, title) {
    return new Promise((resolve, reject) => {
        let port;
        try {
            port = chrome.runtime.connectNative(NM_HOST_NAME);
        } catch (e) {
            reject(new Error(
                'Native host kurulu değil.\n' +
                'native_host\\install.bat dosyasını çalıştırın.'
            ));
            return;
        }

        let settled = false;
        const settle = (fn, val) => {
            if (settled) return;
            settled = true;
            try { port.disconnect(); } catch (_) {}
            fn(val);
        };

        port.onMessage.addListener((msg) => {
            if (msg.status === 'completed') {
                settle(resolve, msg);
            } else if (msg.status === 'error') {
                settle(reject, new Error(msg.message || 'İndirme hatası'));
            }
            // status === 'started' → sadece log
        });

        port.onDisconnect.addListener(() => {
            const err = chrome.runtime.lastError;
            if (!settled) {
                settle(reject, new Error(
                    err ? err.message : 'Native host bağlantısı kesildi'
                ));
            }
        });

        port.postMessage({
            url,
            formatType: formatType || 'video',
            format: formatType === 'audio' ? 'audio' : 'best',
            title: title || url,
        });

        bumpBadge(180000); // 3 dk tahmini

        chrome.notifications.create(`nm_${Date.now()}`, {
            type: 'basic',
            iconUrl: 'icons/icon48.png',
            title: '⬇ İndirme Başladı (Bağımsız Mod)',
            message: `"${(title || url).slice(0, 60)}" → Belgeler/YDL İndirilenler/`,
            priority: 1,
        });
    });
}

// ─── Chrome Downloads ─────────────────────────────────────────────────────────

function downloadToFolder(url, title, ext) {
    const safe = sanitizeFilename(title);
    const filename = `${DL_FOLDER}/${safe}.${ext || 'mp4'}`;

    return new Promise((resolve, reject) => {
        chrome.downloads.download({
            url,
            filename,
            conflictAction: 'uniquify',
            saveAs: false,
        }, (downloadId) => {
            if (chrome.runtime.lastError) {
                reject(new Error(chrome.runtime.lastError.message));
            } else {
                bumpBadge(120000); // 2 min estimate
                chrome.notifications.create({
                    type: 'basic',
                    iconUrl: 'icons/icon48.png',
                    title: 'İndirme Başladı',
                    message: `"${safe.slice(0, 60)}" → ${DL_FOLDER}/`,
                    priority: 1,
                });
                resolve(downloadId);
            }
        });
    });
}

// ─── Platform Fetch-Based Extractors ─────────────────────────────────────────
// Used when content.js signals needsFetch (Vimeo, Dailymotion)

async function resolveVimeo(videoId, format) {
    // Vimeo player config gives progressive download URLs
    const res  = await fetch(`https://player.vimeo.com/video/${videoId}/config`, {
        headers: { 'Referer': `https://vimeo.com/${videoId}` }
    });
    const data = await res.json();
    const files = data?.request?.files?.progressive || [];
    if (!files.length) return null;

    const heightMap = { '1080p': 1080, '720p': 720, '480p': 480, 'best': 9999 };
    const maxH = heightMap[format] || 9999;
    const sorted = files
        .filter(f => (f.height || 0) <= maxH)
        .sort((a, b) => (b.height || 0) - (a.height || 0));
    return sorted[0] ? { url: sorted[0].url, ext: 'mp4' } : null;
}

async function resolveDailymotion(videoId, format) {
    const res  = await fetch(`https://api.dailymotion.com/video/${videoId}?fields=stream_h264_hd_url,stream_h264_url,stream_h264_ld_url`);
    const data = await res.json();
    const url  = (format === '720p' || format === 'best')
        ? (data.stream_h264_hd_url || data.stream_h264_url)
        : data.stream_h264_ld_url || data.stream_h264_url;
    return url ? { url, ext: 'mp4' } : null;
}

// ─── Flask API Download (YouTube, SoundCloud, Twitch) ─────────────────────────

async function doFlaskDownload(videoUrl, format, formatType, videoTitle, sendResponse, extra = {}) {
    // Flask (masaüstü uygulama) açık mı kontrol et
    const flaskUp = await checkFlaskAvailable();

    if (!flaskUp) {
        // ── Bağımsız mod: Native Messaging Host üzerinden indir ──────────────
        try {
            await doNativeDownload(videoUrl, formatType, videoTitle);
            if (sendResponse) sendResponse({ status: 'success', mode: 'native' });
        } catch (err) {
            chrome.notifications.create(`err_${Date.now()}`, {
                type: 'basic',
                iconUrl: 'icons/icon48.png',
                title: '❌ İndirme Hatası (Bağımsız Mod)',
                message: err.message.slice(0, 120),
                priority: 2,
            });
            if (sendResponse) sendResponse({ status: 'error', message: err.message });
        }
        return;
    }

    // ── Normal mod: Masaüstü uygulaması üzerinden Flask API ─────────────────
    try {
        const token = await getToken();
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['X-API-Key'] = token;

        const res = await fetch(`${API_BASE}/download`, {
            method: 'POST', headers,
            body: JSON.stringify({ videoUrl, format, formatType, videoTitle, ...extra }),
        });

        if (!res.ok) {
            const text = await res.text();
            if (res.status === 401) _cachedToken = null;
            throw new Error(`HTTP ${res.status}: ${text}`);
        }

        bumpBadge(30000);
        const data = await res.json();

        chrome.notifications.create(`dl_${Date.now()}`, {
            type: 'basic',
            iconUrl: 'icons/icon48.png',
            title: '⬇ İndirme Başladı',
            message: `"${videoTitle.slice(0, 60)}" masaüstü uygulamasına eklendi`,
            priority: 1,
        });

        if (sendResponse) sendResponse({ status: 'success', data });
    } catch (err) {
        // Flask çağrısı başarısız olduysa native'e düş
        _flaskAvailable = false;
        _flaskCheckTs = 0;
        try {
            await doNativeDownload(videoUrl, formatType, videoTitle);
            if (sendResponse) sendResponse({ status: 'success', mode: 'native_fallback' });
        } catch (err2) {
            chrome.notifications.create(`err2_${Date.now()}`, {
                type: 'basic',
                iconUrl: 'icons/icon48.png',
                title: '❌ İndirme Hatası',
                message: err2.message.slice(0, 120),
                priority: 2,
            });
            if (sendResponse) sendResponse({ status: 'error', message: err2.message });
        }
    }
}

// ─── Message Handler ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

    // Standalone direct URL download → chrome.downloads → YDL İndirilenler/
    if (request.action === 'download_direct') {
        const { url, ext, title, mimeHint } = request;
        const finalExt = ext || extFromMime(mimeHint) || 'mp4';
        downloadToFolder(url, title, finalExt)
            .then(id => sendResponse({ status: 'success', downloadId: id }))
            .catch(err => {
                chrome.notifications.create({
                    type: 'basic', iconUrl: 'icons/icon48.png',
                    title: 'İndirme Hatası', message: err.message.slice(0, 100), priority: 2,
                });
                sendResponse({ status: 'error', message: err.message });
            });
        return true; // async
    }

    // Fetch-based extraction (Vimeo player config, Dailymotion API, etc.)
    if (request.action === 'download_fetch') {
        const { platform, videoId, format, title } = request;
        (async () => {
            try {
                let info = null;
                if (platform === 'vimeo')       info = await resolveVimeo(videoId, format);
                if (platform === 'dailymotion') info = await resolveDailymotion(videoId, format);
                if (info?.url) {
                    await downloadToFolder(info.url, title, info.ext || 'mp4');
                    sendResponse({ status: 'success' });
                } else {
                    throw new Error('Doğrudan URL bulunamadı');
                }
            } catch (err) {
                chrome.notifications.create({
                    type: 'basic', iconUrl: 'icons/icon48.png',
                    title: 'İndirme Hatası', message: err.message.slice(0, 100), priority: 2,
                });
                sendResponse({ status: 'error', message: err.message });
            }
        })();
        return true; // async
    }

    // Flask API (YouTube, SoundCloud, Twitch, Spotify)
    if (request.action === 'download') {
        const { videoUrl, format, formatType, videoTitle } = request;
        doFlaskDownload(videoUrl, format, formatType, videoTitle, sendResponse);
        return true;
    }

    // Native host availability ping
    if (request.action === 'ping_native_host') {
        try {
            const port = chrome.runtime.connectNative(NM_HOST_NAME);
            port.disconnect();
            sendResponse({ available: true });
        } catch {
            sendResponse({ available: false });
        }
        return true;
    }
});

// ─── Context Menus ────────────────────────────────────────────────────────────

const SUPPORTED_PAGES = [
    '*://www.youtube.com/watch*',
    '*://soundcloud.com/*/*',
    '*://open.spotify.com/track/*',
    '*://open.spotify.com/album/*',
    '*://*.bandcamp.com/track/*',
    '*://*.bandcamp.com/album/*',
    '*://www.tiktok.com/*',
    '*://www.instagram.com/p/*',
    '*://www.instagram.com/reel/*',
    '*://twitter.com/*/status/*',
    '*://x.com/*/status/*',
    '*://vimeo.com/*',
    '*://www.dailymotion.com/video/*',
    '*://www.twitch.tv/videos/*',
    '*://clips.twitch.tv/*',
    '*://www.reddit.com/r/*/comments/*',
];

chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.removeAll(() => {
        chrome.contextMenus.create({
            id: 'ydl-link-video',
            title: '▶ YDL: Linki İndir (Video)',
            contexts: ['link'],
        });
        chrome.contextMenus.create({
            id: 'ydl-link-audio',
            title: '♪ YDL: Linki İndir (MP3)',
            contexts: ['link'],
        });
        chrome.contextMenus.create({
            id: 'ydl-sep',
            type: 'separator',
            contexts: ['page'],
            documentUrlPatterns: SUPPORTED_PAGES,
        });
        chrome.contextMenus.create({
            id: 'ydl-page-video',
            title: '▶ YDL: Bu Sayfayı İndir (Video)',
            contexts: ['page'],
            documentUrlPatterns: SUPPORTED_PAGES,
        });
        chrome.contextMenus.create({
            id: 'ydl-page-audio',
            title: '♪ YDL: Bu Sayfayı İndir (MP3)',
            contexts: ['page'],
            documentUrlPatterns: SUPPORTED_PAGES,
        });
        chrome.contextMenus.create({
            id: 'ydl-timestamp-clip',
            title: '⏱ YDL: Bu Anı Kırp & İndir (±60 sn)',
            contexts: ['page'],
            documentUrlPatterns: ['*://www.youtube.com/watch*', '*://music.youtube.com/watch*'],
        });
        chrome.contextMenus.create({
            id: 'ydl-video-sep',
            type: 'separator',
            contexts: ['video'],
        });
        chrome.contextMenus.create({
            id: 'ydl-video-dl',
            title: '⬇ YDL: Video Dosyasını Doğrudan İndir',
            contexts: ['video'],
        });
        chrome.contextMenus.create({
            id: 'ydl-video-audio',
            title: '🎵 YDL: Ses Olarak İndir (MP3)',
            contexts: ['video'],
        });
    });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
    let url, fmt, type, title;
    switch (info.menuItemId) {
        case 'ydl-link-video':
            url = info.linkUrl; fmt = 'best'; type = 'video'; title = info.linkUrl; break;
        case 'ydl-link-audio':
            url = info.linkUrl; fmt = 'audio'; type = 'audio'; title = info.linkUrl; break;
        case 'ydl-page-video':
            url = tab.url; fmt = 'best'; type = 'video'; title = tab.title || tab.url; break;
        case 'ydl-page-audio':
            url = tab.url; fmt = 'audio'; type = 'audio'; title = tab.title || tab.url; break;
        case 'ydl-timestamp-clip': {
            // Inject script to get current video time, then download
            chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: () => {
                    const v = document.querySelector('video.html5-main-video') || document.querySelector('video');
                    return v ? Math.floor(v.currentTime) : 0;
                }
            }, (results) => {
                const ts = results?.[0]?.result || 0;
                const start = Math.max(0, ts - 60);
                const end   = ts + 60;
                doFlaskDownload(tab.url, 'best', 'video', (tab.title || tab.url).slice(0, 80), null,
                    { startTime: start, endTime: end });
            });
            return;
        }
        case 'ydl-video-dl':
            // src of <video> element user right-clicked
            url = info.srcUrl || tab.url; fmt = 'best'; type = 'video';
            title = (tab.title || 'video').slice(0, 100); break;
        case 'ydl-video-audio':
            url = info.srcUrl || tab.url; fmt = 'audio'; type = 'audio';
            title = (tab.title || 'audio').slice(0, 100); break;
        default: return;
    }
    // Context menu always tries Flask (safest — handles all platforms)
    doFlaskDownload(url, fmt, type, (title || url).slice(0, 100), null);
});
