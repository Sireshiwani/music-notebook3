// static/js/note_editor.js

/**
 * Pick a MediaRecorder mime type that works on this device (iOS/Safari use MP4/AAC; Chrome often WebM).
 */
function pickRecorderMimeType() {
    if (typeof MediaRecorder === 'undefined' || !MediaRecorder.isTypeSupported) {
        return '';
    }
    const candidates = [
        'audio/mp4',
        'audio/mp4; codecs=mp4a.40.2',
        'audio/webm; codecs=opus',
        'audio/webm',
    ];
    for (const t of candidates) {
        if (MediaRecorder.isTypeSupported(t)) {
            return t;
        }
    }
    return '';
}

function buildRecorderOptions(mimeType) {
    const opts = {};
    if (!mimeType) {
        return opts;
    }
    opts.mimeType = mimeType;
    if (mimeType.includes('webm')) {
        opts.audioBitsPerSecond = 64000;
    }
    return opts;
}

/** Safari / iOS needs MP4 first; Chrome / Android records reliably with WebM/Opus (MP4 can report supported but stay inactive). */
function isAppleTouchDevice() {
    const ua = navigator.userAgent || '';
    if (/iPhone|iPad|iPod/i.test(ua)) return true;
    if (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1) return true;
    return false;
}

/**
 * Try supported mime types until MediaRecorder accepts one (Safari/iOS differs by version).
 */
function createBestMediaRecorder(stream) {
    const appleFirst = [
        'audio/mp4',
        'audio/mp4; codecs=mp4a.40.2',
        'audio/webm; codecs=opus',
        'audio/webm',
    ];
    const chromeFirst = [
        'audio/webm; codecs=opus',
        'audio/webm',
        'audio/mp4',
        'audio/mp4; codecs=mp4a.40.2',
    ];
    const order = isAppleTouchDevice() ? appleFirst : chromeFirst;

    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported) {
        for (const mime of order) {
            if (!MediaRecorder.isTypeSupported(mime)) continue;
            try {
                const opts = buildRecorderOptions(mime);
                return new MediaRecorder(stream, opts);
            } catch (_) {
                /* try next mime */
            }
        }
    }
    return new MediaRecorder(stream);
}

class NoteEditor {
    constructor(config) {
        this.config = config;

        // Audio recording state
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.isPaused = false;
        this.recordingStartTime = null;
        this.timerInterval = null;
        this.totalRecordingTime = 0;
        this.audioAnalyser = null;
        this.audioContext = null;
        this.audioSource = null;
        this.visualizerBars = [];
        /** @type {string} mime type actually used by MediaRecorder (for Blob / upload) */
        this.recordedMimeType = 'audio/webm';

        // File upload state
        this.files = {
            audio: null,
            document: null,
            image: null
        };

        // Form state
        this.isProcessing = false;
        this.totalFileSize = 0;
    }

    init() {
        this.initAudioRecording();
        this.initFileUploads();
        this.initFormValidation();
        this.initWordCount();
        this.initDragAndDrop();
        this.updateSummary();
    }

    initAudioRecording() {
        const config = this.config.audioRecording;

        // Get DOM elements
        this.startBtn = document.getElementById(config.startBtnId);
        this.stopBtn = document.getElementById(config.stopBtnId);
        this.pauseBtn = document.getElementById(config.pauseBtnId);
        this.resumeBtn = document.getElementById(config.resumeBtnId);
        this.deleteBtn = document.getElementById(config.deleteBtnId);
        this.visualizer = document.getElementById(config.visualizerId);
        this.timerDisplay = document.getElementById(config.timerId);
        this.fileSizeDisplay = document.getElementById(config.fileSizeId);
        this.statusText = document.getElementById(config.statusTextId);
        this.spinner = document.getElementById(config.spinnerId);
        this.progressBar = document.getElementById(config.progressBarId);
        this.audioDataInput = document.getElementById(config.dataInputId);
        this.compressCheckbox = document.getElementById(config.compressCheckboxId);

        // Create visualizer bars
        this.createVisualizerBars();

        // Debounced pointerdown + click — Android fires both; Space/keyboard uses click only.
        let lastStartAt = 0;
        const tryStart = () => {
            const now = Date.now();
            if (now - lastStartAt < 600) return;
            lastStartAt = now;
            this.startRecording();
        };
        this.startBtn.addEventListener('pointerdown', (e) => {
            if (e.button !== 0) return;
            tryStart();
        });
        this.startBtn.addEventListener('click', () => tryStart());

        this.stopBtn.addEventListener('click', () => this.stopRecording());
        this.pauseBtn.addEventListener('click', () => this.pauseRecording());
        this.resumeBtn.addEventListener('click', () => this.resumeRecording());
        this.deleteBtn.addEventListener('click', () => this.deleteRecording());

        // Initialize Web Audio API for visualizer
        this.initAudioAnalyser();
    }

    createVisualizerBars() {
        if (!this.visualizer) return;

        this.visualizer.innerHTML = '';
        this.visualizerBars = [];

        const barCount = 40;
        for (let i = 0; i < barCount; i++) {
            const bar = document.createElement('div');
            bar.className = 'bar';
            bar.style.left = `${(i / barCount) * 100}%`;
            bar.style.height = '0%';
            this.visualizer.appendChild(bar);
            this.visualizerBars.push(bar);
        }
    }

    initAudioAnalyser() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        } catch (error) {
            console.warn('Web Audio API not supported:', error);
        }
    }

    async startRecording() {
        if (this.isRecording) {
            return;
        }

        if (typeof MediaRecorder === 'undefined') {
            this.showMessage(
                'Recording is not supported in this browser. Try Safari or Chrome, or update iOS.',
                'danger'
            );
            return;
        }

        let stream = null;
        try {
            // iOS Safari: user activation for the mic must not be preceded by another await
            // (e.g. AudioContext.resume). Request the mic first, then resume the visualizer context.
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            try {
                if (this.audioContext && this.audioContext.state === 'suspended') {
                    await this.audioContext.resume();
                }
            } catch (_) {
                /* visualizer-only; recording still works */
            }

            this.mediaRecorder = createBestMediaRecorder(stream);
            this.recordedMimeType =
                this.mediaRecorder.mimeType ||
                pickRecorderMimeType() ||
                'audio/webm';

            this.audioChunks = [];
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                    this.updateFileSize();
                }
            };

            this.mediaRecorder.onerror = (event) => {
                console.error('MediaRecorder error:', event.error);
                const msg =
                    event.error && event.error.message
                        ? event.error.message
                        : 'Recording failed on this device';
                this.showMessage(msg, 'danger');
            };

            this.mediaRecorder.onstop = () => {
                this.saveRecording();
                stream.getTracks().forEach((track) => track.stop());
            };

            try {
                if (this.audioContext && this.analyser) {
                    this.audioSource = this.audioContext.createMediaStreamSource(stream);
                    this.audioSource.connect(this.analyser);
                    this.startVisualizer();
                }
            } catch (visErr) {
                console.warn('Audio visualizer skipped:', visErr);
            }

            // Frequent slices — some mobile browsers omit chunks until stop if the slice is too large
            this.mediaRecorder.start(250);

            // Android Chrome: MP4 mime can leave recorder stuck "inactive"; verify we entered "recording"
            await new Promise((r) => setTimeout(r, 50));
            if (this.mediaRecorder.state !== 'recording') {
                this.mediaRecorder.onstop = null;
                this.mediaRecorder.ondataavailable = null;
                try {
                    this.mediaRecorder.stop();
                } catch (_) {
                    /* ignore */
                }
                this.mediaRecorder = null;
                stream.getTracks().forEach((t) => t.stop());
                this.showMessage(
                    'Recorder did not start on this browser. Try Chrome, or update Android WebView.',
                    'danger'
                );
                return;
            }

            this.isRecording = true;
            this.isPaused = false;
            this.recordingStartTime = Date.now();

            this.updateRecordingUI(true);
            this.startTimer();
        } catch (error) {
            if (stream) {
                stream.getTracks().forEach((t) => t.stop());
            }
            console.error('Recording error:', error);
            let msg = 'Microphone unavailable';
            if (error && error.name === 'NotAllowedError') {
                msg =
                    'Microphone blocked — tap the lock/info icon in the address bar and allow the microphone.';
            } else if (error && error.name === 'NotFoundError') {
                msg = 'No microphone found on this device.';
            } else if (error && error.message) {
                msg = error.message;
            }
            this.showMessage(msg, 'danger');
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.updateRecordingUI(false);
            this.stopTimer();
            this.stopVisualizer();
        }
    }

    pauseRecording() {
        if (this.mediaRecorder && this.isRecording && !this.isPaused) {
            this.mediaRecorder.pause();
            this.isPaused = true;
            this.pauseTimer();
            this.updatePauseUI(true);
        }
    }

    resumeRecording() {
        if (this.mediaRecorder && this.isRecording && this.isPaused) {
            this.mediaRecorder.resume();
            this.isPaused = false;
            this.resumeTimer();
            this.updatePauseUI(false);
        }
    }

    deleteRecording() {
        this.audioChunks = [];
        this.files.audio = null;
        this.audioDataInput.value = '';

        // Hide playback
        document.getElementById('audioPlaybackContainer').classList.add('d-none');

        // Reset UI
        this.updateRecordingUI(false);
        this.timerDisplay.textContent = '00:00';
        this.fileSizeDisplay.textContent = '0 MB';
        this.totalRecordingTime = 0;

        // Show success message
        this.showMessage('Recording deleted', 'success');

        this.updateSummary();
    }

    async saveRecording() {
        if (this.audioChunks.length === 0) {
            this.showMessage('No recording to save', 'warning');
            return;
        }

        // Show processing
        this.spinner.classList.remove('d-none');
        this.progressBar.classList.remove('d-none');
        this.updateProgress(30, 'Processing audio...');

        try {
            // Combine chunks (type must match what the browser recorded)
            const blobType = this.recordedMimeType || 'audio/webm';
            const audioBlob = new Blob(this.audioChunks, { type: blobType });

            // Check if compression is enabled
            const compress = this.compressCheckbox ? this.compressCheckbox.checked : true;
            let finalBlob = audioBlob;

            if (compress) {
                this.updateProgress(50, 'Compressing audio...');
                finalBlob = await this.compressAudio(audioBlob);
            }

            // Convert to base64
            this.updateProgress(70, 'Encoding audio...');
            const base64Data = await this.blobToBase64(finalBlob);

            // Save to form
            this.audioDataInput.value = base64Data;
            this.files.audio = {
                blob: finalBlob,
                size: finalBlob.size,
                type: finalBlob.type
            };

            // Show playback
            const audioUrl = URL.createObjectURL(finalBlob);
            const audioPlayback = document.getElementById('audioPlayback');
            audioPlayback.src = audioUrl;
            document.getElementById('audioPlaybackContainer').classList.remove('d-none');

            // Update UI
            this.updateProgress(100, 'Audio saved!');
            this.showMessage('Recording saved successfully', 'success');

            // Update summary
            this.updateSummary();

        } catch (error) {
            console.error('Save error:', error);
            this.showMessage('Failed to save recording', 'danger');
        } finally {
            setTimeout(() => {
                this.spinner.classList.add('d-none');
                this.progressBar.classList.add('d-none');
            }, 1000);
        }
    }

    async compressAudio(audioBlob) {
        // Simple compression by reducing sample rate and channels
        return new Promise((resolve) => {
            // For now, return the original blob
            // In production, you would use a library like pydub on the server
            // or implement client-side compression with Web Audio API
            resolve(audioBlob);
        });
    }

    blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    startTimer() {
        this.totalRecordingTime = 0;
        this.timerInterval = setInterval(() => {
            this.totalRecordingTime += 1;
            const mins = Math.floor(this.totalRecordingTime / 60).toString().padStart(2, '0');
            const secs = (this.totalRecordingTime % 60).toString().padStart(2, '0');
            this.timerDisplay.textContent = `${mins}:${secs}`;

            // Auto-stop after 30 minutes (safety limit)
            if (this.totalRecordingTime >= 1800) {
                this.stopRecording();
                this.showMessage('Maximum recording time (30 minutes) reached', 'warning');
            }
        }, 1000);
    }

    pauseTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    resumeTimer() {
        if (!this.timerInterval) {
            this.startTimer();
        }
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    startVisualizer() {
        if (!this.analyser) return;

        const updateVisualizer = () => {
            if (!this.isRecording || this.isPaused) return;

            this.analyser.getByteFrequencyData(this.dataArray);

            // Update bars
            this.visualizerBars.forEach((bar, index) => {
                const dataIndex = Math.floor(index * (this.dataArray.length / this.visualizerBars.length));
                const value = this.dataArray[dataIndex];
                const height = (value / 255) * 100;
                bar.style.height = `${height}%`;
                bar.style.backgroundColor = this.getBarColor(height);
            });

            requestAnimationFrame(updateVisualizer);
        };

        updateVisualizer();
    }

    stopVisualizer() {
        // Reset bars
        this.visualizerBars.forEach(bar => {
            bar.style.height = '0%';
            bar.style.backgroundColor = '#4361ee';
        });
    }

    getBarColor(height) {
        if (height > 80) return '#dc3545'; // Red for loud
        if (height > 50) return '#ffc107'; // Yellow for medium
        return '#4361ee'; // Blue for quiet
    }

    updateFileSize() {
        if (!this.audioChunks.length) return;

        const totalSize = this.audioChunks.reduce((sum, chunk) => sum + chunk.size, 0);
        const sizeMB = (totalSize / (1024 * 1024)).toFixed(2);
        this.fileSizeDisplay.textContent = `${sizeMB} MB`;
    }

    updateRecordingUI(isRecording) {
        // Show/hide elements
        this.visualizer.classList.toggle('d-none', !isRecording);

        // Enable/disable buttons
        this.startBtn.disabled = isRecording;
        this.stopBtn.disabled = !isRecording;
        this.pauseBtn.disabled = !isRecording;

        // Update status text
        if (isRecording) {
            this.statusText.textContent = 'Recording...';
            this.statusText.classList.add('text-danger');
        } else {
            this.statusText.textContent = 'Recording stopped';
            this.statusText.classList.remove('text-danger');
            this.statusText.classList.add('text-success');
        }
    }

    updatePauseUI(isPaused) {
        this.pauseBtn.disabled = isPaused;
        this.resumeBtn.disabled = !isPaused;

        if (isPaused) {
            this.statusText.textContent = 'Recording paused';
            this.statusText.classList.remove('text-danger');
            this.statusText.classList.add('text-warning');
        } else {
            this.statusText.textContent = 'Recording...';
            this.statusText.classList.remove('text-warning');
            this.statusText.classList.add('text-danger');
        }
    }

    updateProgress(percent, message) {
        if (this.progressBar) {
            const bar = this.progressBar.querySelector('.progress-bar');
            bar.style.width = `${percent}%`;
            bar.textContent = `${percent}%`;
        }

        if (message && this.statusText) {
            this.statusText.textContent = message;
        }
    }

    initFileUploads() {
        // Initialize document upload
        this.initFileUpload('document');

        // Initialize image upload
        this.initFileUpload('image');
    }

    initFileUpload(type) {
        const config = this.config.fileUploads[type];
        if (!config) return;

        // Get DOM elements
        const input = document.getElementById(config.inputId);
        const preview = document.getElementById(config.previewId);
        const uploadArea = document.getElementById(config.uploadAreaId);
        const nameDisplay = document.getElementById(config.nameId);
        const sizeDisplay = document.getElementById(config.sizeId);
        const removeBtn = document.getElementById(config.removeBtnId);
        const progressBar = document.getElementById(config.progressBarId);

        if (!input || !uploadArea) return;

        // Click on area triggers file input
        uploadArea.addEventListener('click', () => input.click());

        // Handle drag and drop
        this.initDragAndDropArea(uploadArea, input, type);

        // Handle file selection
        input.addEventListener('change', (e) => this.handleFileSelect(e, type));

        // Handle file removal
        if (removeBtn) {
            removeBtn.addEventListener('click', () => this.removeFile(type));
        }
    }

    initDragAndDropArea(area, input, type) {
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
                input.files = e.dataTransfer.files;
                this.handleFileSelect({ target: input }, type);
            }
        });
    }

    handleFileSelect(event, type) {
        const file = event.target.files[0];
        if (!file) return;

        // Validate file
        if (!this.validateFile(file, type)) {
            event.target.value = '';
            return;
        }

        // Store file
        this.files[type] = file;

        // Show preview
        this.showFilePreview(file, type);

        // Update summary
        this.updateSummary();
    }

    validateFile(file, type) {
        const maxSizes = {
            document: 50 * 1024 * 1024, // 50MB
            image: 20 * 1024 * 1024,     // 20MB
            audio: 100 * 1024 * 1024     // 100MB
        };

        const allowedExtensions = {
            document: ['pdf', 'doc', 'docx', 'txt', 'rtf'],
            image: ['jpg', 'jpeg', 'png', 'gif', 'bmp'],
            audio: ['webm', 'mp3', 'wav', 'ogg', 'm4a']
        };

        // Check file size
        if (file.size > maxSizes[type]) {
            this.showMessage(`File too large. Maximum size for ${type}s is ${maxSizes[type] / (1024 * 1024)}MB`, 'danger');
            return false;
        }

        // Check file extension
        const extension = file.name.split('.').pop().toLowerCase();
        if (!allowedExtensions[type].includes(extension)) {
            this.showMessage(`Invalid file type. Allowed types: ${allowedExtensions[type].join(', ')}`, 'danger');
            return false;
        }

        return true;
    }

    showFilePreview(file, type) {
        const config = this.config.fileUploads[type];
        if (!config) return;

        // Get DOM elements
        const preview = document.getElementById(config.previewId);
        const nameDisplay = document.getElementById(config.nameId);
        const sizeDisplay = document.getElementById(config.sizeId);

        // Update preview
        preview.classList.remove('d-none');
        nameDisplay.textContent = file.name;
        sizeDisplay.textContent = this.formatFileSize(file.size);

        // Handle image thumbnail
        if (type === 'image' && config.thumbnailId) {
            const thumbnail = document.getElementById(config.thumbnailId);
            const reader = new FileReader();
            reader.onload = (e) => {
                thumbnail.src = e.target.result;
            };
            reader.readAsDataURL(file);
        }

        // Show success message
        this.showMessage(`${type.charAt(0).toUpperCase() + type.slice(1)} uploaded successfully`, 'success');
    }

    removeFile(type) {
        const config = this.config.fileUploads[type];
        if (!config) return;

        // Clear file input
        const input = document.getElementById(config.inputId);
        input.value = '';

        // Hide preview
        const preview = document.getElementById(config.previewId);
        preview.classList.add('d-none');

        // Remove from files object
        delete this.files[type];

        // Update summary
        this.updateSummary();

        // Show message
        this.showMessage(`${type.charAt(0).toUpperCase() + type.slice(1)} removed`, 'info');
    }

    initFormValidation() {
        const form = document.getElementById(this.config.formId);
        if (!form) return;

        form.addEventListener('submit', (e) => this.handleFormSubmit(e));
    }

    async handleFormSubmit(event) {
        event.preventDefault();

        if (this.isProcessing) return;

        // Validate form
        if (!this.validateForm()) {
            return;
        }

        // Show processing modal
        this.showProcessingModal();

        try {
            this.isProcessing = true;

            // Process files (simulate upload)
            await this.processFiles();

            // Submit form
            const form = document.getElementById(this.config.formId);
            form.submit();

        } catch (error) {
            console.error('Form submission error:', error);
            this.showMessage('Error processing form. Please try again.', 'danger');
            this.hideProcessingModal();
            this.isProcessing = false;
        }
    }

    validateForm() {
        const form = document.getElementById(this.config.formId);

        // Check required fields
        const title = form.querySelector('#title');
        const content = form.querySelector('#content');

        if (!title.value.trim()) {
            this.showMessage('Please enter a lesson title', 'danger');
            title.focus();
            return false;
        }

        if (!content.value.trim()) {
            this.showMessage('Please enter lesson notes', 'danger');
            content.focus();
            return false;
        }

        return true;
    }

    async processFiles() {
        // Simulate file processing with progress updates
        const totalSteps = Object.keys(this.files).filter(key => this.files[key]).length + 2;
        let currentStep = 0;

        // Step 1: Validate all files
        this.updateProcessingProgress((++currentStep / totalSteps) * 100, 'Validating files...');
        await this.sleep(500);

        // Step 2: Process each file
        for (const [type, file] of Object.entries(this.files)) {
            if (file) {
                this.updateProcessingProgress((++currentStep / totalSteps) * 100, `Processing ${type}...`);
                await this.sleep(1000);
            }
        }

        // Final step: Saving note
        this.updateProcessingProgress(100, 'Saving note...');
        await this.sleep(500);
    }

    showProcessingModal() {
        const modal = document.getElementById(this.config.processingModalId);
        if (modal) {
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
        }
    }

    hideProcessingModal() {
        const modal = document.getElementById(this.config.processingModalId);
        if (modal) {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        }
    }

    updateProcessingProgress(percent, message) {
        const progressBar = document.getElementById(this.config.processingProgressId);
        if (progressBar) {
            progressBar.style.width = `${percent}%`;
        }
    }

    initWordCount() {
        const contentField = document.getElementById('content');
        if (!contentField) return;

        contentField.addEventListener('input', () => {
            const wordCount = this.countWords(contentField.value);
            const wordCountDisplay = document.getElementById(this.config.summary.wordCountId);
            if (wordCountDisplay) {
                wordCountDisplay.textContent = wordCount;
            }
        });
    }

    countWords(text) {
        return text.trim().split(/\s+/).filter(word => word.length > 0).length;
    }

    initDragAndDrop() {
        // Already handled in file upload sections
    }

    updateSummary() {
        // Calculate total file size
        this.totalFileSize = 0;
        let fileCount = 0;

        for (const [type, file] of Object.entries(this.files)) {
            if (file) {
                this.totalFileSize += file.size;
                fileCount++;
            }
        }

        // Add audio size
        if (this.files.audio && this.files.audio.size) {
            this.totalFileSize += this.files.audio.size;
            fileCount++;
        }

        // Update display
        const fileCountDisplay = document.getElementById(this.config.summary.fileCountId);
        const totalSizeDisplay = document.getElementById(this.config.summary.totalSizeId);

        if (fileCountDisplay) {
            fileCountDisplay.textContent = fileCount;
        }

        if (totalSizeDisplay) {
            totalSizeDisplay.textContent = this.formatFileSize(this.totalFileSize);
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    showMessage(message, type = 'info') {
        // Create toast notification
        const toast = this.createToast(message, type);
        document.body.appendChild(toast);

        // Show toast
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: 3000
        });
        bsToast.show();

        // Remove after hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    createToast(message, type) {
        const toastId = 'toast-' + Date.now();
        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `toast align-items-center text-bg-${type}`;
        toast.setAttribute('role', 'alert');

        const icons = {
            success: 'bi-check-circle',
            danger: 'bi-exclamation-circle',
            warning: 'bi-exclamation-triangle',
            info: 'bi-info-circle'
        };

        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi ${icons[type] || 'bi-info-circle'} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        return toast;
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Export for global use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NoteEditor;
}