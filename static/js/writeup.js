(function () {
    var mapEl = document.getElementById('writeup-map');
    if (!mapEl) return;
    var markers = JSON.parse(mapEl.dataset.markers || '[]');
    initRecommendationMap('writeup-map', markers);

    var saveBtn = document.getElementById('rec-save-btn');
    if (saveBtn && mapEl.dataset.hasSaveBtn === 'true') {
        var title = mapEl.dataset.title || '';
        saveBtn.addEventListener('click', function () {
            showSaveToTripModal(this.dataset.source, title, this);
        });
    }
})();
