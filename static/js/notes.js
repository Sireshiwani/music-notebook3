// static/js/notes.js

// Notes-specific functionality
class NotesManager {
    constructor() {
        this.initNoteActions();
        this.initAudioProcessing();
        this.initPDFPreview();
        this.initNoteFilters();
    }

    initNoteActions() {
        // Delete note confirmation
        document.querySelectorAll('.delete-note').forEach(btn => {
            btn.addEventListener('click', (e) => {
                if (!confirm('Are you sure you want to delete this note?')) {
                    e.preventDefault();
                }
            });
        });

        // Copy note link
        document.querySelectorAll('.copy-note-link').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const noteId = btn.dataset.noteId;
                const noteUrl = `${window.location.origin}/note/${noteId}`;

                navigator.clipboard.writeText(noteUrl).then(() => {
                    window.appUtils.showToast('Note link copied to clipboard!', 'success');
                });
            });
        });

        // Print note
        document.querySelectorAll('.print-note').forEach(btn => {
            btn.addEventListener('click', () => {
                window.print();
            });
        });
    }

    initAudioProcessing() {
        // Audio player enhancements
        const audioPlayers = document.querySelectorAll('audio');
        audioPlayers.forEach(player => {
            // Add custom controls
            player.addEventListener('play', () => {
                player.parentElement.classList.add('playing');
            });

            player.addEventListener('pause', () => {
                player.parentElement.classList.remove('playing');
            });

            // Add download button
            const source = player.querySelector('source');
            if (source) {
                const downloadBtn = document.createElement('button');
                downloadBtn.className = 'btn btn-sm btn-outline-secondary ms-2';
                downloadBtn.innerHTML = '<i class="bi bi-download"></i>';
                downloadBtn.title = 'Download audio';
                downloadBtn.addEventListener('click', () => {
                    window.location.href = source.src;
                });

                player.parentElement.appendChild(downloadBtn);
            }
        });
    }

    initPDFPreview() {
        // PDF preview modal
        document.querySelectorAll('.preview-pdf').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const pdfUrl = btn.href;

                // Create modal for PDF preview
                const modalHtml = `
                    <div class="modal fade" id="pdfPreviewModal" tabindex="-1">
                        <div class="modal-dialog modal-xl">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title">PDF Preview</h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                </div>
                                <div class="modal-body">
                                    <iframe src="${pdfUrl}" width="100%" height="600px" frameborder="0"></iframe>
                                </div>
                            </div>
                        </div>
                    </div>
                `;

                // Remove existing modal
                const existingModal = document.getElementById('pdfPreviewModal');
                if (existingModal) existingModal.remove();

                // Add new modal
                document.body.insertAdjacentHTML('beforeend', modalHtml);

                // Show modal
                const modal = new bootstrap.Modal(document.getElementById('pdfPreviewModal'));
                modal.show();
            });
        });
    }

    initNoteFilters() {
        const filterInput = document.querySelector('#noteFilter');
        if (!filterInput) return;

        filterInput.addEventListener('input', this.debounce((e) => {
            const searchTerm = e.target.value.toLowerCase();
            const notes = document.querySelectorAll('.note-item');

            notes.forEach(note => {
                const noteText = note.textContent.toLowerCase();
                if (noteText.includes(searchTerm)) {
                    note.style.display = '';
                } else {
                    note.style.display = 'none';
                }
            });
        }, 300));
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Initialize notes manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.notes-page')) {
        new NotesManager();
    }
});