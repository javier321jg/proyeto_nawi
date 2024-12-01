function createDiseaseInfoCard(detection) {
    if (!detection.disease_info) return '';
    
    return `
        <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
            <div class="space-y-3">
                <div class="flex items-center text-red-700">
                    <svg class="h-5 w-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                    </svg>
                    <h3 class="font-semibold">${detection.class}</h3>
                </div>
                
                <div class="text-red-600">
                    <p class="mb-2"><strong>Descripción:</strong> ${detection.disease_info.short_description}</p>
                    <p class="mb-2"><strong>Causa:</strong> ${detection.disease_info.cause}</p>
                    <p class="mb-2"><strong>Efectos:</strong> ${detection.disease_info.effects}</p>
                    <p class="text-sm"><strong>Fuente:</strong> ${detection.disease_info.source}</p>
                </div>
            </div>
        </div>
    `;
}

// Función para actualizar la visualización de detecciones
function updateDetectionsDisplay(detections) {
    const detectionsContainer = document.getElementById('detections-container');
    if (!detectionsContainer) return;
    
    detectionsContainer.innerHTML = detections.map(detection => `
        <div class="detection-item mb-4">
            <div class="flex justify-between items-center mb-2">
                <span class="font-bold">${detection.class}</span>
                <span class="confidence">Confianza: ${(detection.confidence * 100).toFixed(2)}%</span>
            </div>
            ${createDiseaseInfoCard(detection)}
        </div>
    `).join('');
}