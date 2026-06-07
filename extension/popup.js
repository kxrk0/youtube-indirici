// popup.js — YDL İndirici popup mantığı
'use strict';

const API_BASE = 'http://127.0.0.1:5000';

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const statusDot   = document.getElementById('statusDot');
const statusText  = document.getElementById('statusText');
const urlInput    = document.getElementById('urlInput');
const pasteBtn    = document.getElementById('pasteBtn');
const typeSelect  = document.getElementById('typeSelect');
const qualitySelect = document.getElementById('qualitySelect');
const downloadBtn = document.getElementById('downloadBtn');
const openAppBtn  = document.getElementById('openAppBtn');
const msgEl       = document.getElementById('msg');

// ─── Helpers ──────────────────────────────────────────────────────────────────
function setMsg(text, cls = 'msg-info') {
    msgEl.textContent = text;
    msgEl.className = cls;
}

function setStatus(online, text) {
    statusDot.className = 'dot ' + (online ? 'online' : 'offline');
    statusText.textContent = text;
}

// ─── Server health check ──────────────────────────────────────────────────────
async function checkServer() {
    try {
        const res = await fetch(API_BASE + '/health', { signal: AbortSignal.timeout(2000) });
        if (res.ok) {
            setStatus(true, 'Masaüstü uygulaması bağlı');
            downloadBtn.disabled = false;
            downloadBtn.title = '';
            return true;
        }
    } catch {}
    // Flask kapalı — native host var mı kontrol et
    const hasNative = await checkNativeHostAvailable();
    if (hasNative) {
        setStatus(false, 'Bağımsız mod (Native Host)');
        downloadBtn.disabled = false;
        downloadBtn.title = 'Masaüstü uygulaması olmadan indirme — yt-dlp gerekli';
    } else {
        setStatus(false, 'Uygulama kapalı — Native Host kurulu değil');
        downloadBtn.disabled = false; // allow anyway, background handles error
        downloadBtn.title = 'Masaüstü uygulamasını açın veya native_host\\install.bat çalıştırın';
    }
    return false;
}

async function checkNativeHostAvailable() {
    // background.js üzerinden native host ping
    return new Promise(resolve => {
        chrome.runtime.sendMessage({ action: 'ping_native_host' }, (resp) => {
            resolve(resp && resp.available === true);
        });
    });
}

// ─── Auto-fill from active tab ────────────────────────────────────────────────
async function fillFromActiveTab() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab?.url && isDownloadableUrl(tab.url)) {
            urlInput.value = tab.url;
            setMsg('Aktif sekme URL\'si yüklendi.', 'msg-ok');
        }
    } catch {}
}

function isDownloadableUrl(url) {
    if (!url) return false;
    return /youtube\.com|youtu\.be|music\.youtube\.com|soundcloud\.com|spotify\.com|tiktok\.com|instagram\.com|twitter\.com|x\.com|vimeo\.com|twitch\.tv|reddit\.com|redd\.it|bandcamp\.com|dailymotion\.com/.test(url);
}

// ─── Paste from clipboard ─────────────────────────────────────────────────────
pasteBtn.addEventListener('click', async () => {
    try {
        const text = await navigator.clipboard.readText();
        if (text) {
            urlInput.value = text.trim();
            setMsg('Panodan yapıştırıldı.', 'msg-info');
        }
    } catch {
        setMsg('Pano erişimi reddedildi.', 'msg-err');
    }
});

// ─── Quality/type sync ────────────────────────────────────────────────────────
typeSelect.addEventListener('change', () => {
    qualitySelect.disabled = typeSelect.value === 'audio';
});

// ─── Download ─────────────────────────────────────────────────────────────────
downloadBtn.addEventListener('click', async () => {
    const url = urlInput.value.trim();
    if (!url) { setMsg('URL boş.', 'msg-err'); return; }
    if (!isDownloadableUrl(url)) { setMsg('Desteklenmeyen URL.', 'msg-err'); return; }

    const isAudio = typeSelect.value === 'audio';
    const quality = qualitySelect.value;
    const fmt     = isAudio ? 'audio' : (quality === 'best' ? 'best' : `bestvideo[height<=${quality}]+bestaudio/best`);

    downloadBtn.disabled = true;
    setMsg('Gönderiliyor...', 'msg-info');

    try {
        const res = await fetch(API_BASE + '/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, format: fmt, type: isAudio ? 'audio' : 'video' }),
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            setMsg('✅ İndirme başlatıldı! Masaüstü uygulamasını kontrol edin.', 'msg-ok');
        } else {
            setMsg('❌ ' + (data.error || 'Sunucu hatası'), 'msg-err');
        }
    } catch (e) {
        setMsg('❌ Bağlantı hatası: masaüstü uygulaması açık mı?', 'msg-err');
    } finally {
        downloadBtn.disabled = false;
    }
});

// ─── Open desktop app hint ───────────────────────────────────────────────────
openAppBtn.addEventListener('click', () => {
    setMsg('ℹ Masaüstü uygulamasını manuel olarak başlatın (python main.py).', 'msg-info');
});

// ─── Active Downloads ─────────────────────────────────────────────────────────
async function fetchActiveQueue() {
    try {
        const res = await fetch(API_BASE + '/api/queue', { signal: AbortSignal.timeout(2000) });
        if (!res.ok) return;
        const data = await res.json();
        renderQueue(data.queue || []);
    } catch {}
}

function renderQueue(queue) {
    let el = document.getElementById('queueSection');
    if (!el) {
        el = document.createElement('div');
        el.id = 'queueSection';
        el.style.cssText = 'padding:8px 16px 12px; border-top:1px solid rgba(255,255,255,0.06);';
        document.body.appendChild(el);
    }
    if (queue.length === 0) {
        el.innerHTML = '<div style="font-size:11px;color:#555;padding:4px 0;">Aktif indirme yok.</div>';
        return;
    }
    const items = queue.slice(0, 5).map(q => {
        const title = (q.title || q.url || '').slice(0, 40);
        const pct   = q.progress || 0;
        return `<div style="margin-bottom:6px;">
          <div style="font-size:11px;color:#ccc;margin-bottom:2px;">${title}</div>
          <div style="background:#0f3460;border-radius:3px;height:4px;overflow:hidden;">
            <div style="background:#0078d4;height:4px;width:${pct}%;transition:width 0.3s;"></div>
          </div>
        </div>`;
    }).join('');
    el.innerHTML = `<div style="font-size:11px;color:#aaa;margin-bottom:6px;">${queue.length} Aktif İndirme</div>${items}`;
}

// ─── Init ─────────────────────────────────────────────────────────────────────
(async () => {
    downloadBtn.disabled = true;
    qualitySelect.disabled = true; // default: audio selected
    await checkServer();
    await fillFromActiveTab();
    await fetchActiveQueue();
    // Recheck every 5 seconds while popup open
    setInterval(checkServer, 5000);
    setInterval(fetchActiveQueue, 3000);
})();
