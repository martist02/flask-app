// main.js
let map, marker, socket, qrcode;
let tracking = false;
let userId = null;
let userRole = null;

// Initialize socket connection
socket = io();

document.addEventListener('DOMContentLoaded', async function() {
    await checkAuth();
    initializeMap();
    initializeSocket();
    initializeQRCode();
    setupEventListeners();
});

async function checkAuth() {
    try {
        const response = await fetch('/api/check-auth');
        const data = await response.json();
        if (!data.authenticated) {
            window.location.href = '/login';
            return;
        }
        userId = data.userId;
        userRole = data.role;
        document.getElementById('userName').textContent = data.name;
        document.getElementById('userRole').textContent = data.role;
        document.getElementById('profileImage').src = data.profileImage || 'profile-placeholder.jpg';

        if (data.role === 'relative') {
            loadRelativeUI();
        } else {
            loadUserUI();
        }
    } catch (error) {
        showError('เกิดข้อผิดพลาดในการตรวจสอบสิทธิ์');
    }
}

function initializeMap() {
    map = L.map('map').setView([13.7563, 100.5018], 15);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    marker = L.marker([13.7563, 100.5018]).addTo(map);
}

function initializeSocket() {
    socket.on('location-update', (data) => {
        if (userRole === 'relative' && data.userId === userId) {
            updateMapLocation(data.latitude, data.longitude);
            updateLocationInfo(data);
            showNotification('ได้รับการอัพเดทตำแหน่งใหม่');
        }
    });

    socket.on('tracking-started', (data) => {
        tracking = true;
        updateTrackingStatus(true);
        showNotification('เริ่มการติดตามตำแหน่งแล้ว');
    });

    socket.on('tracking-stopped', (data) => {
        tracking = false;
        updateTrackingStatus(false);
        showNotification('หยุดการติดตามตำแหน่งแล้ว');
    });
}

function initializeQRCode() {
    const trackingUrl = `${window.location.origin}/track/${userId}`;
    qrcode = new QRCode(document.getElementById("qrcode"), {
        text: trackingUrl,
        width: 128,
        height: 128
    });
}

function startTracking() {
    if ("geolocation" in navigator) {
        tracking = true;
        updateTrackingStatus(true);

        navigator.geolocation.watchPosition(
            position => {
                const { latitude, longitude } = position.coords;
                updateLocationData(latitude, longitude);
            },
            error => {
                console.error('Error getting location:', error);
                showError('ไม่สามารถรับตำแหน่งปัจจุบันได้');
                stopTracking();
            },
            {
                enableHighAccuracy: true,
                maximumAge: 30000,
                timeout: 27000
            }
        );
    } else {
        showError('เบราว์เซอร์ไม่รองรับการระบุตำแหน่ง');
    }
}

function stopTracking() {
    tracking = false;
    updateTrackingStatus(false);
    socket.emit('stop-tracking', { userId });
}

async function updateLocationData(latitude, longitude) {
    try {
        const response = await fetch('/api/update-location', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                userId,
                latitude, 
                longitude,
                timestamp: new Date().toISOString()
            })
        });

        if (!response.ok) throw new Error('Failed to update location');

        updateMapLocation(latitude, longitude);
        updateLocationInfo({ latitude, longitude });
        socket.emit('location-update', { userId, latitude, longitude });
    } catch (error) {
        console.error('Error updating location:', error);
        showError('ไม่สามารถอัพเดทตำแหน่งได้');
    }
}

function updateMapLocation(latitude, longitude) {
    marker.setLatLng([latitude, longitude]);
    map.setView([latitude, longitude]);
}

function updateLocationInfo(data) {
    const locationElem = document.getElementById('currentLocation');
    const updateElem = document.getElementById('lastUpdate');

    locationElem.textContent = `ละติจูด: ${data.latitude.toFixed(6)}, ลองจิจูด: ${data.longitude.toFixed(6)}`;
    updateElem.textContent = `อัพเดทล่าสุด: ${new Date().toLocaleString('th-TH')}`;
}

function updateTrackingStatus(isTracking) {
    const statusElem = document.getElementById('trackingStatus');
    if (isTracking) {
        statusElem.textContent = 'กำลังติดตามตำแหน่ง';
        statusElem.className = 'tracking-status tracking-active';
    } else {
        statusElem.textContent = 'หยุดการติดตามแล้ว';
        statusElem.className = 'tracking-status tracking-inactive';
    }
}

function showNotification(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-info alert-dismissible fade show';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    document.body.appendChild(alertDiv);
    setTimeout(() => alertDiv.remove(), 5000);
}

function showError(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-danger alert-dismissible fade show';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    document.body.appendChild(alertDiv);
    setTimeout(() => alertDiv.remove(), 5000);
}

async function logout() {
    try {
        await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });
        window.location.href = '/login';
    } catch (error) {
        showError('ไม่สามารถออกจากระบบได้');
    }
}