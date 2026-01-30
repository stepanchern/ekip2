// --- 1. Mock Database (Simulating Backend) ---
// Data will be fetched from the "database"
let products = [];
let stores = [];
let prices = {};

// User State
let shoppingList = [];
let userLocation = { lat: 43.2141, lng: 27.9147 }; // Varna, Bulgaria
let map, userMarker, routeLayer, storeMarkersLayer;

// --- 2. Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
    if (navigator.geolocation) {
        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 });
            });
            userLocation = { lat: position.coords.latitude, lng: position.coords.longitude };
        } catch (error) {
            console.warn("Geolocation access denied or failed. Using default location.");
        }
    }

    await loadDatabase();

    initMap();
    populateProductSelect();
    
    document.getElementById('add-btn').addEventListener('click', addToCart);
    document.getElementById('clear-btn').addEventListener('click', clearCart);
    document.getElementById('product-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') addToCart();
    });
});

async function loadDatabase() {
    products = [
        { id: 1, name: "Мляко (1 л)" },
        { id: 2, name: "Хляб (самун)" },
        { id: 3, name: "Яйца (10 бр.)" },
        { id: 4, name: "Ябълки (1 кг)" },
        { id: 5, name: "Пилешки гърди (1 кг)" },
        { id: 6, name: "Ориз (1 кг)" }
    ];

    const chainPrices = {
        "Lidl": { 1: 2.20, 2: 1.50, 3: 3.80, 4: 1.80, 5: 10.50, 6: 2.80 },
        "Kaufland": { 1: 2.15, 2: 1.40, 3: 3.70, 4: 1.70, 5: 10.20, 6: 2.70 },
        "Billa": { 1: 2.40, 2: 1.80, 3: 4.20, 4: 2.00, 5: 11.50, 6: 3.20 },
        "Bulmag": { 1: 2.30, 2: 1.60, 3: 4.00, 4: 1.90, 5: 11.00, 6: 3.00 },
        "MyMarket": { 1: 2.50, 2: 1.90, 3: 4.50, 4: 2.20, 5: 12.00, 6: 3.50 },
        "Nablizo": { 1: 2.60, 2: 2.00, 3: 4.80, 4: 2.50, 5: 12.50, 6: 3.80 }
    };
    const supportedChains = Object.keys(chainPrices);

    try {
        // Search within 5000 meters (5km) of the user's location
        const query = `[out:json][timeout:25];
            (
                node"shop"="supermarket";
                way"shop"="supermarket";
                relation"shop"="supermarket";
            );
            out center;`;
        const response = await fetch('https://overpass-api.de/api/interpreter', {
            method: 'POST',
            body: query
        });
        const data = await response.json();
        stores = data.elements.map(el => {
            const name = el.tags.name || "Неизвестен супермаркет";
            let chain = "Неизвестно";
            
            // Match against supported chains
            for (const c of supportedChains) {
                if (name.toLowerCase().includes(c.toLowerCase())) {
                    chain = c;
                    break;
                }
            }

            // Fallback: Assign random chain if unknown to ensure prices exist for demo
            if (chain === "Неизвестно") {
                chain = supportedChains[Math.floor(Math.random() * supportedChains.length)];
            }

            return { id: el.id, name: name, chain: chain, lat: el.lat || el.center.lat, lng: el.lon || el.center.lon };
        });
    } catch (e) {
        console.error("Overpass API Error:", e);
    }

    // Fallback: Add sample stores if API fails or returns no results (for testing)
    if (stores.length === 0) {
        stores.push({
            id: 999,
            name: "Тестов магазин (Lidl)",
            chain: "Lidl",
            lat: userLocation.lat + 0.1,
            lng: userLocation.lng + 0.1
        });
        stores.push({
            id: 1000,
            name: "Тестов магазин (Kaufland)",
            chain: "Kaufland",
            lat: userLocation.lat - 0.05,
            lng: userLocation.lng + 0.05
        });
        stores.push({
            id: 1001,
            name: "Тестов магазин (Billa)",
            chain: "Billa",
            lat: userLocation.lat + 0.03,
            lng: userLocation.lng - 0.02
        });
        stores.push({
            id: 1002,
            name: "Тестов магазин (Bulmag)",
            chain: "Bulmag",
            lat: userLocation.lat - 0.03,
            lng: userLocation.lng - 0.03
        });
        stores.push({
            id: 1003,
            name: "Тестов магазин (MyMarket)",
            chain: "MyMarket",
            lat: userLocation.lat + 0.02,
            lng: userLocation.lng + 0.04
        });
        stores.push({
            id: 1004,
            name: "Тестов магазин (Nablizo)",
            chain: "Nablizo",
            lat: userLocation.lat - 0.01,
            lng: userLocation.lng - 0.04
        });
        stores.push({
            id: 1005,
            name: "Тестов магазин (Lidl Center)",
            chain: "Lidl",
            lat: userLocation.lat + 0.005,
            lng: userLocation.lng - 0.005
        });
    }

    prices = {};
    stores.forEach(store => {
        if (chainPrices[store.chain]) {
            prices[store.id] = chainPrices[store.chain];
        }
    });
}

function populateProductSelect() {
    const dataList = document.getElementById('product-list');
    products.forEach(p => {
        const option = document.createElement('option');
        option.value = p.name;
        dataList.appendChild(option);
    });
}

// --- 3. Shopping List Logic ---
function addToCart() {
    const searchInput = document.getElementById('product-search');
    const quantityInput = document.getElementById('product-quantity');
    const productName = searchInput.value.trim();
    const quantity = parseInt(quantityInput.value) || 1;

    let product = products.find(p => p.name === productName);
    
    if (!product && productName) {
        product = products.find(p => p.name.toLowerCase().includes(productName.toLowerCase()));
    }
    
    if (!product) {
        alert("Моля, изберете валиден продукт от списъка.");
        return;
    }
    
    const existingItem = shoppingList.find(item => item.id === product.id);
    if (existingItem) {
        existingItem.quantity += quantity;
    } else {
        shoppingList.push({ ...product, quantity: quantity });
    }

    searchInput.value = '';
    quantityInput.value = 1;
    renderList();
    calculateAndCompare();
}

function removeFromCart(id) {
    shoppingList = shoppingList.filter(item => item.id !== id);
    renderList();
    calculateAndCompare();
}

function clearCart() {
    shoppingList = [];
    renderList();
}

function renderList() {
    const listEl = document.getElementById('shopping-list');
    listEl.innerHTML = '';
    
    shoppingList.forEach(item => {
        const li = document.createElement('li');
        li.innerHTML = `
            <div class="item-details">
                <span class="item-name">${item.name}</span>
                <span class="item-qty">Количество: ${item.quantity}</span>
            </div>
            <button class="remove-btn" onclick="removeFromCart(${item.id})">Премахни</button>
        `;
        listEl.appendChild(li);
    });

    const comparisonDiv = document.getElementById('price-comparison');
    const clearBtn = document.getElementById('clear-btn');
    if (shoppingList.length > 0) {
        comparisonDiv.classList.remove('hidden');
        clearBtn.style.display = 'block';
    } else {
        comparisonDiv.classList.add('hidden');
        document.getElementById('comparison-results').innerHTML = '';
        clearBtn.style.display = 'none';
        clearMapRoutes();
        if (storeMarkersLayer) storeMarkersLayer.clearLayers();
    }
}

// --- 4. Price Comparison & Route Logic ---
async function calculateAndCompare() {
    if (shoppingList.length === 0) return;

    if (storeMarkersLayer) storeMarkersLayer.clearLayers();

    const resultsContainer = document.getElementById('comparison-results');
    resultsContainer.innerHTML = '<p>Изчисляване на маршрути...</p>';

    let storeTotals = [];

    // Calculate total for each store
    stores.forEach(store => {
        let total = 0;
        let availableCount = 0;

        shoppingList.forEach(item => {
            const price = prices[store.id][item.id];
            if (price) {
                total += price * item.quantity;
                availableCount++;
            }
        });

        // Only consider stores that have all items (or handle partials differently)
        // For this demo, we assume all stores carry all items, or we mark availability.
        storeTotals.push({
            store: store,
            total: total,
            missing: shoppingList.length - availableCount
        });
    });

    // Sort by price to determine colors
    storeTotals.sort((a, b) => a.total - b.total);
    
    if (storeTotals.length === 0) {
        resultsContainer.innerHTML = '<p>Не са намерени поддържани магазини наблизо.</p>';
        return;
    }

    const minPrice = storeTotals[0].total;
    const maxPrice = storeTotals[storeTotals.length - 1].total;

    resultsContainer.innerHTML = '';

    // Render Cards
    for (const data of storeTotals) {
        const div = document.createElement('div');
        const routeData = await getRouteData(userLocation, data.store);
        const distanceText = routeData ? (routeData.distance / 1000).toFixed(1) + ' km' : 'N/A';
        let colorClass = 'avg';
        
        if (data.total === minPrice) colorClass = 'cheap';
        else if (data.total === maxPrice) colorClass = 'exp';

        const totalBGN = data.total;
        const totalEUR = totalBGN / 1.95583;

        div.className = `store-card ${colorClass}`;
        div.innerHTML = `
            <h3>${data.store.name}</h3>
            <div class="price-tag">€${totalEUR.toFixed(2)} / ${totalBGN.toFixed(2)} лв.</div>
            <small>
                ${data.missing === 0 ? 'Всички продукти са налични' : data.missing + ' липсващи продукта'}
                <br>🚗 Разстояние: ${distanceText}
            </small>
        `;
        
        // Add click listener to focus map
        div.addEventListener('click', () => {
            focusStore(data.store);
        });

        resultsContainer.appendChild(div);
        
        L.marker([data.store.lat, data.store.lng], { icon: getMarkerIcon(colorClass) })
            .addTo(storeMarkersLayer)
            .bindPopup(`<b>${data.store.name}</b><br>Цена: ${totalBGN.toFixed(2)} лв.`);
    }

    // Auto-plan route to the cheapest store
    planRoute(storeTotals[0].store);
}

// --- 5. Map & Routing (Leaflet) ---
function initMap() {
    // Initialize map centered on mock user location
    map = L.map('map').setView([userLocation.lat, userLocation.lng], 14);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    // User Marker
    userMarker = L.marker([userLocation.lat, userLocation.lng])
        .addTo(map)
        .bindPopup("<b>Вие сте тук</b>")
        .openPopup();

    routeLayer = L.layerGroup().addTo(map);
    storeMarkersLayer = L.layerGroup().addTo(map);
}

function clearMapRoutes() {
    routeLayer.clearLayers();
    document.getElementById('route-info').innerHTML = '';
}

function focusStore(store) {
    map.flyTo([store.lat, store.lng], 16);
}

async function planRoute(targetStore) {
    clearMapRoutes();

    // Use OSRM for road-based routing (like Google Maps)
    const mainRoute = await drawRoute(userLocation, targetStore, 'blue');
    if (mainRoute) {
        map.fitBounds(mainRoute.getBounds(), {padding: [50, 50]});
    }

    // Check for "Split Route" optimization
    // This logic checks if buying specific items at different stores saves significant money
    const optimization = checkSplitRouteOptimization();
    
    let routeMsg = `<strong>Препоръчителен маршрут:</strong> Отидете до ${targetStore.name} за най-ниска обща цена.`;
    
    if (optimization.shouldSplit) {
        const savingsBGN = optimization.savings;
        const savingsEUR = savingsBGN / 1.95583;

        routeMsg += `<br><br><strong>💡 Умен съвет:</strong> Можете да спестите 
        <span style="color:green">€${savingsEUR.toFixed(2)} (${savingsBGN.toFixed(2)} лв.)</span> 
        ако купите ${optimization.storeAItems.join(', ')} от ${optimization.storeA.name} 
        и останалото от ${optimization.storeB.name}.`;
        
        // Draw second line if split
        await drawRoute(userLocation, optimization.storeB, 'green', '5, 10');
    }

    document.getElementById('route-info').innerHTML = routeMsg;
}

async function drawRoute(start, end, color, dashArray = null) {
    const url = `https://router.project-osrm.org/route/v1/driving/${start.lng},${start.lat};${end.lng},${end.lat}?overview=full&geometries=geojson`;
    try {
        const response = await fetch(url);
        const data = await response.json();
        if (data.routes && data.routes.length > 0) {
            const options = { color: color, weight: 4, opacity: 0.7 };
            if (dashArray) options.dashArray = dashArray;
            return L.geoJSON(data.routes[0].geometry, { style: options }).addTo(routeLayer);
        }
    } catch (e) {
        console.error("Routing error:", e);
    }
    return null;
}

async function getRouteData(start, end) {
    const url = `https://router.project-osrm.org/route/v1/driving/${start.lng},${start.lat};${end.lng},${end.lat}?overview=false`;
    try {
        const response = await fetch(url);
        const data = await response.json();
        if (data.routes && data.routes.length > 0) {
            return data.routes[0];
        }
    } catch (e) {
        console.error("Routing error:", e);
    }
    return null;
}

function checkSplitRouteOptimization() {
    // Naive algorithm: Compare cheapest single store vs cheapest individual items
    // In reality, this needs to account for travel cost (gas/time).
    
    if (shoppingList.length < 2) return { shouldSplit: false };

    let bestSingleStoreTotal = Infinity;
    
    // 1. Find best single store total
    stores.forEach(store => {
        let total = 0;
        shoppingList.forEach(item => total += prices[store.id][item.id] * item.quantity);
        if (total < bestSingleStoreTotal) bestSingleStoreTotal = total;
    });

    // 2. Find absolute cheapest price for every item regardless of store
    let absoluteCheapestTotal = 0;
    shoppingList.forEach(item => {
        let minPrice = Infinity;
        stores.forEach(store => {
            if (prices[store.id][item.id] < minPrice) minPrice = prices[store.id][item.id];
        });
        absoluteCheapestTotal += minPrice * item.quantity;
    });

    const potentialSavings = bestSingleStoreTotal - absoluteCheapestTotal;

    // If savings are significant (e.g., > $2.00), suggest a split
    // This is a mock implementation returning a hypothetical split for demonstration
    if (potentialSavings > 2.00) {
        return {
            shouldSplit: true,
            savings: potentialSavings,
            storeA: stores[1], // Mock: BudgetBuy
            storeB: stores[0], // Mock: FreshMart
            storeAItems: ["Мляко", "Яйца"] // Mock items
        };
    }
    return { shouldSplit: false };
}

function getMarkerIcon(type) {
    const colors = {
        'cheap': '#10b981',
        'avg': '#f59e0b',
        'exp': '#ef4444'
    };
    const color = colors[type] || '#3b82f6';
    
    const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="40" height="40" fill="${color}">
        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
    </svg>`;

    return L.divIcon({
        className: 'custom-pin',
        html: svg,
        iconSize: [40, 40],
        iconAnchor: [20, 40],
        popupAnchor: [0, -40]
    });
}