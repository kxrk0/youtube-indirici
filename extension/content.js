'use strict';

const BTN_ID   = 'ydl-inline-btn';
const FLOAT_ID = 'ydl-float-btn';
const MENU_ID  = 'ydl-menu';
const API      = 'http://127.0.0.1:5000';
const STORE_KEY = 'ydl_last_fmt';

// Platforms that can't be downloaded standalone (need desktop app)
const NEEDS_APP = new Set(['YouTube', 'YouTube Music', 'SoundCloud', 'Spotify', 'Twitch']);

// Platforms truly blocked by DRM (not Spotify — handled via spotidownloader.com)
const DRM_PLATFORMS = new Set(['Apple Music', 'Tidal', 'Deezer']);

// ─── Helpers ──────────────────────────────────────────────────────────────────

function _fmtSec(s) {
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${String(r).padStart(2, '0')}`;
}

// ─── Platform Registry ────────────────────────────────────────────────────────

const PLATFORMS = {
    youtube: {
        name: 'YouTube', color: '#FF0000',
        hosts: ['www.youtube.com'],
        isPage: () => location.pathname.startsWith('/watch'),
        findBar() {
            for (const s of [
                'ytd-watch-metadata #actions-inner', 'ytd-watch-metadata #actions',
                '#above-the-fold #actions-inner',    '#above-the-fold #actions',
                '#actions-inner', '#actions',         '#top-level-buttons-computed',
                'ytd-video-primary-info-renderer #menu-container',
            ]) { const el = document.querySelector(s); if (el) return el; }
            return null;
        },
        getTitle: () => document.title.replace(' - YouTube', '').trim(),
        getTimestamp() {
            // Oynatıcının şu anki konumunu saniye cinsinden döndür
            const video = document.querySelector('video.html5-main-video')
                       || document.querySelector('video');
            return video ? Math.floor(video.currentTime) : null;
        },
        getDuration() {
            for (const script of document.querySelectorAll('script')) {
                const t = script.textContent;
                if (!t.includes('ytInitialPlayerResponse')) continue;
                const m = t.match(/"lengthSeconds"\s*:\s*"(\d+)"/);
                if (m) {
                    const s = parseInt(m[1]);
                    const h = Math.floor(s / 3600);
                    const min = Math.floor((s % 3600) / 60);
                    const sec = s % 60;
                    return h > 0
                        ? `${h}:${String(min).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
                        : `${min}:${String(sec).padStart(2,'0')}`;
                }
                break;
            }
            const el = document.querySelector('.ytp-time-duration');
            return el?.textContent?.trim() || null;
        },
        inline: true,
        getFormats() {
            // Read actual available qualities from ytInitialPlayerResponse
            const heights = new Set();
            for (const script of document.querySelectorAll('script')) {
                const t = script.textContent;
                if (!t.includes('ytInitialPlayerResponse')) continue;
                for (const m of t.matchAll(/"qualityLabel"\s*:\s*"(\d+)p[^"]*"/g)) {
                    heights.add(parseInt(m[1]));
                }
                break;
            }

            const LABEL = {
                2160: '📺 4K (2160p)',
                1440: '📺 1440p',
                1080: '📺 1080p MP4',
                720:  '📺 720p MP4',
                480:  '📺 480p MP4',
                360:  '📺 360p MP4',
                240:  '📺 240p MP4',
                144:  '📺 144p MP4',
            };

            const list = [{ label: '🎬 En İyi Kalite', fmt: 'best', type: 'video' }];
            const sorted = [...heights].sort((a, b) => b - a);

            if (sorted.length) {
                for (const h of sorted) {
                    if (LABEL[h]) list.push({ label: LABEL[h], fmt: `${h}p`, type: 'video' });
                }
            } else {
                // Fallback if page not fully loaded yet
                list.push(
                    { label: '📺 1080p MP4', fmt: '1080p', type: 'video' },
                    { label: '📺 720p MP4',  fmt: '720p',  type: 'video' },
                    { label: '📺 480p MP4',  fmt: '480p',  type: 'video' },
                );
            }

            list.push({ label: '📝 Altyazıyla İndir (TR/EN)', fmt: 'best_subs', type: 'video' });
            list.push({ label: '🎵 MP3 (Ses)', fmt: 'audio', type: 'audio' });
            // Zaman damgası klibi — oynatıcı konumu ±60 sn
            const ts = this.getTimestamp?.();
            if (ts !== null && ts !== undefined && ts > 0) {
                const start = Math.max(0, ts - 60);
                const end   = ts + 60;
                list.push({ label: `⏱ Bu Anı Kırp (${_fmtSec(start)}–${_fmtSec(end)})`, fmt: `clip:${start}:${end}`, type: 'video' });
            }
            return list;
        },
    },
    soundcloud: {
        name: 'SoundCloud', color: '#FF5500',
        hosts: ['soundcloud.com'],
        isPage() {
            const p = location.pathname.split('/').filter(Boolean);
            const skip = new Set(['discover','stream','charts','upload','messages',
                                   'notifications','you','signin','login','search','pages']);
            return p.length >= 2 && !skip.has(p[0]);
        },
        findBar: () => null,
        getTitle() {
            const el = document.querySelector('.soundTitle__title span')
                    || document.querySelector('h1[class*="soundTitle"]');
            return el ? el.textContent.trim()
                      : document.title.replace(' | SoundCloud', '').trim();
        },
        inline: false,
        formats: [{ label: '🎵 MP3 (En İyi)', fmt: 'audio', type: 'audio' }],
    },
    spotify: {
        name: 'Spotify', color: '#1DB954',
        hosts: ['open.spotify.com'],
        isPage: () => /\/(track|album|playlist)\//.test(location.pathname),
        findBar: () => null,
        getTitle() {
            const el = document.querySelector('[data-testid="context-item-link"]')
                    || document.querySelector('h1');
            return el ? el.textContent.trim()
                      : document.title.replace(' - Spotify', '').trim();
        },
        inline: false,
        formats: [{ label: '🎵 MP3 320kbps', fmt: 'audio', type: 'audio' }],
    },
    youtubeMusic: {
        name: 'YouTube Music', color: '#FF0000',
        hosts: ['music.youtube.com'],
        isPage: () => location.pathname.startsWith('/watch'),
        findBar: () => null,
        getTitle() {
            const el = document.querySelector('yt-formatted-string.title')
                    || document.querySelector('.ytmusic-player-bar .title');
            return el ? el.textContent.trim()
                      : document.title.replace(' - YouTube Music', '').trim();
        },
        inline: false,
        formats: [
            { label: '🎵 MP3 En İyi Kalite', fmt: 'audio', type: 'audio' },
            { label: '🎥 Video İndir',        fmt: 'best',  type: 'video' },
        ],
    },
    bandcamp: {
        name: 'Bandcamp', color: '#1DA0C3',
        hostsRegex: /\.bandcamp\.com$/,
        isPage: () => /\/(track|album)\//.test(location.pathname),
        findBar: () => null,
        getTitle() {
            const el = document.querySelector('h2.trackTitle')
                    || document.querySelector('.trackTitle');
            return el ? el.textContent.trim() : document.title;
        },
        inline: false,
        formats: [{ label: '🎵 MP3', fmt: 'audio', type: 'audio' }],
    },
    tiktok: {
        name: 'TikTok', color: '#EE1D52',
        hosts: ['www.tiktok.com'],
        isPage: () => /@[^/]+\/video\//.test(location.pathname),
        findBar: () => null,
        getTitle() {
            const el = document.querySelector('[data-e2e="browse-video-desc"]')
                    || document.querySelector('[class*="VideoDescription"]');
            return el ? el.textContent.trim().slice(0, 100) : 'TikTok Video';
        },
        inline: false,
        formats: [
            { label: '🎬 Video',     fmt: 'best',  type: 'video' },
            { label: '🎵 Ses (MP3)', fmt: 'audio', type: 'audio' },
        ],
    },
    instagram: {
        name: 'Instagram', color: '#E1306C',
        hosts: ['www.instagram.com'],
        isPage: () => /^\/(p|reel|tv|stories)\//.test(location.pathname),
        findBar: () => null,
        getTitle: () => document.title.replace(' • Instagram', '').trim() || 'Instagram Media',
        inline: false,
        formats: [
            { label: '🎬 Video / Fotoğraf', fmt: 'best',  type: 'video' },
            { label: '🎵 Ses (MP3)',         fmt: 'audio', type: 'audio' },
        ],
    },
    twitter: {
        name: 'Twitter / X', color: '#1DA1F2',
        hosts: ['twitter.com', 'x.com'],
        isPage: () => /\/status\/\d+/.test(location.pathname),
        findBar: () => null,
        getTitle() {
            const el = document.querySelector('[data-testid="tweetText"]');
            return el ? el.textContent.trim().slice(0, 100) : 'Tweet Video';
        },
        inline: false,
        formats: [
            { label: '🎬 Video',     fmt: 'best',  type: 'video' },
            { label: '🎵 Ses (MP3)', fmt: 'audio', type: 'audio' },
        ],
    },
    vimeo: {
        name: 'Vimeo', color: '#1AB7EA',
        hosts: ['vimeo.com'],
        isPage: () => /^\/\d+/.test(location.pathname),
        findBar: () => null,
        getTitle: () => document.title.replace(' on Vimeo', '').trim(),
        inline: false,
        formats: [
            { label: '🎬 En İyi Kalite', fmt: 'best',  type: 'video' },
            { label: '📺 1080p',         fmt: '1080p', type: 'video' },
            { label: '📺 720p',          fmt: '720p',  type: 'video' },
            { label: '🎵 Ses (MP3)',     fmt: 'audio', type: 'audio' },
        ],
    },
    dailymotion: {
        name: 'Dailymotion', color: '#0066DC',
        hosts: ['www.dailymotion.com'],
        isPage: () => location.pathname.startsWith('/video/'),
        findBar: () => null,
        getTitle: () => document.title.replace(' - Dailymotion Video', '').trim(),
        inline: false,
        formats: [
            { label: '🎬 En İyi Kalite', fmt: 'best',  type: 'video' },
            { label: '📺 720p',          fmt: '720p',  type: 'video' },
            { label: '🎵 Ses (MP3)',     fmt: 'audio', type: 'audio' },
        ],
    },
    twitch: {
        name: 'Twitch', color: '#9146FF',
        hosts: ['www.twitch.tv', 'clips.twitch.tv'],
        isPage() {
            return /\/videos\/\d+/.test(location.pathname)
                || /^\/[^/]+\/clip\//.test(location.pathname)
                || location.hostname === 'clips.twitch.tv';
        },
        findBar: () => null,
        getTitle: () => document.title.replace(' - Twitch', '').trim(),
        inline: false,
        formats: [
            { label: '🎬 En İyi Kalite', fmt: 'best',  type: 'video' },
            { label: '📺 720p',          fmt: '720p',  type: 'video' },
            { label: '🎵 Ses (MP3)',     fmt: 'audio', type: 'audio' },
        ],
    },
    reddit: {
        name: 'Reddit', color: '#FF4500',
        hosts: ['www.reddit.com', 'old.reddit.com'],
        isPage: () => /\/comments\//.test(location.pathname),
        findBar: () => null,
        getTitle() {
            const el = document.querySelector('h1[id]')
                    || document.querySelector('[data-testid="post-content"] h1')
                    || document.querySelector('shreddit-post h1');
            return el ? el.textContent.trim() : document.title;
        },
        inline: false,
        formats: [
            { label: '🎬 Video',     fmt: 'best',  type: 'video' },
            { label: '🎵 Ses (MP3)', fmt: 'audio', type: 'audio' },
        ],
    },
};

// ─── Platform Detection ───────────────────────────────────────────────────────

function detectPlatform() {
    const host = location.hostname;
    for (const p of Object.values(PLATFORMS)) {
        if (p.hosts?.includes(host)) return p;
        if (p.hostsRegex?.test(host)) return p;
    }
    return null;
}

// ─── DOM-Based Direct URL Extraction ─────────────────────────────────────────
// Extracts a direct downloadable media URL from the current page without
// needing the desktop application.

function extractDirectUrl(platform) {
    const name = platform.name;

    // ── Twitter / X ──────────────────────────────────────────────────────────
    if (name === 'Twitter / X') {
        // Try og:video meta (available for public tweets with video)
        const og = document.querySelector('meta[property="og:video:url"]')
                || document.querySelector('meta[property="og:video"]');
        if (og?.content?.startsWith('http')) return { url: og.content, ext: 'mp4' };

        // Try player:stream in scripts (Twitter embeds stream URL in page JSON)
        for (const s of document.querySelectorAll('script')) {
            const t = s.textContent;
            if (!t.includes('video/mp4') && !t.includes('.mp4')) continue;
            const m = t.match(/"content_type"\s*:\s*"video\/mp4"[^}]*"url"\s*:\s*"([^"]+)"/)
                   || t.match(/"url"\s*:\s*"(https:\/\/[^"]+\.mp4[^"]*)"/);
            if (m) return { url: m[1].replace(/\\u002F/g, '/').replace(/\\/g, ''), ext: 'mp4' };
        }
        return null;
    }

    // ── Instagram ─────────────────────────────────────────────────────────────
    if (name === 'Instagram') {
        const og = document.querySelector('meta[property="og:video"]')
                || document.querySelector('meta[property="og:video:url"]');
        if (og?.content?.startsWith('http')) return { url: og.content, ext: 'mp4' };

        // JSON-LD
        for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
            try {
                const data = JSON.parse(s.textContent);
                const url = data?.video?.contentUrl || data?.contentUrl;
                if (url) return { url, ext: 'mp4' };
            } catch {}
        }
        return null;
    }

    // ── TikTok ────────────────────────────────────────────────────────────────
    if (name === 'TikTok') {
        // __NEXT_DATA__ (new TikTok)
        try {
            const nd = document.getElementById('__NEXT_DATA__');
            if (nd) {
                const data = JSON.parse(nd.textContent);
                const v = data?.props?.pageProps?.itemInfo?.itemStruct?.video
                       || data?.props?.pageProps?.videoData?.itemInfo?.itemStruct?.video;
                const url = v?.downloadAddr || v?.playAddr;
                if (url) return { url, ext: 'mp4' };
            }
        } catch {}

        // SIGI_STATE (older TikTok)
        try {
            const ss = document.getElementById('SIGI_STATE');
            if (ss) {
                const data = JSON.parse(ss.textContent);
                const items = Object.values(data?.ItemModule || {});
                const url = items[0]?.video?.downloadAddr || items[0]?.video?.playAddr;
                if (url) return { url, ext: 'mp4' };
            }
        } catch {}

        // og:video fallback
        const og = document.querySelector('meta[property="og:video"]');
        if (og?.content) return { url: og.content, ext: 'mp4' };
        return null;
    }

    // ── Reddit ────────────────────────────────────────────────────────────────
    if (name === 'Reddit') {
        // shreddit-player has src
        const player = document.querySelector('shreddit-player');
        if (player?.getAttribute('src')) return { url: player.getAttribute('src'), ext: 'mp4' };

        // Old Reddit / JSON-LD
        for (const s of document.querySelectorAll('script')) {
            const t = s.textContent;
            if (!t.includes('fallback_url') && !t.includes('v.redd.it')) continue;
            const m = t.match(/"fallback_url"\s*:\s*"([^"]+\.mp4[^"]*)"/);
            if (m) return { url: m[1].replace(/\\u002F/g, '/').replace(/\\/g, ''), ext: 'mp4' };
        }

        const og = document.querySelector('meta[property="og:video:url"]')
                || document.querySelector('meta[property="og:video"]');
        if (og?.content?.includes('v.redd.it') || og?.content?.includes('.mp4')) {
            return { url: og.content, ext: 'mp4' };
        }
        return null;
    }

    // ── Vimeo ─────────────────────────────────────────────────────────────────
    if (name === 'Vimeo') {
        // og:video usually points to embed, not direct
        // Try JSON-LD first
        for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
            try {
                const data = JSON.parse(s.textContent);
                const url = data?.contentUrl || data?.embedUrl;
                if (url?.includes('.mp4') || url?.includes('vimeocdn')) return { url, ext: 'mp4' };
            } catch {}
        }
        // Background will handle Vimeo via player config API
        return { needsFetch: true, platform: 'vimeo', videoId: location.pathname.split('/')[1] };
    }

    // ── Dailymotion ───────────────────────────────────────────────────────────
    if (name === 'Dailymotion') {
        const og = document.querySelector('meta[property="og:video:url"]')
                || document.querySelector('meta[property="og:video"]');
        if (og?.content?.startsWith('http')) return { url: og.content, ext: 'mp4' };
        const videoId = location.pathname.split('/')[2];
        if (videoId) return { needsFetch: true, platform: 'dailymotion', videoId };
        return null;
    }

    // ── Bandcamp ──────────────────────────────────────────────────────────────
    if (name === 'Bandcamp') {
        // data-tralbum attribute contains track info
        const tralbum = document.querySelector('[data-tralbum]');
        if (tralbum) {
            try {
                const data = JSON.parse(tralbum.getAttribute('data-tralbum'));
                const url = data?.trackinfo?.[0]?.file?.['mp3-128'];
                if (url) return { url: url.startsWith('//') ? 'https:' + url : url, ext: 'mp3' };
            } catch {}
        }
        // Also try inline scripts
        for (const s of document.querySelectorAll('script')) {
            const m = s.textContent.match(/"mp3-128"\s*:\s*"([^"]+)"/);
            if (m) return { url: m[1].replace(/\\\//g, '/'), ext: 'mp3' };
        }
        return null;
    }

    return null;
}

// ─── Last-format Memory ───────────────────────────────────────────────────────

function getLastFmt(platformName) {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || '{}')[platformName] || null; }
    catch { return null; }
}

function setLastFmt(platformName, fmt) {
    try {
        const d = JSON.parse(localStorage.getItem(STORE_KEY) || '{}');
        d[platformName] = fmt;
        localStorage.setItem(STORE_KEY, JSON.stringify(d));
    } catch {}
}

// ─── Floating Button ──────────────────────────────────────────────────────────

function createFloatingBtn(platform) {
    if (document.getElementById(FLOAT_ID)) return document.getElementById(FLOAT_ID);
    const btn = document.createElement('button');
    btn.id = FLOAT_ID;
    btn.title = `${platform.name} — İndir  (Alt+D)`;
    btn.style.cssText = `
        position: fixed; bottom: 24px; right: 24px; z-index: 2147483647;
        width: 48px; height: 48px; border-radius: 50%;
        background: ${platform.color}; border: none; cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 4px 16px rgba(0,0,0,0.45);
        transition: transform 0.15s, box-shadow 0.15s; outline: none;
    `;
    btn.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="white">
        <path d="M17 18v1H6v-1h11zm-.5-6.6-.7-.7-3.8 3.7V4h-1v10.4l-3.8-3.8-.7.7 5 5 5-4.9z"/>
    </svg>`;
    btn.addEventListener('mouseenter', () => {
        btn.style.transform = 'scale(1.12)';
        btn.style.boxShadow = '0 6px 24px rgba(0,0,0,0.55)';
    });
    btn.addEventListener('mouseleave', () => {
        btn.style.transform = 'scale(1)';
        btn.style.boxShadow = '0 4px 16px rgba(0,0,0,0.45)';
    });
    btn.addEventListener('click', e => { e.stopPropagation(); toggleMenu(btn, platform); });
    document.body.appendChild(btn);
    return btn;
}

// ─── Inline Button (YouTube style) ───────────────────────────────────────────

function createInlineBtn(platform) {
    const btn = document.createElement('button');
    btn.id = BTN_ID;
    btn.title = `${platform.name} İndirici  (Alt+D)`;
    btn.style.cssText = `
        display: inline-flex; align-items: center; gap: 6px;
        background: none; border: none; cursor: pointer;
        color: inherit; font-size: 14px; font-weight: 500;
        padding: 0 16px; height: 36px; border-radius: 18px;
        transition: background 0.15s; outline: none;
    `;
    btn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M17 18v1H6v-1h11zm-.5-6.6-.7-.7-3.8 3.7V4h-1v10.4l-3.8-3.8-.7.7 5 5 5-4.9z"/>
        </svg>
        <span>İndir</span>
    `;
    btn.addEventListener('mouseenter', () => btn.style.background = 'rgba(255,255,255,0.1)');
    btn.addEventListener('mouseleave', () => btn.style.background = 'none');
    btn.addEventListener('click', e => { e.stopPropagation(); toggleMenu(btn, platform); });
    return btn;
}

// ─── Menu ─────────────────────────────────────────────────────────────────────

function removeMenu() {
    const m = document.getElementById(MENU_ID);
    if (m?._scrollCleanup) m._scrollCleanup();
    m?.remove();
}

function buildMenu(anchorEl, platform) {
    removeMenu();
    const url     = location.href;
    const title   = platform.getTitle();
    const lastFmt = getLastFmt(platform.name);
    const needsApp = NEEDS_APP.has(platform.name);

    const menu = document.createElement('div');
    menu.id = MENU_ID;
    menu.style.cssText = `
        position: fixed; z-index: 2147483647;
        background: #1e1e1e; color: #fff; border-radius: 12px; overflow: hidden;
        box-shadow: 0 4px 32px rgba(0,0,0,0.65); min-width: 220px;
        font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
        border: 1px solid rgba(255,255,255,0.09);
    `;

    // Header
    const header = document.createElement('div');
    header.style.cssText = `padding:12px 16px;font-weight:600;font-size:13px;
        border-bottom:1px solid rgba(255,255,255,0.09);display:flex;align-items:center;gap:8px;`;
    const dot = document.createElement('span');
    dot.style.cssText = `width:8px;height:8px;border-radius:50%;background:${platform.color};display:inline-block;flex-shrink:0;`;
    header.append(dot, `${platform.name} — Format Seç`);
    menu.appendChild(header);

    // Title preview
    if (title) {
        const tEl = document.createElement('div');
        tEl.style.cssText = 'padding:8px 16px 4px;font-size:11px;color:#888;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:280px;';
        tEl.textContent = title.slice(0, 65) + (title.length > 65 ? '…' : '');
        menu.appendChild(tEl);
    }

    // Duration (YouTube only — other platforms could add getDuration too)
    if (platform.getDuration) {
        const dur = platform.getDuration();
        if (dur) {
            const durEl = document.createElement('div');
            durEl.style.cssText = 'padding:0 16px 8px;font-size:11px;color:#666;';
            durEl.textContent = `⏱ ${dur}`;
            menu.appendChild(durEl);
        }
    }

    // Format items — use getFormats() if available (e.g. YouTube dynamic), else static formats
    const formats = platform.getFormats ? platform.getFormats() : platform.formats;
    for (const { label, fmt, type } of formats) {
        const isLast = fmt === lastFmt;
        const item = document.createElement('div');
        item.style.cssText = `padding:10px 16px;cursor:pointer;font-size:13px;
            transition:background 0.1s;display:flex;align-items:center;justify-content:space-between;
            ${isLast ? 'background:rgba(255,255,255,0.05);' : ''}`;
        item.innerHTML = `<span>${label}</span>${isLast ? '<span style="font-size:10px;color:#555;margin-left:6px">son</span>' : ''}`;
        item.addEventListener('mouseenter', () => item.style.background = '#333');
        item.addEventListener('mouseleave', () => { item.style.background = isLast ? 'rgba(255,255,255,0.05)' : 'transparent'; });
        item.addEventListener('click', () => {
            removeMenu();
            setLastFmt(platform.name, fmt);
            sendDownload(url, fmt, type, title, platform);
        });
        menu.appendChild(item);
    }

    // Status line
    const status = document.createElement('div');
    status.style.cssText = 'padding:8px 16px;font-size:11px;color:#888;border-top:1px solid rgba(255,255,255,0.08);display:flex;align-items:center;gap:6px;';

    if (DRM_PLATFORMS.has(platform.name)) {
        status.innerHTML = '<span style="color:#ff6b6b">⛔ DRM korumalı — indirilemez</span>';
    } else if (platform.name === 'Spotify') {
        status.innerHTML = '<span style="color:#1DB954">🎵 Spotify — masaüstü uygulaması gerekli</span>';
    } else if (needsApp) {
        status.innerHTML = '<span style="color:#f0ad4e">⚠ Bu platform için masaüstü uygulaması gerekli</span>';
        // Also check if app is running
        fetch(`${API}/ping`).then(r => r.json()).then(() => {
            status.innerHTML = '<span style="color:#00cc6a">✓ Uygulama bağlı</span>';
        }).catch(() => {
            status.innerHTML = '<span style="color:#ff6b6b">✗ Uygulama kapalı — önce başlat</span>';
        });
    } else {
        status.innerHTML = '<span style="color:#00cc6a">✓ Bağımsız indirme — uygulama gerekmez</span>';
    }
    menu.appendChild(status);

    document.body.appendChild(menu);

    // Position
    const r = anchorEl.getBoundingClientRect();
    let top  = r.bottom + 8;
    let left = r.left;
    if (left + 248 > window.innerWidth)  left = window.innerWidth - 256;
    if (top  + 280 > window.innerHeight) top  = r.top - 290;
    menu.style.top  = `${Math.max(4, top)}px`;
    menu.style.left = `${Math.max(4, left)}px`;

    // Close on outside click
    setTimeout(() => document.addEventListener('click', removeMenu, { once: true }), 50);

    // Close on scroll — prevents menu floating away from anchor
    const onScroll = () => removeMenu();
    window.addEventListener('scroll', onScroll, { once: true, passive: true });
    menu._scrollCleanup = () => window.removeEventListener('scroll', onScroll);
}

function toggleMenu(anchorEl, platform) {
    if (document.getElementById(MENU_ID)) { removeMenu(); return; }
    buildMenu(anchorEl, platform);
}

// ─── Download Dispatch ────────────────────────────────────────────────────────

async function sendDownload(videoUrl, format, formatType, videoTitle, platform) {
    const name = platform.name;

    // Hard DRM platforms — block immediately
    if (DRM_PLATFORMS.has(name)) {
        showToast(`⛔ ${name} DRM korumalı — indirilemez`, true);
        return;
    }

    // Handle subtitle download special format
    const writeSubs = (format === 'best_subs');
    if (writeSubs) format = 'best';

    // Handle timestamp clip: 'clip:start:end'
    let clipStart = null, clipEnd = null;
    if (format && format.startsWith('clip:')) {
        const parts = format.split(':');
        clipStart = parseInt(parts[1]) || 0;
        clipEnd   = parseInt(parts[2]) || null;
        format = 'best';
    }

    // ── Standalone path (no app needed) ─────────────────────────────────────
    if (!NEEDS_APP.has(name)) {
        const info = extractDirectUrl(platform);

        if (info && !info.needsFetch && info.url) {
            // Direct URL found in DOM — hand off to background for chrome.downloads
            chrome.runtime.sendMessage({
                action: 'download_direct',
                url: info.url,
                ext: info.ext || 'mp4',
                title: videoTitle,
                mimeHint: info.mimeType,
            });
            showToast(`⬇ "${videoTitle.slice(0, 40)}" indiriliyor…`);
            return;
        }

        if (info?.needsFetch) {
            // Background needs to fetch and resolve the URL (e.g., Vimeo player config)
            chrome.runtime.sendMessage({
                action: 'download_fetch',
                platform: info.platform,
                videoId: info.videoId,
                format,
                title: videoTitle,
            });
            showToast(`⬇ "${videoTitle.slice(0, 40)}" çözülüyor…`);
            return;
        }

        // Extraction failed — try Flask API as fallback
        showToast('⚠ Doğrudan URL bulunamadı, uygulama deneniyor…', false);
    }

    // ── Flask API path (YouTube, SoundCloud, Twitch, Spotify, or fallback) ───
    try {
        const pingRes = await fetch(`${API}/ping`, { signal: AbortSignal.timeout(2000) });
        const { token } = await pingRes.json();
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['X-API-Key'] = token;

        const res = await fetch(`${API}/download`, {
            method: 'POST', headers,
            body: JSON.stringify({ videoUrl, format, formatType, videoTitle, writeSubs,
                                   startTime: clipStart, endTime: clipEnd }),
        });

        if (res.ok) {
            showToast(`✓ "${videoTitle.slice(0, 40)}" kuyruğa eklendi`);
        } else {
            const err = await res.text();
            showToast(`✗ Hata: ${err.slice(0, 80)}`, true);
        }
    } catch {
        if (NEEDS_APP.has(name)) {
            showToast(`✗ ${name} için masaüstü uygulaması gerekli. Lütfen başlatın.`, true);
        } else {
            showToast('✗ İndirme başarısız. Sayfayı yenileyip tekrar deneyin.', true);
        }
    }
}

// ─── Toast ────────────────────────────────────────────────────────────────────

function showToast(msg, isError = false) {
    const t = document.createElement('div');
    t.style.cssText = `
        position: fixed; bottom: 84px; right: 24px; z-index: 2147483647;
        background: ${isError ? '#c0392b' : '#1a1a1a'};
        border-left: 3px solid ${isError ? '#e74c3c' : '#00cc6a'};
        color: white; padding: 12px 20px; border-radius: 6px;
        font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
        font-size: 13px; font-weight: 500;
        box-shadow: 0 4px 16px rgba(0,0,0,0.5); max-width: 380px;
        transition: opacity 0.3s; opacity: 1;
    `;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 4000);
}

// ─── Injection ────────────────────────────────────────────────────────────────

function inject() {
    const platform = detectPlatform();
    if (!platform || !platform.isPage()) {
        document.getElementById(FLOAT_ID)?.remove();
        return false;
    }
    if (platform.inline) {
        if (document.getElementById(BTN_ID)) return true;

        // Insert BEFORE the like button (first child of the buttons row)
        // #top-level-buttons-computed contains like/dislike as first element
        const buttonsRow = document.querySelector('#top-level-buttons-computed')
                        || platform.findBar();
        if (!buttonsRow) return false;

        const btn = createInlineBtn(platform);
        buttonsRow.insertBefore(btn, buttonsRow.firstElementChild);
    } else {
        createFloatingBtn(platform);
    }
    return true;
}

function tryInject(retries = 20, delay = 500) {
    if (inject()) return;
    if (retries > 0) setTimeout(() => tryInject(retries - 1, delay), delay);
}

function cleanup() {
    document.getElementById(BTN_ID)?.remove();
    document.getElementById(FLOAT_ID)?.remove();
    removeMenu();
}

// ─── Init ─────────────────────────────────────────────────────────────────────

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => tryInject());
} else {
    tryInject();
}

// MutationObserver for SPA navigation (all platforms)
let _lastUrl = location.href;
new MutationObserver(() => {
    if (location.href !== _lastUrl) {
        _lastUrl = location.href;
        cleanup();
        setTimeout(() => tryInject(), 1000);
    }
}).observe(document, { subtree: true, childList: true });

// YouTube-specific nav events — more reliable than MutationObserver
// Fires after YouTube's SPA navigation completes and DOM is ready
document.addEventListener('yt-navigate-finish', () => {
    cleanup();
    tryInject(20, 400);
});
document.addEventListener('yt-page-data-updated', () => {
    if (!document.getElementById(BTN_ID) && !document.getElementById(FLOAT_ID)) {
        tryInject(15, 300);
    }
});

document.addEventListener('keydown', e => {
    if (!e.altKey || e.key.toLowerCase() !== 'd') return;
    e.preventDefault();

    // Alt+Shift+D — quick download with last used format (no menu)
    if (e.shiftKey) {
        const platform = detectPlatform();
        if (!platform || !platform.isPage()) return;
        const formats = platform.getFormats ? platform.getFormats() : platform.formats;
        const lastFmt = getLastFmt(platform.name);
        const chosen = (lastFmt && formats.find(f => f.fmt === lastFmt)) || formats[0];
        if (chosen) {
            showToast(`⚡ Hızlı indirme: ${chosen.label}`);
            sendDownload(location.href, chosen.fmt, chosen.type, platform.getTitle(), platform);
        }
        return;
    }

    // Alt+D — toggle format menu
    const btn = document.getElementById(BTN_ID) || document.getElementById(FLOAT_ID);
    if (btn) btn.click();
});
