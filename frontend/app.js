// Configuration
const CONFIG = {
    DIAGRAM_TYPE: 'architecture-beta',
    LOCAL_API_URL: 'http://localhost:8080'
};

// Global state
let currentMermaidCode = '';
let currentDiagramId = '';
let originalMermaidCode = '';
let mermaidCounter = 0;
let currentTab = 'ai-generator';
let currentDiagramTab = 'diagram-view';
let historyLoaded = false;

// SVG zoom and pan state
let svgState = {
    scale: 1,
    translateX: 0,
    translateY: 0,
    isDragging: false,
    startX: 0,
    startY: 0,
    minScale: 0.1,
    maxScale: 5
};

// Initialize Mermaid
function initializeMermaid() {
    mermaid.initialize({
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'loose',
        flowchart: { useMaxWidth: true, htmlLabels: true },
        architecture: { useMaxWidth: true, htmlLabels: true },
        dompurifyConfig: {
            USE_PROFILES: { svg: true, svgFilters: true },
            ADD_TAGS: ['iconify-icon'],
            ADD_ATTR: ['icon', 'width', 'height', 'inline']
        }
    });

    // Register icon packs
    mermaid.registerIconPacks([
        { name: 'gcp', loader: () => fetch(getIconUrl('gcp.json')).then(res => res.json()) },
        { name: 'azr', loader: () => fetch(getIconUrl('azr.json')).then(res => res.json()) },
        { name: 'aws', loader: () => fetch(getIconUrl('aws.json')).then(res => res.json()) },
        { name: 'custom', loader: () => fetch(getIconUrl('custom.json')).then(res => res.json()) },
        {
            name: 'logos',
            loader: () =>
                fetch('https://unpkg.com/@iconify-json/logos@1/icons.json').then((res) => res.json()),
        },
        {
            name: 'mdi',
            loader: () =>
                fetch('https://unpkg.com/@iconify-json/mdi@1/icons.json').then((res) => res.json()),
        },

    ]);
}

// Utility functions
function getIconUrl(filename) {
    // Use CloudFront domain (or current origin) for icon files
    const cloudfrontDomain = window.location.origin;
    return `${cloudfrontDomain}/icons/${filename}`;
}

function getApiBaseUrl() {
    // Check for meta tag injected during deployment
    const metaApiUrl = document.querySelector('meta[name="api-base-url"]');
    if (metaApiUrl && metaApiUrl.content) {
        return metaApiUrl.content;
    }

    // Local development
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return CONFIG.LOCAL_API_URL;
    }

    // Fallback: warn if meta tag is missing in production
    console.warn('API URL meta tag not found. Please ensure the deployment script injects the api-base-url meta tag.');
    return '';
}

// DOM manipulation
function showLoading(isManual = false) {
    const container = document.getElementById('diagramContainer');
    const placeholder = document.getElementById('placeholder');

    if (container && placeholder) {
        // 기존 다이어그램 모두 제거
        const existingDiagrams = container.querySelectorAll('div:not(#placeholder)');
        existingDiagrams.forEach(diagram => diagram.remove());

        // 스피너 표시
        const loadingText = isManual ? '다이어그램 렌더링 중...' : '다이어그램 생성 중...';
        placeholder.innerHTML = `
            <div class="spinner-container">
                <div class="spinner"></div>
                <div class="loading-text">${loadingText}</div>
                <div class="loading-subtext">잠시만 기다려 주세요</div>
            </div>
        `;
        placeholder.style.display = 'block';
    }

    // 버튼 비활성화
    if (isManual) {
        const btnText = document.getElementById('manualBtnText');
        const button = document.querySelector('#manualCodeForm .generate-btn');
        if (btnText) btnText.textContent = '렌더링 중...';
        if (button) button.disabled = true;
    } else {
        const btnText = document.getElementById('btnText');
        const button = document.querySelector('#diagramForm .generate-btn');
        if (btnText) btnText.textContent = '생성 중...';
        if (button) button.disabled = true;
    }
}

function hideLoading(isManual = false) {
    const placeholder = document.getElementById('placeholder');
    if (placeholder) {
        placeholder.style.display = 'none';
    }

    // 버튼 상태 복원
    if (isManual) {
        const btnText = document.getElementById('manualBtnText');
        const button = document.querySelector('#manualCodeForm .generate-btn');
        if (btnText) btnText.textContent = '다이어그램 렌더링';
        if (button) button.disabled = false;
    } else {
        const btnText = document.getElementById('btnText');
        const button = document.querySelector('#diagramForm .generate-btn');
        if (btnText) btnText.textContent = '다이어그램 생성';
        if (button) button.disabled = false;
    }
}

function showDiagramActions() {
    const actionsElement = document.getElementById('diagramActions');
    if (actionsElement) {
        actionsElement.style.display = 'flex';
    }
    // Show and populate inline code editor
    showCodeEditor(currentMermaidCode);
}

function showError(message) {
    console.log('showError 호출됨');

    const container = document.getElementById('diagramContainer');
    const placeholder = document.getElementById('placeholder');

    if (container) {
        // 기존 다이어그램 모두 제거
        const existingDiagrams = container.querySelectorAll('div:not(#placeholder)');
        existingDiagrams.forEach(diagram => diagram.remove());

        if (placeholder) {
            placeholder.innerHTML = `
                <div class="placeholder-icon">⚠️</div>
                <h3>오류가 발생했습니다</h3>
                <div style="text-align: left; max-width: 400px; margin: 0 auto;">${message}</div>
            `;
            placeholder.style.display = 'block';
        }
    }

    // 버튼 상태 복원
    const btnText = document.getElementById('btnText');
    const button = document.querySelector('#diagramForm .generate-btn');
    const manualBtnText = document.getElementById('manualBtnText');
    const manualButton = document.querySelector('#manualCodeForm .generate-btn');

    if (btnText) btnText.textContent = '다이어그램 생성';
    if (button) button.disabled = false;
    if (manualBtnText) manualBtnText.textContent = '다이어그램 렌더링';
    if (manualButton) manualButton.disabled = false;
}

// Main functionality
async function generateDiagram() {
    const formData = new FormData(document.getElementById('diagramForm'));
    const requestData = {
        description: formData.get('description'),
        cloud_provider: formData.get('cloud_provider'),
        diagram_type: CONFIG.DIAGRAM_TYPE
    };

    console.log('다이어그램 생성 시작');

    // 로딩 상태 표시
    showLoading();

    try {
        const API_BASE_URL = getApiBaseUrl();
        console.log('API 요청 전송:', API_BASE_URL);

        const response = await fetch(`${API_BASE_URL}/generate-diagram`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (!data.mermaid_code) {
            throw new Error('API 응답에 mermaid_code가 없습니다.');
        }

        console.log('API 응답 성공, 다이어그램 렌더링 시작');
        currentMermaidCode = data.mermaid_code;
        originalMermaidCode = data.mermaid_code;
        currentDiagramId = data.id || '';
        await renderMermaidDiagram(currentMermaidCode);
        showDiagramActions();

        // Refresh history so the new diagram appears
        historyLoaded = false;

    } catch (error) {
        console.error('API 에러:', error);

        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showError(`API 서버에 연결할 수 없습니다.<br><br>
                <strong>현재 API URL:</strong> ${getApiBaseUrl()}<br><br>
                <em>배포가 완료되었는지 확인하거나 잠시 후 다시 시도해주세요.</em>`);
        } else {
            showError(`다이어그램 생성에 실패했습니다.<br><br>
                <strong>오류:</strong> ${error.message}`);
        }
    }
}

// Tab switching functionality
function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tabName).classList.add('active');

    // Update current tab
    currentTab = tabName;
}

// Manual code rendering
async function renderManualCode() {
    const formData = new FormData(document.getElementById('manualCodeForm'));
    const mermaidCode = formData.get('mermaid_code').trim();

    if (!mermaidCode) {
        showError('코드를 입력해주세요.');
        return;
    }

    console.log('수동 코드 렌더링 시작');

    // 로딩 상태 표시
    showLoading(true);

    try {
        // Validate code starts with architecture-beta
        if (!mermaidCode.toLowerCase().includes('architecture-beta')) {
            throw new Error('코드가 "architecture-beta"로 시작해야 합니다.');
        }

        console.log('수동 코드 렌더링 중:', mermaidCode);
        currentMermaidCode = mermaidCode;
        await renderMermaidDiagram(mermaidCode);
        showDiagramActions();

    } catch (error) {
        console.error('수동 렌더링 에러:', error);
        showError(`코드 렌더링에 실패했습니다.<br><br>
            <strong>오류:</strong> ${error.message}<br><br>
            <small>💡 코드 구문을 확인하고 다시 시도해보세요.</small>`);
    }
}

// Utility function to completely clear diagram container
function clearDiagramContainer() {
    const container = document.getElementById('diagramContainer');
    if (!container) return;

    // Get all direct children of the diagram container
    const children = Array.from(container.children);

    // Remove all children except the placeholder
    children.forEach(child => {
        if (child.id !== 'placeholder') {
            child.remove();
        }
    });

    // Reset mermaid counter to avoid conflicts
    mermaidCounter = 0;
}

async function renderMermaidDiagram(code) {
    const container = document.getElementById('diagramContainer');

    if (!container) {
        console.error('다이어그램 컨테이너를 찾을 수 없습니다');
        return;
    }

    try {
        // Use utility function for thorough cleanup
        clearDiagramContainer();

        // Render with mermaid
        mermaidCounter++;
        const graphDefinition = `mermaid-${mermaidCounter}`;
        const renderResult = await mermaid.render(graphDefinition, code);

        // Insert SVG
        const svgContainer = document.createElement('div');
        svgContainer.style.textAlign = 'center';
        svgContainer.style.padding = '20px';
        svgContainer.innerHTML = renderResult.svg;

        container.appendChild(svgContainer);

        // 로딩 상태 숨기기
        hideLoading(currentTab === 'manual-code');

        // Enable SVG interaction after rendering
        setTimeout(() => enableSVGInteraction(), 100);

    } catch (error) {
        console.error('Mermaid 렌더링 실패:', error);

        // Clear any partial content before trying fallback
        clearDiagramContainer();

        // Fallback method
        try {
            mermaidCounter++;
            const fallbackId = `mermaid-fallback-${mermaidCounter}`;

            const mermaidDiv = document.createElement('div');
            mermaidDiv.id = fallbackId;
            mermaidDiv.className = 'mermaid';
            mermaidDiv.style.textAlign = 'center';
            mermaidDiv.style.padding = '20px';
            mermaidDiv.textContent = code;

            container.appendChild(mermaidDiv);

            await new Promise(resolve => setTimeout(resolve, 200));

            const mermaidElement = document.getElementById(fallbackId);
            if (!mermaidElement) {
                throw new Error('Mermaid 요소를 찾을 수 없습니다.');
            }

            mermaidElement.removeAttribute('data-processed');

            // Try mermaid.init with error handling
            try {
                await mermaid.init(undefined, mermaidElement);

                // Check if rendering was successful (SVG was created)
                const svgElement = mermaidElement.querySelector('svg');
                if (!svgElement) {
                    throw new Error('Mermaid 렌더링이 완료되지 않았습니다.');
                }

                // 로딩 상태 숨기기
                hideLoading(currentTab === 'manual-code');

                // Enable SVG interaction after fallback rendering
                setTimeout(() => enableSVGInteraction(), 500);

            } catch (initError) {
                console.error('mermaid.init 실패:', initError);
                // Remove the failed element
                mermaidElement.remove();
                throw initError;
            }

        } catch (fallbackError) {
            console.error('모든 렌더링 방법 실패:', fallbackError);

            // Ensure complete cleanup on final failure
            clearDiagramContainer();

            showError(`다이어그램 렌더링에 실패했습니다.<br><br>
                <strong>Mermaid 코드:</strong><br>
                <pre style="background: #f5f5f5; padding: 15px; border-radius: 4px; font-size: 12px; overflow-x: auto; margin: 10px 0;">${code}</pre>
                <br><small>💡 이 코드를 <a href="https://mermaid.live" target="_blank">mermaid.live</a>에서 직접 테스트해보세요.</small>`);
        }
    }
}

// Download and export functions
function downloadDiagram(format) {
    const svg = document.querySelector('#diagramContainer svg');
    if (!svg) return;

    if (format === 'svg') {
        const svgData = new XMLSerializer().serializeToString(svg);
        const svgBlob = new Blob([svgData], { type: 'image/svg+xml' });
        const svgUrl = URL.createObjectURL(svgBlob);
        const link = document.createElement('a');
        link.href = svgUrl;
        link.download = 'cloud-architecture.svg';
        link.click();
        URL.revokeObjectURL(svgUrl);
    } else if (format === 'png') {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const img = new Image();

        // Get SVG dimensions
        const svgRect = svg.getBoundingClientRect();
        const svgWidth = svg.viewBox?.baseVal?.width || svgRect.width || 800;
        const svgHeight = svg.viewBox?.baseVal?.height || svgRect.height || 600;

        // Use current UI scale factor instead of fixed 2x
        // svgState.scale represents the current zoom level in the UI
        const scaleFactor = svgState.scale;

        // Set canvas size based on current UI scale
        canvas.width = svgWidth * scaleFactor;
        canvas.height = svgHeight * scaleFactor;

        // Scale the context to ensure correct drawing operations
        ctx.scale(scaleFactor, scaleFactor);

        // Enable high-quality rendering
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';

        // Create SVG data with current scale
        const svgClone = svg.cloneNode(true);
        svgClone.setAttribute('width', svgWidth);
        svgClone.setAttribute('height', svgHeight);

        const svgData = new XMLSerializer().serializeToString(svgClone);
        const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
        const svgUrl = URL.createObjectURL(svgBlob);

        img.onload = function () {
            // Fill white background for better contrast
            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, svgWidth, svgHeight);

            // Draw the image
            ctx.drawImage(img, 0, 0, svgWidth, svgHeight);

            canvas.toBlob(function (blob) {
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = 'cloud-architecture.png';
                link.click();
                URL.revokeObjectURL(link.href);
            }, 'image/png', 1.0); // Maximum quality

            URL.revokeObjectURL(svgUrl);
        };

        img.onerror = function () {
            console.error('PNG 변환 중 오류가 발생했습니다.');
            alert('PNG 다운로드 중 오류가 발생했습니다. SVG 형식으로 다운로드해보세요.');
            URL.revokeObjectURL(svgUrl);
        };

        img.src = svgUrl;
    }
}

function copyMermaidCode() {
    if (currentMermaidCode) {
        navigator.clipboard.writeText(currentMermaidCode).then(() => {
            alert('Mermaid 코드가 클립보드에 복사되었습니다!');
        });
    }
}

// Event handlers
function setExample(text) {
    document.getElementById('description').value = text;
}

function handleExampleClick(event) {
    const example = event.target.closest('.example-item');
    if (example && example.dataset.example) {
        // Handle AI generation examples
        setExample(example.dataset.example);
    } else if (example && example.dataset.code) {
        // Handle manual code examples
        document.getElementById('mermaidCode').value = example.dataset.code;
    }
}

function handleActionClick(event) {
    const button = event.target.closest('.action-btn');
    if (!button) return;

    const action = button.dataset.action;
    switch (action) {
        case 'download-svg':
            downloadDiagram('svg');
            break;
        case 'download-png':
            downloadDiagram('png');
            break;
        case 'copy-code':
            copyMermaidCode();
            break;
        case 'share':
            shareDiagram();
            break;
    }
}

// Initialize app
function initializeApp() {
    initializeMermaid();

    // Form submission for AI generator
    document.getElementById('diagramForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await generateDiagram();
    });

    // Form submission for manual code
    document.getElementById('manualCodeForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await renderManualCode();
    });

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tabName = e.target.dataset.tab;
            switchTab(tabName);
        });
    });

    // Example items - use event delegation for both AI and manual examples
    document.addEventListener('click', (event) => {
        const example = event.target.closest('.example-item');
        if (example) {
            handleExampleClick(event);
        }
    });

    // Action buttons - use event delegation
    document.addEventListener('click', handleActionClick);

    // Diagram panel tab switching
    document.querySelectorAll('.diagram-tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tabName = e.target.dataset.diagramTab;
            switchDiagramTab(tabName);
        });
    });

    // History refresh button
    const refreshBtn = document.getElementById('refreshHistoryBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            historyLoaded = false;
            loadHistory();
        });
    }

    // Initialize SVG controls
    initializeSVGControls();

    // Initialize inline code editor
    initializeCodeEditor();

    console.log('앱 초기화 완료');
    console.log('API URL:', getApiBaseUrl());

    // Check for shared diagram in URL
    checkSharedDiagram();
}

// SVG Zoom and Pan functionality
function initializeSVGControls() {
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const resetZoomBtn = document.getElementById('resetZoomBtn');
    const diagramContainer = document.getElementById('diagramContainer');

    if (zoomInBtn) zoomInBtn.addEventListener('click', () => zoomSVG(1.2));
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => zoomSVG(0.8));
    if (resetZoomBtn) resetZoomBtn.addEventListener('click', resetSVGZoom);

    // Add mouse wheel support
    if (diagramContainer) {
        diagramContainer.addEventListener('wheel', handleWheelZoom, { passive: false });
    }
}

function enableSVGInteraction() {
    const svgElement = document.querySelector('#diagramContainer svg');
    if (!svgElement) return;

    // Make sure controls are visible
    const controls = document.getElementById('diagramControls');
    if (controls) controls.style.display = 'block';

    // Reset state
    resetSVGState();

    // Add drag functionality
    svgElement.addEventListener('mousedown', startDrag);
    svgElement.addEventListener('mousemove', drag);
    svgElement.addEventListener('mouseup', endDrag);
    svgElement.addEventListener('mouseleave', endDrag);

    // Touch support
    svgElement.addEventListener('touchstart', startDragTouch, { passive: false });
    svgElement.addEventListener('touchmove', dragTouch, { passive: false });
    svgElement.addEventListener('touchend', endDrag);

    // Initial transform
    applySVGTransform();
    updateZoomDisplay();
}

function resetSVGState() {
    svgState.scale = 1;
    svgState.translateX = 0;
    svgState.translateY = 0;
    svgState.isDragging = false;
}

function applySVGTransform() {
    const svgElement = document.querySelector('#diagramContainer svg');
    if (!svgElement) return;

    const transform = `translate(${svgState.translateX}px, ${svgState.translateY}px) scale(${svgState.scale})`;
    svgElement.style.transform = transform;
    svgElement.style.transformOrigin = 'center center';
    svgElement.style.cursor = svgState.isDragging ? 'grabbing' : 'grab';
}

function zoomSVG(factor) {
    const newScale = svgState.scale * factor;
    if (newScale >= svgState.minScale && newScale <= svgState.maxScale) {
        svgState.scale = newScale;
        applySVGTransform();
        updateZoomDisplay();
    }
}

function resetSVGZoom() {
    resetSVGState();
    applySVGTransform();
    updateZoomDisplay();
}

function updateZoomDisplay() {
    const zoomLevel = document.getElementById('zoomLevel');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(svgState.scale * 100) + '%';
    }
}

function handleWheelZoom(e) {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    zoomSVG(factor);
}

function startDrag(e) {
    e.preventDefault();
    svgState.isDragging = true;
    svgState.startX = e.clientX - svgState.translateX;
    svgState.startY = e.clientY - svgState.translateY;
    applySVGTransform();
}

function drag(e) {
    if (!svgState.isDragging) return;
    e.preventDefault();

    svgState.translateX = e.clientX - svgState.startX;
    svgState.translateY = e.clientY - svgState.startY;
    applySVGTransform();
}

function endDrag() {
    svgState.isDragging = false;
    applySVGTransform();
}

function startDragTouch(e) {
    e.preventDefault();
    if (e.touches.length === 1) {
        const touch = e.touches[0];
        svgState.isDragging = true;
        svgState.startX = touch.clientX - svgState.translateX;
        svgState.startY = touch.clientY - svgState.translateY;
        applySVGTransform();
    }
}

function dragTouch(e) {
    if (!svgState.isDragging || e.touches.length !== 1) return;
    e.preventDefault();

    const touch = e.touches[0];
    svgState.translateX = touch.clientX - svgState.startX;
    svgState.translateY = touch.clientY - svgState.startY;
    applySVGTransform();
}

// Diagram panel tab switching
function switchDiagramTab(tabName) {
    document.querySelectorAll('.diagram-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-diagram-tab="${tabName}"]`).classList.add('active');

    document.querySelectorAll('.diagram-tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tabName).classList.add('active');

    currentDiagramTab = tabName;

    // Load history when switching to history tab for the first time
    if (tabName === 'history-view' && !historyLoaded) {
        loadHistory();
    }
}

// History functions
async function loadHistory() {
    const historyList = document.getElementById('historyList');
    if (!historyList) return;

    historyList.innerHTML = `
        <div class="history-loading">
            <div class="spinner"></div>
            <p>불러오는 중...</p>
        </div>
    `;

    try {
        const API_BASE_URL = getApiBaseUrl();
        const response = await fetch(`${API_BASE_URL}/diagrams?limit=20`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        historyLoaded = true;

        if (!data.diagrams || data.diagrams.length === 0) {
            historyList.innerHTML = `
                <div class="history-empty">
                    <div class="history-empty-icon">📭</div>
                    <h3>저장된 다이어그램이 없습니다</h3>
                    <p>AI로 다이어그램을 생성하면 여기에 표시됩니다.</p>
                </div>
            `;
            return;
        }

        historyList.innerHTML = '';
        data.diagrams.forEach(diagram => {
            const item = createHistoryItem(diagram);
            historyList.appendChild(item);
        });

    } catch (error) {
        console.error('히스토리 로드 실패:', error);
        historyList.innerHTML = `
            <div class="history-empty">
                <div class="history-empty-icon">⚠️</div>
                <h3>불러오기 실패</h3>
                <p>API 서버에 연결할 수 없습니다.<br>잠시 후 다시 시도해주세요.</p>
            </div>
        `;
    }
}

function createHistoryItem(diagram) {
    const item = document.createElement('div');
    item.className = 'history-item';

    const providerClass = `provider-${diagram.cloud_provider || 'gcp'}`;
    const providerLabel = {
        gcp: '☁️ GCP',
        aws: '🟠 AWS',
        azure: '🔵 Azure'
    }[diagram.cloud_provider] || diagram.cloud_provider;

    const createdAt = formatDate(diagram.created_at);

    item.innerHTML = `
        <div class="history-item-header">
            <span class="history-item-provider ${providerClass}">${providerLabel}</span>
            <button class="history-item-delete" data-id="${diagram.id}" title="삭제">✕</button>
        </div>
        <div class="history-item-description">${escapeHtml(diagram.description || '설명 없음')}</div>
        <div class="history-item-date">${createdAt}</div>
    `;

    // Click to load diagram
    item.addEventListener('click', (e) => {
        // Don't trigger if delete button was clicked
        if (e.target.closest('.history-item-delete')) return;
        loadDiagramFromHistory(diagram);
    });

    // Delete button
    const deleteBtn = item.querySelector('.history-item-delete');
    deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteDiagramFromHistory(diagram.id, item);
    });

    return item;
}

function formatDate(isoString) {
    if (!isoString) return '';
    try {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return '방금 전';
        if (diffMins < 60) return `${diffMins}분 전`;
        if (diffHours < 24) return `${diffHours}시간 전`;
        if (diffDays < 7) return `${diffDays}일 전`;

        return date.toLocaleDateString('ko-KR', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    } catch {
        return isoString;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function loadDiagramFromHistory(diagram) {
    if (!diagram.mermaid_code) {
        // If mermaid_code not in list response, fetch detail
        try {
            const API_BASE_URL = getApiBaseUrl();
            const response = await fetch(`${API_BASE_URL}/diagrams/${diagram.id}`);
            if (!response.ok) throw new Error('Failed to fetch diagram');
            const data = await response.json();
            diagram.mermaid_code = data.mermaid_code;
        } catch (error) {
            console.error('다이어그램 상세 조회 실패:', error);
            alert('다이어그램을 불러올 수 없습니다.');
            return;
        }
    }

    // Switch to diagram view
    switchDiagramTab('diagram-view');

    // Render the diagram
    currentMermaidCode = diagram.mermaid_code;
    originalMermaidCode = diagram.mermaid_code;
    currentDiagramId = diagram.id || '';

    showLoading(false);
    try {
        await renderMermaidDiagram(diagram.mermaid_code);
        showDiagramActions();
    } catch (error) {
        console.error('다이어그램 렌더링 실패:', error);
        showError(`다이어그램 렌더링에 실패했습니다.<br><br><strong>오류:</strong> ${error.message}`);
    }

    // Also populate the manual code editor for easy editing
    const mermaidCodeInput = document.getElementById('mermaidCode');
    if (mermaidCodeInput) {
        mermaidCodeInput.value = diagram.mermaid_code;
    }
}

async function deleteDiagramFromHistory(diagramId, itemElement) {
    if (!confirm('이 다이어그램을 삭제하시겠습니까?')) return;

    try {
        const API_BASE_URL = getApiBaseUrl();
        const response = await fetch(`${API_BASE_URL}/diagrams/${diagramId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Remove from DOM with animation
        itemElement.style.transition = 'all 0.3s ease';
        itemElement.style.opacity = '0';
        itemElement.style.transform = 'translateX(20px)';
        setTimeout(() => {
            itemElement.remove();

            // Check if list is now empty
            const historyList = document.getElementById('historyList');
            if (historyList && historyList.children.length === 0) {
                historyList.innerHTML = `
                    <div class="history-empty">
                        <div class="history-empty-icon">📭</div>
                        <h3>저장된 다이어그램이 없습니다</h3>
                        <p>AI로 다이어그램을 생성하면 여기에 표시됩니다.</p>
                    </div>
                `;
            }
        }, 300);

    } catch (error) {
        console.error('다이어그램 삭제 실패:', error);
        alert('삭제에 실패했습니다. 다시 시도해주세요.');
    }
}

// Inline Code Editor
function initializeCodeEditor() {
    const toggle = document.getElementById('codeEditorToggle');
    const reRenderBtn = document.getElementById('reRenderBtn');
    const resetCodeBtn = document.getElementById('resetCodeBtn');
    const editor = document.getElementById('inlineCodeEditor');

    if (toggle) {
        toggle.addEventListener('click', toggleCodeEditor);
    }

    if (reRenderBtn) {
        reRenderBtn.addEventListener('click', reRenderFromEditor);
    }

    if (resetCodeBtn) {
        resetCodeBtn.addEventListener('click', resetEditorCode);
    }

    // Tab key support in editor
    if (editor) {
        editor.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = editor.selectionStart;
                const end = editor.selectionEnd;
                editor.value = editor.value.substring(0, start) + '    ' + editor.value.substring(end);
                editor.selectionStart = editor.selectionEnd = start + 4;
            }
        });
    }
}

function showCodeEditor(code) {
    const panel = document.getElementById('codeEditorPanel');
    const editor = document.getElementById('inlineCodeEditor');

    if (panel && editor) {
        panel.classList.add('visible');
        panel.classList.remove('collapsed');
        editor.value = code;
    }
}

function toggleCodeEditor() {
    const panel = document.getElementById('codeEditorPanel');
    if (panel) {
        panel.classList.toggle('collapsed');
    }
}

async function reRenderFromEditor() {
    const editor = document.getElementById('inlineCodeEditor');
    if (!editor) return;

    const code = editor.value.trim();
    if (!code) {
        showToast('코드를 입력해주세요.', 'warning');
        return;
    }

    if (!code.toLowerCase().includes('architecture-beta')) {
        showToast('코드가 "architecture-beta"를 포함해야 합니다.', 'warning');
        return;
    }

    try {
        currentMermaidCode = code;
        await renderMermaidDiagram(code);
        showToast('다이어그램이 업데이트되었습니다.', 'success');

        // Also sync to manual code tab
        const mermaidCodeInput = document.getElementById('mermaidCode');
        if (mermaidCodeInput) {
            mermaidCodeInput.value = code;
        }
    } catch (error) {
        console.error('재렌더링 실패:', error);
        showToast('렌더링에 실패했습니다. 코드를 확인해주세요.', 'error');
    }
}

function resetEditorCode() {
    const editor = document.getElementById('inlineCodeEditor');
    if (editor && originalMermaidCode) {
        editor.value = originalMermaidCode;
        showToast('원래 코드로 복원되었습니다.', 'info');
    }
}

// Share functionality
function shareDiagram() {
    if (!currentDiagramId) {
        showToast('공유하려면 먼저 AI로 다이어그램을 생성하세요.', 'warning');
        return;
    }

    const shareUrl = `${window.location.origin}${window.location.pathname}?share=${currentDiagramId}`;

    navigator.clipboard.writeText(shareUrl).then(() => {
        showToast('공유 링크가 클립보드에 복사되었습니다!', 'success');
    }).catch(() => {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = shareUrl;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showToast('공유 링크가 클립보드에 복사되었습니다!', 'success');
        } catch {
            showToast('링크 복사에 실패했습니다. URL을 직접 복사해주세요.', 'error');
            prompt('공유 링크:', shareUrl);
        }
        document.body.removeChild(textArea);
    });
}

async function checkSharedDiagram() {
    const params = new URLSearchParams(window.location.search);
    const sharedId = params.get('share');

    if (!sharedId) return;

    console.log('공유 다이어그램 로드:', sharedId);

    // Show loading
    switchDiagramTab('diagram-view');
    showLoading(false);

    try {
        const API_BASE_URL = getApiBaseUrl();
        const response = await fetch(`${API_BASE_URL}/diagrams/${sharedId}`);

        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('공유된 다이어그램을 찾을 수 없습니다. 삭제되었거나 잘못된 링크입니다.');
            }
            throw new Error(`다이어그램 로드 실패 (${response.status})`);
        }

        const data = await response.json();

        currentMermaidCode = data.mermaid_code;
        currentDiagramId = sharedId;
        originalMermaidCode = data.mermaid_code;

        await renderMermaidDiagram(data.mermaid_code);
        showDiagramActions();

        // Populate manual code editor
        const mermaidCodeInput = document.getElementById('mermaidCode');
        if (mermaidCodeInput) {
            mermaidCodeInput.value = data.mermaid_code;
        }

        showToast('공유된 다이어그램을 불러왔습니다.', 'success');

    } catch (error) {
        console.error('공유 다이어그램 로드 실패:', error);
        showError(`${error.message}`);
    }
}

// Toast notification
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;

    toast.textContent = message;
    toast.className = `toast toast-${type} toast-show`;

    setTimeout(() => {
        toast.classList.remove('toast-show');
    }, 3000);
}

// Start app when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeApp);