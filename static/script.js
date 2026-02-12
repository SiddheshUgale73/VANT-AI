const chatContainer = document.getElementById('chatContainer');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const fileInput = document.getElementById('fileInput');
const uploadStatus = document.getElementById('uploadStatus');
const clearChat = document.getElementById('clearChat');
const docList = document.getElementById('docList');

// Auto-expand textarea
userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = (userInput.scrollHeight) + 'px';
});

// Load Indexed Documents
async function loadDocuments() {
    try {
        const response = await fetch('/documents');
        const data = await response.json();
        docList.innerHTML = '';
        if (data.documents && data.documents.length > 0) {
            data.documents.forEach(doc => {
                const li = document.createElement('li');
                li.innerHTML = `<i class="fas fa-file-lines"></i> <span>${doc}</span>`;
                docList.appendChild(li);
            });
        } else {
            docList.innerHTML = '<p style="font-size: 0.8rem; color: var(--text-secondary); text-align: center; padding: 1rem;">No files added yet.</p>';
        }
    } catch (error) {
        console.error('Failed to load documents:', error);
    }
}

// Handle File Upload
fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    uploadStatus.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

    try {
        const response = await fetch('/process', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.status === 'success') {
            uploadStatus.innerHTML = `<i class="fas fa-check-circle"></i> Indexed.`;
            addMessage('assistant', marked.parse(`**${file.name}** added.`));
            loadDocuments();
        } else {
            uploadStatus.innerHTML = `<span style="color: #ff4d4d; font-size: 0.75rem;">Error: ${data.message}</span>`;
        }
    } catch (error) {
        uploadStatus.textContent = 'Upload failed.';
    }
});

// Handle Sending Messages
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    userInput.value = '';
    userInput.style.height = 'auto';

    addMessage('user', message);

    const thinkingId = 'thinking-' + Date.now();
    addMessage('assistant', '<div class="thinking"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>', thinkingId);

    try {
        const formData = new FormData();
        formData.append('message', message);

        const response = await fetch('/chat', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        const thinkingMsg = document.getElementById(thinkingId);
        if (data.status === 'success') {
            thinkingMsg.innerHTML = marked.parse(data.response);

            if (data.sources && data.sources.length > 0) {
                const sourcesDiv = document.createElement('div');
                sourcesDiv.className = 'sources-container';
                data.sources.forEach(source => {
                    const badge = document.createElement('span');
                    badge.className = 'source-badge';
                    badge.textContent = source;
                    sourcesDiv.appendChild(badge);
                });
                thinkingMsg.appendChild(sourcesDiv);
            }
            saveChat();
        } else {
            thinkingMsg.innerHTML = 'Sorry, I encountered an issue while processing your request.';
        }
    } catch (error) {
        const msg = document.getElementById(thinkingId);
        if (msg) msg.innerHTML = 'The connection to VANT AI failed.';
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

// Persist Chat History
function saveChat() {
    localStorage.setItem('vant_vibrant_chat', chatContainer.innerHTML);
}

function loadChat() {
    const history = localStorage.getItem('vant_vibrant_chat');
    if (history) {
        chatContainer.innerHTML = history;
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

// Clear Chat
clearChat.addEventListener('click', () => {
    if (confirm('Clear?')) {
        chatContainer.innerHTML = '';
        localStorage.removeItem('vant_vibrant_chat');
    }
});

// Initialization
loadDocuments();
loadChat();
