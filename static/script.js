const chatContainer = document.getElementById('chatContainer');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const fileInput = document.getElementById('fileInput');
const uploadStatus = document.getElementById('uploadStatus');
const clearChat = document.getElementById('clearChat');


userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = (userInput.scrollHeight) + 'px';
});

// Handle File Upload
fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    uploadStatus.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    uploadStatus.className = 'status-box status-success';

    try {
        const response = await fetch('/process', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.status === 'success') {
            uploadStatus.textContent = data.message;
            addMessage('assistant', marked.parse(`Great! I've indexed **${file.name}**. What would you like to know?`));
        } else {
            uploadStatus.textContent = data.message;
            uploadStatus.className = 'status-box status-error';
        }
    } catch (error) {
        uploadStatus.textContent = 'Upload failed';
        uploadStatus.className = 'status-box status-error';
    }
});

// Handle Sending Messages
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Reset input
    userInput.value = '';
    userInput.style.height = 'auto';

    addMessage('user', message);

    // AI thinking indicator
    const thinkingId = 'thinking-' + Date.now();
    addMessage('assistant', '<i class="fas fa-circle-notch fa-spin"></i> Thinking...', thinkingId);

    try {
        const formData = new FormData();
        formData.append('message', message);

        const response = await fetch('/chat', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        // Replace thinking with actual response
        const thinkingMsg = document.getElementById(thinkingId);
        if (data.status === 'success') {
            thinkingMsg.innerHTML = marked.parse(data.response);

            // Add citations if available
            if (data.sources && data.sources.length > 0) {
                const sourcesDiv = document.createElement('div');
                sourcesDiv.className = 'sources-container';
                sourcesDiv.innerHTML = '<span class="sources-label">Sources:</span>';

                data.sources.forEach(source => {
                    const badge = document.createElement('span');
                    badge.className = 'source-badge';
                    badge.textContent = source;
                    sourcesDiv.appendChild(badge);
                });

                thinkingMsg.appendChild(sourcesDiv);
            }
        } else {
            thinkingMsg.innerHTML = 'Sorry, I encountered an error: ' + data.message;
        }
    } catch (error) {
        document.getElementById(thinkingId).innerHTML = 'Sorry, the connection failed.';
    }
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Add Message to DOM
function addMessage(role, content, id = null) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    if (id) div.id = id;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'content';
    contentDiv.innerHTML = content;

    div.appendChild(contentDiv);
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Clear Chat
clearChat.addEventListener('click', () => {
    chatContainer.innerHTML = '';
    addMessage('assistant', 'Chat history cleared. How can I help you?');
});
