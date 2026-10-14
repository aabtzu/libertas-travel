(function () {
    var mapEl = document.getElementById('rec-map');
    if (!mapEl) return;
    var markers = JSON.parse(mapEl.dataset.markers || '[]');
    initRecommendationMap('rec-map', markers);

    var saveBtn = document.getElementById('rec-save-btn');
    if (saveBtn) {
        var title = mapEl.dataset.title || '';
        saveBtn.addEventListener('click', function () {
            showSaveToTripModal(this.dataset.source, title, this);
        });
    }
})();
