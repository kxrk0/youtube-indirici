// content.js

// Konsola bilgi mesajı
console.log("YouTube Downloader Companion: Eklenti yüklendi");

// YouTube API'sinden video bilgilerini almak için yardımcı fonksiyon
async function getVideoDetails() {
    // YouTube'un kendi video bilgilerini içeren script etiketini bulalım
    const ytInitialPlayerResponse = document.body.innerHTML.match(/ytInitialPlayerResponse\s*=\s*({.+?});/)?.[1];
    
    if (ytInitialPlayerResponse) {
        try {
            const data = JSON.parse(ytInitialPlayerResponse);
            const videoDetails = data.videoDetails;
            const streamingData = data.streamingData;
            
            // Mevcut formatları alalım
            const formats = [];
            
            // Adaptive formatlar (video ve ses ayrı)
            if (streamingData && streamingData.adaptiveFormats) {
                streamingData.adaptiveFormats.forEach(format => {
                    if (format.mimeType.includes('video/')) {
                        const quality = format.qualityLabel;
                        // Eğer bu kalite daha önce eklenmemişse ekleyelim
                        if (!formats.find(f => f.quality === quality)) {
                            formats.push({
                                quality: quality,
                                mimeType: format.mimeType.split(';')[0],
                                type: 'video'
                            });
                        }
                    }
                });
            }
            
            // MP3 seçeneğini her zaman ekleyelim
            formats.push({
                quality: 'Audio Only',
                mimeType: 'audio/mp3',
                type: 'audio'
            });
            
            // Kalite etiketine göre sıralayalım (en yüksek kaliteden en düşüğe)
            formats.sort((a, b) => {
                if (a.type !== b.type) {
                    return a.type === 'video' ? -1 : 1;
                }
                
                if (a.quality === 'Audio Only') return 1;
                if (b.quality === 'Audio Only') return -1;
                
                const aNum = parseInt(a.quality) || 0;
                const bNum = parseInt(b.quality) || 0;
                return bNum - aNum;
            });
            
            return {
                title: videoDetails.title,
                videoId: videoDetails.videoId,
                formats: formats
            };
        } catch (error) {
            console.error('Video detayları alınırken hata oluştu:', error);
        }
    }
    
    // Eğer video detayları alınamazsa varsayılan formatları döndürelim
    return {
        title: document.title.replace(' - YouTube', ''),
        videoId: getYouTubeVideoId(),
        formats: [
            { quality: '1080p', mimeType: 'video/mp4', type: 'video' },
            { quality: '720p', mimeType: 'video/mp4', type: 'video' },
            { quality: '480p', mimeType: 'video/mp4', type: 'video' },
            { quality: '360p', mimeType: 'video/mp4', type: 'video' },
            { quality: 'Audio Only', mimeType: 'audio/mp3', type: 'audio' }
        ]
    };
}

function getYouTubeVideoId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('v');
}

function isYouTubeDarkTheme() {
    return document.documentElement.getAttribute('dark') === 'true';
}

function createDownloadButton() {
    // YouTube'un kendi butonlarının stilini birebir taklit edelim
    const button = document.createElement('button');
    button.id = 'youtube-downloader-btn';
    button.className = 'yt-spec-button-shape-next yt-spec-button-shape-next--tonal yt-spec-button-shape-next--mono yt-spec-button-shape-next--size-m yt-spec-button-shape-next--icon-leading yt-spec-button-shape-next--enable-backdrop-filter-experiment';
    button.setAttribute('aria-label', 'İndir');
    
    // SVG ikonu doğrudan içeri yerleştirelim - YouTube'un kendi SVG'sini kullanıyoruz
    const iconColor = isYouTubeDarkTheme() ? '#fff' : 'currentcolor';
    
    button.innerHTML = `
        <div aria-hidden="true" class="yt-spec-button-shape-next__icon">
            <span class="ytIconWrapperHost" style="width: 24px; height: 24px;">
                <span class="yt-icon-shape yt-spec-icon-shape">
                    <div style="width: 100%; height: 100%; display: block; fill: ${iconColor};">
                        <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24" focusable="false" aria-hidden="true" style="pointer-events: none; display: inherit; width: 100%; height: 100%;">
                            <path d="M17 18v1H6v-1h11zm-.5-6.6-.7-.7-3.8 3.7V4h-1v10.4l-3.8-3.8-.7.7 5 5 5-4.9z"></path>
                        </svg>
                    </div>
                </span>
            </span>
        </div>
        <div class="yt-spec-button-shape-next__button-text-content">
            <span class="yt-core-attributed-string yt-core-attributed-string--white-space-no-wrap" role="text">İndir</span>
        </div>
        <yt-touch-feedback-shape style="border-radius: inherit;">
            <div aria-hidden="true" class="yt-spec-touch-feedback-shape yt-spec-touch-feedback-shape--touch-response">
                <div class="yt-spec-touch-feedback-shape__stroke"></div>
                <div class="yt-spec-touch-feedback-shape__fill"></div>
            </div>
        </yt-touch-feedback-shape>
    `;
    
    button.addEventListener('click', toggleDropdown);
    return button;
}

async function createDropdownMenu() {
    const menu = document.createElement('div');
    menu.id = 'youtube-downloader-menu';
    menu.className = 'ytd-custom-dropdown';
    
    // Koyu/aydınlık tema kontrolü
    const isDarkTheme = isYouTubeDarkTheme();
    menu.style.backgroundColor = isDarkTheme ? '#282828' : '#ffffff';
    menu.style.color = isDarkTheme ? '#ffffff' : '#0f0f0f';
    menu.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.3)';

    const header = document.createElement('div');
    header.className = 'dropdown-header';
    header.textContent = 'Format Seçin';
    header.style.borderBottom = isDarkTheme ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)';
    menu.appendChild(header);
    
    // Yükleniyor göstergesi
    const loadingDiv = document.createElement('div');
    loadingDiv.textContent = 'Formatlar yükleniyor...';
    loadingDiv.style.padding = '12px 16px';
    menu.appendChild(loadingDiv);
    
    // Video detaylarını alalım
    const videoDetails = await getVideoDetails();
    
    // Yükleniyor göstergesini kaldıralım
    menu.removeChild(loadingDiv);
    
    videoDetails.formats.forEach(format => {
        const item = document.createElement('div');
        item.className = 'dropdown-item';
        
        const formatLabel = document.createElement('span');
        formatLabel.className = 'format-label';
        formatLabel.textContent = format.quality;
        
        const formatInfo = document.createElement('span');
        formatInfo.className = 'format-info';
        formatInfo.textContent = format.type === 'video' ? 'MP4' : 'MP3';
        
        item.appendChild(formatLabel);
        item.appendChild(formatInfo);
        
        // Koyu/aydınlık tema için hover efekti
        item.addEventListener('mouseover', () => {
            item.style.backgroundColor = isDarkTheme ? '#3f3f3f' : '#f2f2f2';
        });
        
        item.addEventListener('mouseout', () => {
            item.style.backgroundColor = 'transparent';
        });
        
        item.addEventListener('click', (e) => {
            e.preventDefault();
            selectFormat(format, videoDetails.videoId, videoDetails.title);
        });
        
        menu.appendChild(item);
    });

    return menu;
}

function toggleDropdown(event) {
    event.stopPropagation();
    
    // Eğer menü zaten varsa, göster/gizle
    let menu = document.getElementById('youtube-downloader-menu');
    
    if (menu) {
        if (menu.style.display === 'block') {
            menu.style.display = 'none';
        } else {
            menu.style.display = 'block';
        }
    } else {
        // Menü henüz oluşturulmamışsa, oluşturup gösterelim
        createDropdownMenu().then(newMenu => {
            // Butonun konumunu al
            const button = document.getElementById('youtube-downloader-btn');
            const buttonRect = button.getBoundingClientRect();
            
            // Menüyü butonun altına yerleştir
            newMenu.style.position = 'fixed';
            newMenu.style.top = `${buttonRect.bottom}px`;
            newMenu.style.left = `${buttonRect.left}px`;
            newMenu.style.zIndex = '9999';
            newMenu.style.display = 'block';
            
            document.body.appendChild(newMenu);
        });
    }
}

function selectFormat(format, videoId, videoTitle) {
    const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
    
    console.log(`Selected: ${format.quality} (${format.mimeType}) for video: ${videoTitle}`);

    chrome.runtime.sendMessage({
        action: 'download',
        videoUrl: videoUrl,
        format: format.quality,
        formatType: format.type,
        videoTitle: videoTitle
    }, response => {
        if (chrome.runtime.lastError) {
            console.error(chrome.runtime.lastError.message);
            alert(`Hata: ${chrome.runtime.lastError.message}`);
        } else if (response && response.status === 'success') {
            console.log(response.status);
            const formatText = format.type === 'video' ? `${format.quality} MP4` : 'MP3';
            alert(`İndirme başlatıldı: ${videoTitle}\nFormat: ${formatText}\n\nİndirme işlemi Python uygulaması üzerinden gerçekleştirilecek.`);
        } else {
            console.error(response ? response.message : 'Bilinmeyen hata');
            alert('İndirme başlatılamadı. Python uygulamasının çalıştığından emin olun.');
        }
    });

    // Menüyü kapatalım
    const menu = document.getElementById('youtube-downloader-menu');
    if (menu) {
        menu.style.display = 'none';
    }
}

// DOM'dan buton kapsayıcılarını bulmak için tüm olası seçicileri deneyen fonksiyon
function findButtonContainer() {
    // Ekran görüntüsünden gördüğümüz butonların olduğu kapsayıcıları deneyelim
    const selectors = [
        // Yeni ekran görüntüsünden gördüğümüz butonlar
        'div:has(button[aria-label="Paylaş"])',
        'div:has(button[aria-label="Teşekkürler"])',
        'div:has(button[aria-label="Klip"])',
        'div:has(button[aria-label="Kaydet"])',
        // Diğer olası kapsayıcılar
        '#actions-inner',
        '#actions',
        '#top-level-buttons-computed',
        '#flexible-item-buttons',
        'ytd-menu-renderer[class*="ytd-video-primary-info-renderer"]',
        '.ytd-menu-renderer',
        // Genel buton kapsayıcıları
        'div[class*="buttons"]'
    ];
    
    // Her seçiciyi deneyelim
    for (const selector of selectors) {
        try {
            const container = document.querySelector(selector);
            if (container) {
                console.log(`YouTube Downloader Companion: Buton kapsayıcısı bulundu: ${selector}`);
                return container;
            }
        } catch (e) {
            // Bazı seçiciler tarayıcı tarafından desteklenmeyebilir, hataları görmezden gelelim
            console.log(`Seçici hata verdi: ${selector}`, e);
        }
    }
    
    // Hiçbir kapsayıcı bulunamadıysa, DOM'u manuel olarak tarayalım
    console.log("YouTube Downloader Companion: Standart seçicilerle buton kapsayıcısı bulunamadı, DOM taranıyor...");
    
    // Klip, Kaydet veya Teşekkürler butonlarını bulalım ve onların ebeveynini alalım
    const buttonLabels = ["Klip", "Kaydet", "Teşekkürler", "Paylaş"];
    for (const label of buttonLabels) {
        const buttons = Array.from(document.querySelectorAll('button'));
        const button = buttons.find(btn => btn.getAttribute('aria-label') === label);
        
        if (button) {
            // Butonun ebeveynini bulalım (kapsayıcı olabilir)
            let parent = button.parentElement;
            
            // Ebeveynin ebeveynini de kontrol edelim (genellikle asıl kapsayıcı)
            while (parent) {
                if (parent.tagName === 'YT-BUTTON-RENDERER' || 
                    parent.tagName === 'YTD-BUTTON-RENDERER' ||
                    parent.tagName === 'YTD-TOGGLE-BUTTON-RENDERER' ||
                    parent.id === 'actions' || 
                    parent.id === 'actions-inner' || 
                    parent.className.includes('buttons')) {
                    console.log(`YouTube Downloader Companion: "${label}" butonu üzerinden kapsayıcı bulundu: ${parent.tagName || parent.id || parent.className}`);
                    return parent;
                }
                parent = parent.parentElement;
            }
        }
    }
    
    // Son çare olarak, video bilgilerinin olduğu bölümü bulmaya çalışalım
    const videoInfo = document.querySelector('ytd-video-primary-info-renderer');
    if (videoInfo) {
        console.log("YouTube Downloader Companion: Video bilgileri bölümü bulundu");
        return videoInfo;
    }
    
    return null;
}

// YouTube'un indirme butonunu gizleyip kendi butonumuzu ekleyen CSS enjekte edelim
function injectCustomCSS() {
    if (document.getElementById('youtube-downloader-styles')) {
        return; // CSS zaten enjekte edilmiş
    }
    
    const style = document.createElement('style');
    style.id = 'youtube-downloader-styles';
    style.textContent = `
        /* YouTube'un kendi indirme butonunu gizle */
        ytd-download-button-renderer, 
        button[aria-label="İndir"]:not(#youtube-downloader-btn) {
            display: none !important;
        }
    `;
    document.head.appendChild(style);
    console.log("YouTube Downloader Companion: CSS enjekte edildi");
}

// YouTube'un indirme butonunu değiştirme fonksiyonu - Doğrudan butonlar kapsayıcısına ekleyelim
function addButtonToYouTube() {
    // Önce CSS'i enjekte edelim
    injectCustomCSS();
    
    // Eğer butonumuz zaten eklenmişse, tekrar eklemeyelim
    if (document.getElementById('youtube-downloader-btn')) {
        return true;
    }
    
    // Butonların olduğu kapsayıcıyı bulalım
    const buttonContainer = findButtonContainer();
    
    // Eğer geçerli bir kapsayıcı bulamazsak, sayfanın yüklenmesini bekleyelim
    if (!buttonContainer) {
        console.log("YouTube Downloader Companion: Buton kapsayıcısı bulunamadı, tekrar deneniyor...");
        return false;
    }
    
    // Kendi butonumuzu oluşturalım
    const customButton = createDownloadButton();
    
    // Butonumuzu kapsayıcıya ekleyelim
    buttonContainer.appendChild(customButton);
    console.log("YouTube Downloader Companion: Buton başarıyla eklendi");
    
    // Menünün dışına tıklandığında kapatalım
    document.addEventListener('click', (event) => {
        const menu = document.getElementById('youtube-downloader-menu');
        const button = document.getElementById('youtube-downloader-btn');
        if (menu && button && !button.contains(event.target) && !menu.contains(event.target)) {
            menu.style.display = 'none';
        }
    });
    
    return true;
}

// Sayfadaki tüm butonları konsola yazdıran yardımcı fonksiyon (hata ayıklama için)
function debugButtons() {
    console.log("Sayfadaki butonlar:");
    const buttons = document.querySelectorAll('button');
    buttons.forEach(button => {
        const ariaLabel = button.getAttribute('aria-label');
        const text = button.textContent.trim();
        console.log(`Button: ${text || 'No text'}, Aria-Label: ${ariaLabel || 'No label'}, Parent: ${button.parentElement.tagName}`);
    });
    
    // Ayrıca olası kapsayıcıları da kontrol edelim
    console.log("Olası buton kapsayıcıları:");
    ['#actions', '#actions-inner', '#top-level-buttons-computed', '#flexible-item-buttons'].forEach(selector => {
        const el = document.querySelector(selector);
        console.log(`${selector}: ${el ? 'Bulundu' : 'Bulunamadı'}`);
    });
}

// YouTube'un dinamik yapısı nedeniyle butonu eklemek için bir gözlemci kullanalım
const observer = new MutationObserver((mutations) => {
    // Sayfa URL'sinin bir video sayfası olup olmadığını kontrol edelim
    const isVideoPage = window.location.href.includes('/watch');
    
    if (isVideoPage) {
        // Eğer buton henüz eklenmemişse, eklemeyi deneyelim
        if (!document.getElementById('youtube-downloader-btn')) {
            addButtonToYouTube();
        }
    }
});

// Gözlemciyi başlatalım
observer.observe(document.body, {
    childList: true,
    subtree: true
});

// Sayfa yüklendikten sonra butonu eklemeyi deneyelim
window.addEventListener('load', () => {
    // Sayfa URL'sinin bir video sayfası olup olmadığını kontrol edelim
    const isVideoPage = window.location.href.includes('/watch');
    
    if (isVideoPage) {
        // Butonun eklenmesi için biraz bekleyelim, YouTube'un kendi butonları yüklensin
        setTimeout(() => {
            if (!addButtonToYouTube()) {
                // Başarısız olursa, hata ayıklama bilgisi alalım
                debugButtons();
                // Biraz daha bekleyip tekrar deneyelim
                setTimeout(() => {
                    if (!addButtonToYouTube()) {
                        // İkinci deneme de başarısız olursa, zorla ekleyelim
                        const forceContainer = document.querySelector('ytd-menu-renderer') || 
                                             document.querySelector('#actions') || 
                                             document.querySelector('#above-the-fold');
                        
                        if (forceContainer && !document.getElementById('youtube-downloader-btn')) {
                            const customButton = createDownloadButton();
                            forceContainer.appendChild(customButton);
                            console.log("YouTube Downloader Companion: Buton zorla eklendi");
                        }
                    }
                }, 2000);
            }
        }, 1500); // 1.5 saniye bekle
    }
});

// URL değişikliklerini dinleyelim (YouTube SPA olduğu için)
let lastUrl = window.location.href;
new MutationObserver(() => {
    const currentUrl = window.location.href;
    if (currentUrl !== lastUrl) {
        lastUrl = currentUrl;
        
        // Sayfa URL'sinin bir video sayfası olup olmadığını kontrol edelim
        const isVideoPage = currentUrl.includes('/watch');
        
        if (isVideoPage) {
            // Butonun eklenmesi için biraz bekleyelim, YouTube'un kendi butonları yüklensin
            setTimeout(() => {
                if (!addButtonToYouTube()) {
                    // Başarısız olursa, hata ayıklama bilgisi alalım
                    debugButtons();
                    // Biraz daha bekleyip tekrar deneyelim
                    setTimeout(() => {
                        if (!addButtonToYouTube()) {
                            // İkinci deneme de başarısız olursa, zorla ekleyelim
                            const forceContainer = document.querySelector('ytd-menu-renderer') || 
                                                 document.querySelector('#actions') || 
                                                 document.querySelector('#above-the-fold');
                            
                            if (forceContainer && !document.getElementById('youtube-downloader-btn')) {
                                const customButton = createDownloadButton();
                                forceContainer.appendChild(customButton);
                                console.log("YouTube Downloader Companion: Buton zorla eklendi");
                            }
                        }
                    }, 2000);
                }
            }, 1500); // 1.5 saniye bekle
        }
    }
}).observe(document, {subtree: true, childList: true});

// Tema değişikliğini dinleyelim
const htmlObserver = new MutationObserver(() => {
    const downloadBtn = document.getElementById('youtube-downloader-btn');
    if (downloadBtn) {
        const iconColor = isYouTubeDarkTheme() ? '#fff' : 'currentcolor';
        const svg = downloadBtn.querySelector('svg');
        if (svg && svg.parentElement) {
            svg.parentElement.style.fill = iconColor;
        }
    }
});

htmlObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['dark']
}); 