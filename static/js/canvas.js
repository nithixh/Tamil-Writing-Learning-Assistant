// static/js/canvas.js
class CanvasManager {
    constructor(canvasId, resetBtnId, submitBtnId, feedbackAreaId, feedbackContentId, lessonId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.resetBtn = document.getElementById(resetBtnId);
        this.submitBtn = document.getElementById(submitBtnId);
        this.feedbackArea = document.getElementById(feedbackAreaId);
        this.feedbackContent = document.getElementById(feedbackContentId);
        this.lessonId = lessonId;
        
        this.isDrawing = false;
        this.lastX = 0;
        this.lastY = 0;
        
        // Set canvas styles
        this.ctx.lineWidth = 3;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.strokeStyle = '#000';
        
        // Set up event listeners
        this.setupEventListeners();
        this.setupTouchEvents();
        this.adjustCanvasSize();
        
        // Handle window resize
        window.addEventListener('resize', () => this.adjustCanvasSize());
    }
    
    adjustCanvasSize() {
        // Make canvas responsive
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth - 40; // Account for padding
        this.canvas.height = Math.min(300, window.innerHeight * 0.4);
    }
    
    setupEventListeners() {
        // Mouse events
        this.canvas.addEventListener('mousedown', (e) => this.startDrawing(e));
        this.canvas.addEventListener('mousemove', (e) => this.draw(e));
        this.canvas.addEventListener('mouseup', () => this.stopDrawing());
        this.canvas.addEventListener('mouseout', () => this.stopDrawing());
        
        // Button events
        this.resetBtn.addEventListener('click', () => this.clearCanvas());
        this.submitBtn.addEventListener('click', () => this.submitDrawing());
    }
    
    setupTouchEvents() {
        // Touch events for mobile devices
        this.canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousedown', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            this.canvas.dispatchEvent(mouseEvent);
        });
        
        this.canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousemove', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            this.canvas.dispatchEvent(mouseEvent);
        });
        
        this.canvas.addEventListener('touchend', (e) => {
            e.preventDefault();
            const mouseEvent = new MouseEvent('mouseup');
            this.canvas.dispatchEvent(mouseEvent);
        });
    }
    
    startDrawing(e) {
        this.isDrawing = true;
        const rect = this.canvas.getBoundingClientRect();
        this.lastX = e.clientX - rect.left;
        this.lastY = e.clientY - rect.top;
    }
    
    draw(e) {
        if (!this.isDrawing) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;
        
        this.ctx.beginPath();
        this.ctx.moveTo(this.lastX, this.lastY);
        this.ctx.lineTo(currentX, currentY);
        this.ctx.stroke();
        
        this.lastX = currentX;
        this.lastY = currentY;
    }
    
    stopDrawing() {
        this.isDrawing = false;
    }
    
    clearCanvas() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.hideFeedback();
    }
    
    submitDrawing() {
        // Convert canvas to base64 image
        const imageData = this.canvas.toDataURL('image/png');
        
        // Show loading state
        this.submitBtn.disabled = true;
        this.submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Checking...';
        
        // Send to server for evaluation
        fetch(`/api/submit_attempt/${this.lessonId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ image: imageData })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.showFeedback(data.feedback, data.correct, data.accuracy);
            } else {
                this.showFeedback('Error: ' + data.error, false);
            }
        })
        .catch(error => {
            this.showFeedback('Network error: ' + error.message, false);
        })
        .finally(() => {
            // Reset button state
            this.submitBtn.disabled = false;
            this.submitBtn.innerHTML = '<i class="fas fa-check me-1"></i> Submit';
        });
    }
    
    showFeedback(message, isCorrect, accuracy = null) {
        this.feedbackContent.innerHTML = message;
        
        if (isCorrect) {
            this.feedbackArea.className = 'alert alert-success';
        } else {
            this.feedbackArea.className = 'alert alert-danger';
        }
        
        if (accuracy !== null) {
            this.feedbackContent.innerHTML += `<br><small>Accuracy: ${accuracy}%</small>`;
        }
        
        this.feedbackArea.classList.remove('d-none');
        
        // Scroll to feedback
        this.feedbackArea.scrollIntoView({ behavior: 'smooth' });
    }
    
    hideFeedback() {
        this.feedbackArea.classList.add('d-none');
    }
}
