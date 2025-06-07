document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    const fileName = document.getElementById('file-name');
    const uploadBtn = document.getElementById('upload-btn');
    const uploadSection = document.getElementById('upload-section');
    const progressSection = document.getElementById('progress-section');
    const resultSection = document.getElementById('result-section');
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');
    const progressTime = document.getElementById('progress-time');
    const chunkContainer = document.getElementById('chunk-container');
    const downloadPdfBtn = document.getElementById('download-pdf-btn');
    const downloadTextBtn = document.getElementById('download-text-btn');
    const newTranslationBtn = document.getElementById('new-translation-btn');
    const translationPreview = document.getElementById('translation-preview');
    const pagesPerChunkSlider = document.getElementById('pages-per-chunk');
    const pagesPerChunkValue = document.getElementById('pages-per-chunk-value');
    const helpToggleBtn = document.getElementById('toggle-help');
    const helpContent = document.getElementById('help-content');
    const apiKeyInput = document.getElementById('api-key');

    // Variables
    let selectedFile = null;
    let currentJobId = null;
    let progressInterval = null;
    let translatedChunks = {};
    let pagesPerChunk = 10; // Default value

    // Initialize help toggle
    helpToggleBtn.addEventListener('click', function() {
        helpContent.classList.toggle('hidden');
        const icon = helpToggleBtn.querySelector('i');
        if (helpContent.classList.contains('hidden')) {
            icon.classList.remove('fa-chevron-up');
            icon.classList.add('fa-chevron-down');
        } else {
            icon.classList.remove('fa-chevron-down');
            icon.classList.add('fa-chevron-up');
        }
    });

    // Initialize pages per chunk slider
    pagesPerChunkSlider.addEventListener('input', function() {
        pagesPerChunk = parseInt(this.value);
        pagesPerChunkValue.textContent = pagesPerChunk;
    });

    // Event Listeners for drag and drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    function highlight() {
        dropArea.classList.add('drag-over');
    }

    function unhighlight() {
        dropArea.classList.remove('drag-over');
    }

    // Handle dropped files
    dropArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // Handle file selection via input
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length > 0) {
            const file = files[0];
            if (file.type === 'application/pdf') {
                selectedFile = file;
                fileName.textContent = file.name;
                uploadBtn.disabled = false;
            } else {
                alert('لطفاً فقط فایل PDF انتخاب کنید.');
                resetFileInput();
            }
        }
    }

    function resetFileInput() {
        fileInput.value = '';
        fileName.textContent = '';
        selectedFile = null;
        uploadBtn.disabled = true;
    }

    // Handle upload button click
    uploadBtn.addEventListener('click', uploadFile);

    function uploadFile() {
        if (!selectedFile) {
            alert('لطفاً ابتدا یک فایل PDF انتخاب کنید.');
            return;
        }
        
        const apiKey = apiKeyInput.value.trim();
        if (!apiKey) {
            alert('لطفاً کلید API Gemini را وارد کنید.');
            apiKeyInput.focus();
            return;
        }

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('pages_per_chunk', pagesPerChunk);
        formData.append('api_key', apiKey);

        // Show loading state
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> در حال آپلود...';

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            currentJobId = data.job_id;
            showProgressSection();
            startProgressTracking();
        })
        .catch(error => {
            alert('خطا در آپلود فایل: ' + error.message);
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="fas fa-play"></i> شروع ترجمه';
        });
    }

    function showProgressSection() {
        uploadSection.classList.add('hidden');
        progressSection.classList.remove('hidden');
        resultSection.classList.add('hidden');
    }

    function showResultSection() {
        uploadSection.classList.add('hidden');
        progressSection.classList.add('hidden');
        resultSection.classList.remove('hidden');
    }

    function startProgressTracking() {
        // Clear any existing interval
        if (progressInterval) {
            clearInterval(progressInterval);
        }

        // Initialize chunks container
        chunkContainer.innerHTML = '';
        translatedChunks = {};

        // Start checking progress
        checkProgress();
        progressInterval = setInterval(checkProgress, 3000); // Check every 3 seconds
    }

    function checkProgress() {
        if (!currentJobId) return;

        fetch(`/progress/${currentJobId}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }

                // Update progress bar
                const progress = data.progress || 0;
                progressBar.style.width = `${progress}%`;
                progressPercent.textContent = `${Math.round(progress)}%`;

                // Update time estimation
                if (data.remaining_time) {
                    const minutes = Math.floor(data.remaining_time / 60);
                    const seconds = Math.round(data.remaining_time % 60);
                    progressTime.textContent = `زمان باقیمانده: ${minutes} دقیقه و ${seconds} ثانیه`;
                } else {
                    progressTime.textContent = 'زمان باقیمانده: در حال محاسبه...';
                }

                // Update chunks
                updateChunks(data.chunks);

                // Check if translation is complete
                if (data.status === 'completed') {
                    clearInterval(progressInterval);
                    finishTranslation(data);
                } else if (data.status === 'failed') {
                    clearInterval(progressInterval);
                    alert('خطا در ترجمه: ' + (data.error || 'خطای نامشخص'));
                }
            })
            .catch(error => {
                console.error('Error checking progress:', error);
            });
    }

    function updateChunks(chunks) {
    if (!chunks || !Array.isArray(chunks)) return;

    chunks.forEach(chunk => {
        const chunkId = `chunk-${chunk.chunk_index}`;
        let chunkElement = document.getElementById(chunkId);

        // If chunk element doesn't exist, create it
        if (!chunkElement) {
            chunkElement = document.createElement('div');
            chunkElement.id = chunkId;
            chunkElement.className = 'chunk';
            
            // Create chunk header
            const chunkHeader = document.createElement('div');
            chunkHeader.className = 'chunk-header';
            
            // Create chunk title
            const chunkTitle = document.createElement('div');
            chunkTitle.className = 'chunk-title';
            chunkTitle.textContent = `بخش ${chunk.chunk_index + 1} (صفحات ${chunk.pages.join(', ')})`;
            
            // Create chunk status icon
            const chunkStatus = document.createElement('div');
            chunkStatus.className = 'chunk-status';
            chunkStatus.id = `${chunkId}-status`;
            
            // Add elements to chunk header
            chunkHeader.appendChild(chunkTitle);
            chunkHeader.appendChild(chunkStatus);
            
            // Create chunk content for translation
            const chunkContent = document.createElement('div');
            chunkContent.className = 'chunk-translation';
            chunkContent.id = `${chunkId}-translation`;
            
            // Add elements to chunk
            chunkElement.appendChild(chunkHeader);
            chunkElement.appendChild(chunkContent);
            
            // Add to container
            chunkContainer.appendChild(chunkElement);
        }

        // Update chunk status
        const statusElement = document.getElementById(`${chunkId}-status`);
        const translationElement = document.getElementById(`${chunkId}-translation`);
        
        let statusClass = '';
        let statusIcon = '';
        let tooltipText = '';
        
        switch (chunk.status) {
            case 'pending':
                statusClass = 'status-pending';
                statusIcon = '<i class="fas fa-clock"></i>';
                tooltipText = 'در انتظار';
                translationElement.textContent = 'در انتظار شروع ترجمه...';
                break;
            case 'in_progress':
                statusClass = 'status-in-progress';
                statusIcon = '<i class="fas fa-spinner fa-spin"></i>';
                tooltipText = 'در حال ترجمه';
                translationElement.textContent = 'در حال ترجمه...';
                break;
            case 'completed':
                statusClass = 'status-completed';
                statusIcon = '<i class="fas fa-check"></i>';
                tooltipText = 'تکمیل شده';
                // Store and display translated text
                if (chunk.translated_text) {
                    translatedChunks[chunk.chunk_index] = chunk.translated_text;
                    translationElement.textContent = chunk.translated_text;
                }
                break;
            case 'failed':
                statusClass = 'status-failed';
                statusIcon = '<i class="fas fa-exclamation-triangle"></i>';
                tooltipText = 'خطا: ' + (chunk.error || 'خطای نامشخص');
                translationElement.textContent = 'خطا در ترجمه: ' + (chunk.error || 'خطای نامشخص');
                break;
        }
        
        // Update chunk element
        chunkElement.className = `chunk ${statusClass}`;
        chunkElement.title = tooltipText;
        statusElement.innerHTML = statusIcon;
    });
}

    function finishTranslation(data) {
        // Show result section
        showResultSection();

        // Set up download buttons
        if (data.pdf_url) {
            downloadPdfBtn.addEventListener('click', () => {
                window.location.href = data.pdf_url;
            });
        } else {
            downloadPdfBtn.disabled = true;
        }

        // Set up text download
        downloadTextBtn.addEventListener('click', () => {
            fetch(`/text/${currentJobId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        throw new Error(data.error);
                    }
                    
                    // Create and download text file
                    const blob = new Blob([data.text], { type: 'text/plain;charset=utf-8' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'translated_document.txt';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                })
                .catch(error => {
                    alert('خطا در دریافت متن: ' + error.message);
                });
        });

        // Show preview of translated text
        let allText = '';
        const sortedChunks = Object.keys(translatedChunks)
            .sort((a, b) => parseInt(a) - parseInt(b));
        
        sortedChunks.forEach(chunkIndex => {
            allText += translatedChunks[chunkIndex] + '\n\n';
        });
        
        translationPreview.textContent = allText;

        // Update result section with icons
        downloadPdfBtn.innerHTML = '<i class="fas fa-file-pdf"></i> دانلود PDF';
        downloadTextBtn.innerHTML = '<i class="fas fa-file-alt"></i> دانلود متن';
        newTranslationBtn.innerHTML = '<i class="fas fa-redo-alt"></i> ترجمه جدید';
        
        // Set up new translation button
        newTranslationBtn.addEventListener('click', resetTranslation);
    }

    function resetTranslation() {
        // Reset all variables and UI
        currentJobId = null;
        selectedFile = null;
        translatedChunks = {};
        resetFileInput();
        
        // Clear intervals
        if (progressInterval) {
            clearInterval(progressInterval);
            progressInterval = null;
        }
        
        // Reset progress UI
        progressBar.style.width = '0%';
        progressPercent.textContent = '0%';
        progressTime.textContent = 'زمان باقیمانده: در حال محاسبه...';
        chunkContainer.innerHTML = '';
        translationPreview.textContent = '';
        
        // Show upload section
        uploadSection.classList.remove('hidden');
        progressSection.classList.add('hidden');
        resultSection.classList.add('hidden');
        
        // Reset buttons
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-play"></i> شروع ترجمه';
        
        // Reset pages per chunk slider to default
        pagesPerChunkSlider.value = 10;
        pagesPerChunkValue.textContent = '10';
        pagesPerChunk = 10;
        
        // Remove event listeners from result buttons to prevent multiple bindings
        downloadPdfBtn.replaceWith(downloadPdfBtn.cloneNode(true));
        downloadTextBtn.replaceWith(downloadTextBtn.cloneNode(true));
        newTranslationBtn.replaceWith(newTranslationBtn.cloneNode(true));
        
        // Re-assign DOM references after cloning
        downloadPdfBtn = document.getElementById('download-pdf-btn');
        downloadTextBtn = document.getElementById('download-text-btn');
        newTranslationBtn = document.getElementById('new-translation-btn');
        
        // Add event listener to new button
        newTranslationBtn.addEventListener('click', resetTranslation);
    }
});