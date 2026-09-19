/* Trip source-file assets panel. */

(function () {
    'use strict';

    var _link = null;

    function _formatBytes(bytes) {
        if (!bytes) return '';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function _iconForMime(mime) {
        if (!mime) return 'fa-file';
        if (mime.startsWith('image/')) return 'fa-image';
        if (mime === 'application/pdf') return 'fa-file-pdf';
        if (mime.includes('spreadsheet') || mime.includes('excel')) return 'fa-file-excel';
        if (mime.includes('word') || mime.includes('document')) return 'fa-file-word';
        if (mime === 'application/json') return 'fa-file-code';
        return 'fa-file-alt';
    }

    function _removeCard(card) {
        card.style.opacity = '0';
        setTimeout(function () {
            card.remove();
            _updateCount();
        }, 200);
    }

    function _updateCount() {
        var list = document.getElementById('assets-list');
        var countEl = document.getElementById('assets-count');
        if (!list || !countEl) return;
        var n = list.querySelectorAll('.asset-card').length;
        countEl.textContent = n > 0 ? '(' + n + ')' : '';
    }

    function _buildCard(asset) {
        var card = document.createElement('div');
        card.className = 'asset-card';
        card.dataset.id = asset.id;

        if (asset.is_image) {
            var img = document.createElement('img');
            img.src = '/api/trips/' + encodeURIComponent(_link) + '/assets/' + asset.id + '/file';
            img.className = 'asset-thumb';
            img.alt = asset.original_name;
            card.appendChild(img);
        } else {
            var icon = document.createElement('i');
            icon.className = 'fas ' + _iconForMime(asset.mime_type) + ' asset-icon';
            card.appendChild(icon);
        }

        var info = document.createElement('div');
        info.className = 'asset-info';

        var name = document.createElement('span');
        name.className = 'asset-name';
        name.textContent = asset.original_name;
        info.appendChild(name);

        if (asset.file_size) {
            var size = document.createElement('span');
            size.className = 'asset-size';
            size.textContent = _formatBytes(asset.file_size);
            info.appendChild(size);
        }

        card.appendChild(info);

        var del = document.createElement('button');
        del.className = 'asset-delete';
        del.title = 'Remove source file';
        del.setAttribute('aria-label', 'Remove ' + asset.original_name);
        del.innerHTML = '<i class="fas fa-times"></i>';
        del.addEventListener('click', function () {
            fetch('/api/trips/' + encodeURIComponent(_link) + '/assets/' + asset.id, {method: 'DELETE'})
                .then(function (r) {
                    if (r.ok) _removeCard(card);
                })
                .catch(function (err) { console.error('delete asset', err); });
        });
        card.appendChild(del);

        return card;
    }

    function _renderAssets(assets) {
        var list = document.getElementById('assets-list');
        if (!list) return;
        list.innerHTML = '';
        assets.forEach(function (a) { list.appendChild(_buildCard(a)); });
        _updateCount();
    }

    function initAssets(link) {
        _link = link;
        fetch('/api/trips/' + encodeURIComponent(link) + '/assets')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (data && data.assets) _renderAssets(data.assets);
            })
            .catch(function (err) { console.error('load assets', err); });
    }

    window.initAssets = initAssets;
})();
