document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.easymde-field').forEach(function (el) {
        new EasyMDE({
            element: el,
            spellChecker: false,
            autosave: { enabled: false },
            toolbar: [
                'bold', 'italic', 'heading', '|',
                'quote', 'unordered-list', 'ordered-list', '|',
                'link', 'horizontal-rule', '|',
                'preview', 'side-by-side', 'fullscreen'
            ],
            minHeight: '300px',
        });
    });
});
