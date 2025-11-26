// background.js

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'download') {
        const { videoUrl, format, formatType, videoTitle } = request;
        
        console.log(`Background script received: ${format} (${formatType}) for "${videoTitle}"`);

        // Python uygulamasının çalıştığı API endpoint'i
        const apiUrl = 'http://127.0.0.1:5000/download';

        fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                videoUrl: videoUrl,
                format: format,
                formatType: formatType,
                videoTitle: videoTitle
            }),
        })
        .then(response => {
            if (!response.ok) {
                // Sunucudan gelen hata durumunu yakala
                return response.text().then(text => { 
                    throw new Error(`Server responded with ${response.status}: ${text}`) 
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Success:', data);
            
            // İndirme başladığında kullanıcıya bildirim gösterelim
            chrome.notifications.create({
                type: 'basic',
                iconUrl: 'icons/download.svg',
                title: 'İndirme Başladı',
                message: `"${videoTitle}" indiriliyor...`,
                priority: 2
            });
            
            sendResponse({ status: 'success', data: data });
        })
        .catch((error) => {
            console.error('Error:', error);
            
            // Hata durumunda kullanıcıya bildirim gösterelim
            chrome.notifications.create({
                type: 'basic',
                iconUrl: 'icons/download.svg',
                title: 'İndirme Hatası',
                message: `"${videoTitle}" indirilirken bir hata oluştu.`,
                priority: 2
            });
            
            sendResponse({ status: 'error', message: error.message });
        });

        // Asenkron bir yanıt gönderileceğini belirtmek için true döndür
        return true;
    }
}); 