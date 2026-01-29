let map, userMarker, routeLayer, storeMarkersLayer;
let userLocation = { lat: 43.2047, lng: 27.9100 }; // Default: Varna Center

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Get User Location
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(pos => {
            userLocation = { lat: pos.coords.latitude, lng: pos.coords.longitude };
            initMap();
        }, () => initMap());
    } else {
        initMap();
    }

    // 2. Event Listeners
    document.getElementById('add-btn').addEventListener('click', addToCart);
    document.getElementById('clear-btn').addEventListener('click', clearCart);
});

function initMap() {
    map = L.map('map').setView([userLocation.lat, userLocation.lng], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    
    userMarker = L.marker([userLocation.lat, userLocation.lng]).addTo(map).bindPopup("You are here");
    routeLayer = L.layerGroup().addTo(map);
    storeMarkersLayer = L.layerGroup().addTo(map);
}

async function addToCart() {
    const input = document.getElementById('product-search');
    const qty = document.getElementById('product-quantity').value;
    if (!input.value) return;

    // Add to UI List
    const li = document.createElement('li');
    li.innerHTML = `<span>${input.value} (x${qty})</span> <button onclick="this.parentElement.remove(); updateBackend();">X</button>`;
    li.dataset.name = input.value;
    document.getElementById('shopping-list').appendChild(li);
    
    input.value = '';
    updateBackend();
}

async function updateBackend() {
    const items = Array.from(document.querySelectorAll('#shopping-list li'))
                       .map(li => li.dataset.name);

    if (items.length === 0) {
        clearCart();
        return;
    }

    // Call your Flask API
    const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            items: items,
            coords: `${userLocation.lat}, ${userLocation.lng}`
        })
    });

    const rankings = await response.json();
    displayRankings(rankings);
}

function displayRankings(rankings) {
    const resultsDiv = document.getElementById('comparison-results');
    document.getElementById('price-comparison').classList.remove('hidden');
    document.getElementById('clear-btn').style.display = 'block';
    resultsDiv.innerHTML = '';
    storeMarkersLayer.clearLayers();

    rankings.forEach((data, index) => {
        const card = document.createElement('div');
        card.className = `store-card ${index === 0 ? 'cheap' : ''}`;
        card.innerHTML = `
            <h3>${data.chain_name}</h3>
            <p>${data.address}</p>
            <div class="price-tag">${data.real_price.toFixed(2)} лв</div>
            <small>${data.distance_km} km away | ${data.missing_count} missing</small>
        `;
        
        // When clicking a store card, draw the route to it
        card.onclick = () => planRoute(data);
        resultsDiv.appendChild(card);

        // Add Marker
        const [lat, lon] = data.coords.split(',').map(Number);
        L.marker([lat, lon]).addTo(storeMarkersLayer).bindPopup(data.chain_name);
    });

    // Auto-draw route to the #1 cheapest store
    if (rankings.length > 0) planRoute(rankings[0]);
}

async function planRoute(targetStore) {
    routeLayer.clearLayers();
    const [tLat, tLon] = targetStore.coords.split(',').map(Number);
    
    // OSRM API Call (from your mock file logic)
    const url = `https://router.project-osrm.org/route/v1/driving/${userLocation.lng},${userLocation.lat};${tLon},${tLat}?overview=full&geometries=geojson`;
    
    const resp = await fetch(url);
    const data = await resp.json();
    
    if (data.routes && data.routes.length > 0) {
        L.geoJSON(data.routes[0].geometry, {
            style: { color: 'blue', weight: 5, opacity: 0.6 }
        }).addTo(routeLayer);
        
        document.getElementById('route-info').innerHTML = `
            <strong>Target:</strong> ${targetStore.chain_name}<br>
            <strong>Distance:</strong> ${(data.routes[0].distance / 1000).toFixed(2)} km via roads.
        `;
    }
}

function clearCart() {
    document.getElementById('shopping-list').innerHTML = '';
    document.getElementById('price-comparison').classList.add('hidden');
    document.getElementById('clear-btn').style.display = 'none';
    routeLayer.clearLayers();
    storeMarkersLayer.clearLayers();
}