// static/js/canvas.js
class CanvasManager {
    // MODIFIED: Constructor accepts templateCanvasId
    constructor(canvasId, templateCanvasId, resetBtnId, submitBtnId, feedbackAreaId, feedbackContentId, lessonId, templateText) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        
        // NEW: Handle the template canvas
        this.templateCanvas = document.getElementById(templateCanvasId);
        this.templateCtx = this.templateCanvas.getContext('2d');

        this.resetBtn = document.getElementById(resetBtnId);
        this.submitBtn = document.getElementById(submitBtnId);
        this.feedbackArea = document.getElementById(feedbackAreaId);
        this.feedbackContent = document.getElementById(feedbackContentId);
        this.lessonId = lessonId;
        this.templateText = templateText;
        this.isDrawing = false;
        this.lastX = 0;
        this.lastY = 0;
        
        // Set canvas styles for drawing canvas
        this.ctx.lineWidth = 5; // A bit thicker for better detection
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.strokeStyle = '#000';
        
        // Set up event listeners
        this.setupEventListeners();
        this.setupTouchEvents();
        
        // Adjust canvas sizes on load and resize
        this.adjustCanvasSize();
        window.addEventListener('resize', () => this.adjustCanvasSize());
    }
    
    adjustCanvasSize() {
        const container = this.canvas.parentElement;
        const width = container.clientWidth;
        // Make height proportional to width, but max 300px
        const height = Math.min(300, width * 0.5); 
        
        container.style.height = `${height}px`;

        // MODIFIED: Resize both canvases
        this.canvas.width = width;
        this.canvas.height = height;
        this.templateCanvas.width = width;
        this.templateCanvas.height = height;

        // Re-apply drawing styles after resize
        this.ctx.lineWidth = 5;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.strokeStyle = '#000';
        
        this.drawTemplate();
    }
    
    setupEventListeners() {
        // Events are attached to the top canvas (this.canvas)
        this.canvas.addEventListener('mousedown', (e) => this.startDrawing(e));
        this.canvas.addEventListener('mousemove', (e) => this.draw(e));
        this.canvas.addEventListener('mouseup', () => this.stopDrawing());
        this.canvas.addEventListener('mouseout', () => this.stopDrawing());
        
        this.resetBtn.addEventListener('click', () => this.clearCanvas());
        this.submitBtn.addEventListener('click', () => this.submitDrawing());
    }

    // MODIFIED: Draws on the template canvas now
    drawTemplate() {
        if (!this.templateText) return;
        const ctx = this.templateCtx; // Use template context
        ctx.clearRect(0, 0, this.templateCanvas.width, this.templateCanvas.height);

        ctx.save();
        ctx.globalAlpha = 0.2;
        ctx.fillStyle = '#6c757d'; // A muted gray color
        ctx.font = `bold ${Math.floor(this.templateCanvas.height * 0.7)}px "Noto Sans Tamil"`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(this.templateText, this.templateCanvas.width / 2, this.templateCanvas.height / 2);
        ctx.restore();
    }
    
    setupTouchEvents() {
        // Touch events remain the same, they target the top canvas
        this.canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousedown', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            this.canvas.dispatchEvent(mouseEvent);
        }, { passive: false });
        
        this.canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousemove', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            this.canvas.dispatchEvent(mouseEvent);
        }, { passive: false });
        
        this.canvas.addEventListener('touchend', (e) => {
            e.preventDefault();
            const mouseEvent = new MouseEvent('mouseup');
            this.canvas.dispatchEvent(mouseEvent);
        }, { passive: false });
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
    
    // MODIFIED: Only clears the user's drawing canvas
    clearCanvas() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.hideFeedback();
    }
    
    submitDrawing() {
        // This correctly gets data ONLY from the user's drawing canvas
        const imageData = this.canvas.toDataURL('image/png');
        
        this.submitBtn.disabled = true;
        this.submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Checking...';
        
        fetch(`/api/submit_attempt/${this.lessonId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ image: imageData })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                this.showFeedback(data.feedback, data.correct, data.accuracy);
            } else {
                this.showFeedback('Error: ' + data.error, false);
            }
        })
        .catch(error => {
            this.showFeedback('An error occurred: ' + error.message, false);
        })
        .finally(() => {
            this.submitBtn.disabled = false;
            this.submitBtn.innerHTML = '<i class="fas fa-check me-1"></i> Submit';
        });
    }
    
    // In static/js/canvas.js

    showFeedback(message, isCorrect, accuracy = null) {
        this.feedbackContent.innerHTML = message;
        
        if (isCorrect) {
            this.feedbackArea.className = 'alert alert-success';
        } else {
            this.feedbackArea.className = 'alert alert-danger';
        }
        
        if (accuracy !== null) {
            // CHANGED: Format the number to one decimal place
            const formattedAccuracy = accuracy.toFixed(1);
            this.feedbackContent.innerHTML += `<br><small>Accuracy: ${formattedAccuracy}%</small>`;
        }
        
        this.feedbackArea.classList.remove('d-none');
        this.feedbackArea.scrollIntoView({ behavior: 'smooth' });
    }
    
    hideFeedback() {
        this.feedbackArea.classList.add('d-none');
    }
}
