// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initTooltips();

    // Initialize file uploads
    initFileUploads();

    // Initialize audio recorder
    initAudioRecorder();

    // Initialize signature pad
    initSignaturePad();

    // Initialize student search
    initStudentSearch();

    // Add animations to cards
    addCardAnimations();

    // Handle form submissions
    handleFormSubmissions();
});

// ===== Tooltip Initialization =====
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// ===== File Upload Handling =====
function initFileUploads() {
    const fileUploadAreas = document.querySelectorAll('.file-upload-area');

    fileUploadAreas.forEach(area => {
        const fileInput = area.querySelector('input[type="file"]');

        if (!fileInput) return;

        // Click on area triggers file input
        area.addEventListener('click', () => fileInput.click());

        // Handle drag and drop
        area.addEventListener('dragover', (e) => {
            e.preventDefault();
            area.classList.add('dragover');
        });

        area.addEventListener('dragleave', () => {
            area.classList.remove('dragover');
        });

        area.addEventListener('drop', (e) => {
            e.preventDefault();
            area.classList.remove('dragover');

            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                updateFileList(fileInput);
            }
        });

        // Handle file selection
        fileInput.addEventListener('change', () => updateFileList(fileInput));
    });
}

function updateFileList(fileInput) {
    const container = fileInput.closest('.file-upload-container');
    if (!container) return;

    const fileList = container.querySelector('.file-list');
    if (!fileList) return;

    // Clear existing list
    fileList.innerHTML = '';

    // Add new files
    Array.from(fileInput.files).forEach(file => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';

        const icon = getFileIcon(file.type);

        fileItem.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="file-icon">
                    <i class="bi ${icon}"></i>
                </div>
                <div>
                    <div class="file-name">${file.name}</div>
                    <small class="text-muted">${formatFileSize(file.size)}</small>
                </div>
            </div>
            <button type="button" class="btn btn-sm btn-outline-danger remove-file">
                <i class="bi bi-x"></i>
            </button>
        `;

        fileItem.querySelector('.remove-file').addEventListener('click', () => {
            fileInput.value = '';
            fileItem.remove();
        });

        fileList.appendChild(fileItem);
    });
}

function getFileIcon(fileType) {
    if (fileType.includes('audio')) return 'bi-file-music';
    if (fileType.includes('pdf')) return 'bi-file-pdf';
    if (fileType.includes('image')) return 'bi-file-image';
    if (fileType.includes('video')) return 'bi-file-play';
    return 'bi-file-earmark';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// ===== Audio Recorder =====
function initAudioRecorder() {
    const recorderContainer = document.querySelector('#audioRecorder');
    if (!recorderContainer) return;

    const startBtn = recorderContainer.querySelector('#startRecording');
    const stopBtn = recorderContainer.querySelector('#stopRecording');
    const statusText = recorderContainer.querySelector('#recordingStatus');
    const audioPreview = recorderContainer.querySelector('#audioPreview');
    const audioDataInput = recorderContainer.querySelector('#audioData');

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    startBtn.addEventListener('click', startRecording);
    stopBtn.addEventListener('click', stopRecording);

    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                const audioUrl = URL.createObjectURL(audioBlob);

                // Update preview
                audioPreview.src = audioUrl;
                audioPreview.classList.remove('d-none');

                // Convert to base64 for form submission
                const reader = new FileReader();
                reader.onload = function() {
                    audioDataInput.value = reader.result;
                };
                reader.readAsDataURL(audioBlob);

                // Stop all tracks
                mediaRecorder.stream.getTracks().forEach(track => track.stop());

                updateRecordingStatus('Recording saved successfully!', 'success');
                startBtn.disabled = false;
                stopBtn.disabled = true;
            };

            mediaRecorder.start();
            isRecording = true;

            updateRecordingStatus('Recording...', 'recording');
            startBtn.disabled = true;
            stopBtn.disabled = false;

        } catch (error) {
            console.error('Error starting recording:', error);
            updateRecordingStatus('Microphone access denied or not available', 'error');
        }
    }

    function stopRecording() {
        if (mediaRecorder && isRecording) {
            mediaRecorder.stop();
            isRecording = false;
        }
    }

    function updateRecordingStatus(message, type) {
        if (!statusText) return;

        statusText.textContent = message;
        statusText.className = 'recording-status';

        switch(type) {
            case 'recording':
                statusText.classList.add('text-danger');
                statusText.innerHTML = '<span class="recording-indicator"></span>' + message;
                break;
            case 'success':
                statusText.classList.add('text-success');
                break;
            case 'error':
                statusText.classList.add('text-danger');
                break;
            default:
                statusText.classList.add('text-muted');
        }
    }
}

// ===== Signature Pad =====
function initSignaturePad() {
    const signatureContainer = document.querySelector('#signaturePad');
    if (!signatureContainer) return;

    const canvas = signatureContainer.querySelector('canvas');
    if (!canvas) return;

    const signatureDataInput = document.querySelector('#signatureData');
    const clearBtn = document.querySelector('#clearSignature');
    const saveBtn = document.querySelector('#saveSignature');

    // Set canvas size
    canvas.width = signatureContainer.offsetWidth;
    canvas.height = signatureContainer.offsetHeight;

    const signaturePad = new SignaturePad(canvas, {
        backgroundColor: 'rgb(255, 255, 255)',
        penColor: 'rgb(0, 0, 0)',
        minWidth: 1,
        maxWidth: 3
    });

    // Handle window resize
    window.addEventListener('resize', function() {
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        canvas.width = canvas.offsetWidth * ratio;
        canvas.height = canvas.offsetHeight * ratio;
        canvas.getContext('2d').scale(ratio, ratio);
        signaturePad.clear();
    });

    // Clear signature
    if (clearBtn) {
        clearBtn.addEventListener('click', () => signaturePad.clear());
    }

    // Save signature
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            if (signaturePad.isEmpty()) {
                alert('Please provide your signature');
                return;
            }

            if (signatureDataInput) {
                signatureDataInput.value = signaturePad.toDataURL();
                alert('Signature saved successfully!');
            }
        });
    }

    // Auto-save on form submission
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            const signatureField = form.querySelector('#signatureData');
            if (signatureField && !signaturePad.isEmpty()) {
                signatureField.value = signaturePad.toDataURL();
            }
        });
    });
}

// ===== Student Search =====
function initStudentSearch() {
    const searchInput = document.querySelector('#studentSearch');
    if (!searchInput) return;

    const studentList = document.querySelector('#studentList');
    if (!studentList) return;

    searchInput.addEventListener('input', debounce(function(e) {
        const searchTerm = e.target.value.toLowerCase();
        const students = studentList.querySelectorAll('.student-item');

        students.forEach(student => {
            const studentName = student.textContent.toLowerCase();
            if (studentName.includes(searchTerm)) {
                student.style.display = '';
            } else {
                student.style.display = 'none';
            }
        });
    }, 300));
}

// ===== Card Animations =====
function addCardAnimations() {
    const cards = document.querySelectorAll('.card');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1
    });

    cards.forEach(card => {
        observer.observe(card);
    });
}

// ===== Form Submission Handling =====
function handleFormSubmissions() {
    const forms = document.querySelectorAll('form');

    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="loading-spinner"></span> Processing...';
            }

            // Validate required fields
            const requiredFields = this.querySelectorAll('[required]');
            let isValid = true;

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    field.classList.add('is-invalid');
                    isValid = false;
                } else {
                    field.classList.remove('is-invalid');
                }
            });

            if (!isValid) {
                e.preventDefault();
                alert('Please fill in all required fields');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = submitBtn.dataset.originalText || 'Submit';
                }
            }
        });
    });
}

// ===== Utility Functions =====
function debounce(func, wait) {
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

function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer') || createToastContainer();

    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');

    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi ${getToastIcon(type)} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;

    toastContainer.appendChild(toast);

    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 5000
    });

    bsToast.show();

    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

function getToastIcon(type) {
    switch(type) {
        case 'success': return 'bi-check-circle';
        case 'danger': return 'bi-exclamation-circle';
        case 'warning': return 'bi-exclamation-triangle';
        default: return 'bi-info-circle';
    }
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1060';
    document.body.appendChild(container);
    return container;
}

// ===== API Helper Functions =====
async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Request failed');
        }

        return result;
    } catch (error) {
        console.error('API request failed:', error);
        showToast(error.message, 'danger');
        throw error;
    }
}

// ===== Real-time Updates =====
function initRealTimeUpdates() {
    // Check for new notes every 30 seconds
    if (window.location.pathname.includes('/dashboard')) {
        setInterval(checkForNewNotes, 30000);
    }
}

async function checkForNewNotes() {
    try {
        const response = await fetch('/api/check-new-notes');
        const data = await response.json();

        if (data.hasNewNotes) {
            showToast('New notes are available!', 'info');
        }
    } catch (error) {
        // Silent fail for background checks
    }
}

// ===== Export Functions for Global Use =====
window.appUtils = {
    showToast,
    apiRequest,
    formatFileSize,
    debounce
};

// Initialize real-time updates when DOM is loaded
initRealTimeUpdates();