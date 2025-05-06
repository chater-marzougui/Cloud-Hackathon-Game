// Cloud Clash: Sudden Deployment - Main JavaScript

// Global socket connection
const socket = io();

// Global game state
const gameState = {
    playerId: null,
    score: 0,
    currentQuestion: 0,
    hasAnswered: false,
    gameStarted: false,
    totalQuestions: 45
};

// Sound effects - uncomment and provide audio files if needed
/*
const sounds = {
    correct: new Audio('/static/sounds/correct.mp3'),
    wrong: new Audio('/static/sounds/wrong.mp3'),
    newQuestion: new Audio('/static/sounds/new-question.mp3'),
    gameOver: new Audio('/static/sounds/game-over.mp3')
};
*/

// Helper functions
function playSound(soundName) {
    try {
        // Check if sounds object exists and sound exists
        if (typeof sounds !== 'undefined' && sounds[soundName]) {
            sounds[soundName].play().catch(error => {
                console.log('Sound play error:', error);
            });
        }
    } catch (error) {
        console.log('Sound error:', error);
    }
}

function showMessage(message, type = 'info') {
    const messageContainer = document.getElementById('feedback-area') || 
                           document.getElementById('message-container');
    
    if (messageContainer) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${type}`;
        messageElement.textContent = message;
        
        messageContainer.appendChild(messageElement);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            messageElement.classList.add('fade-out');
            setTimeout(() => {
                if (messageElement.parentNode === messageContainer) {
                    messageContainer.removeChild(messageElement);
                }
            }, 1000);
        }, 4000);
    }
}

function updateScoreDisplay(score) {
    const scoreElement = document.getElementById('player-score');
    if (scoreElement) {
        const scoreSpan = scoreElement.querySelector('span') || scoreElement;
        scoreSpan.textContent = score !== undefined ? score : gameState.score;
    }
}

function updateQuestionCounter(current, total) {
    const counterElement = document.getElementById('question-number');
    if (counterElement) {
        counterElement.textContent = current;
    }
    
    // Update total if provided
    if (total && document.querySelector('.question-counter span')) {
        // If there's a separate element for total, update it
        const totalElement = document.querySelector('.question-counter').lastElementChild;
        if (totalElement && totalElement !== counterElement) {
            // Extract the number from the text "Question: X/Y"
            const counterText = document.querySelector('.question-counter').textContent;
            const newText = counterText.replace(/\/\d+/, `/${total}`);
            document.querySelector('.question-counter').textContent = newText;
        }
    }
}

// Socket event handlers
socket.on('connect', () => {
    console.log('Connected to server');
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    showMessage('Connection lost. Trying to reconnect...', 'error');
});

socket.on('error', (data) => {
    console.error('Socket error:', data);
    showMessage(data.message || 'An error occurred', 'error');
});

// Export helper functions and socket for use in other scripts
window.gameHelpers = {
    playSound,
    showMessage,
    updateScoreDisplay,
    updateQuestionCounter,
    gameState,
    socket
};