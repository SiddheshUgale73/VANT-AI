const chatContainer = document.getElementById('chatContainer');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const fileInput = document.getElementById('fileInput');
const uploadStatus = document.getElementById('uploadStatus');
const clearChat = document.getElementById('clearChat');
const docList = document.getElementById('docList');
const sessionList = document.getElementById('sessionList');
const newChatBtn = document.getElementById('newChatBtn');
const activeModelBadge = document.getElementById('activeModelBadge');
const modelSelect = document.getElementById('modelSelect');
const micBtn = document.getElementById('micBtn');

let currentSessionId = null;
let isRecording = false;

// Voice Search (Web Speech API)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
        isRecording = true;
        micBtn.classList.add('recording');
        micBtn.innerHTML = '<i class="fas fa-microphone-lines fa-beat"></i>';
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        userInput.value = transcript;
        micBtn.classList.remove('recording');
        micBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        isRecording = false;
    };

    recognition.onerror = () => {
        micBtn.classList.remove('recording');
        micBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        isRecording = false;
    };

    recognition.onend = () => {
        micBtn.classList.remove('recording');
        micBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        isRecording = false;
    };

    micBtn.onclick = () => {
        if (isRecording) {
            recognition.stop();
        } else {
            recognition.start();
        }
    };
} else {
    micBtn.style.display = 'none';
}

// Configure marked with highlight.js
marked.setOptions({
    highlight: function (code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
    },
    breaks: true,
    gfm: true
});

// Model Management
async function loadModels() {
    try {
        const response = await fetch('/models');
        const data = await response.json();
        modelSelect.innerHTML = '';
        data.models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            modelSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

modelSelect.addEventListener('change', async () => {
    const modelId = modelSelect.value;
    const modelName = modelSelect.options[modelSelect.selectedIndex].text;

    try {
        const formData = new FormData();
        formData.append('model_id', modelId);
        const response = await fetch('/models/change', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.status === 'success') {
            activeModelBadge.textContent = modelName;
        }
    } catch (error) {
        console.error('Model change failed:', error);
    }
});

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    loadModels();
    loadDocuments();
    loadSessions();
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
                li.innerHTML = `
                    <i class="fas fa-file-lines"></i> 
                    <span title="${doc}" onclick="showSummary('${doc}', this)">${doc}</span>
                    <button class="delete-doc" onclick="deleteDocument('${doc}')">
                        <i class="fas fa-trash-can"></i>
                    </button>
                    <div class="doc-summary" id="summary-${btoa(doc).replace(/=/g, '')}"></div>
                `;
                docList.appendChild(li);
            });
        } else {
            docList.innerHTML = '<p class="empty-msg">No files added yet.</p>';
        }
    } catch (error) {
        console.error('Failed to load documents:', error);
    }
}

async function loadSessions() {
    try {
        const response = await fetch('/sessions');
        const data = await response.json();
        sessionList.innerHTML = '';

        data.sessions.forEach(session => {
            const li = document.createElement('li');
            li.className = `session-item ${session.id === currentSessionId ? 'active' : ''}`;
            li.innerHTML = `
                <i class="fas fa-message"></i>
                <span class="session-title" onclick="switchSession('${session.id}')">${session.title}</span>
                <i class="fas fa-trash-can delete-session" onclick="deleteSession(event, '${session.id}')"></i>
            `;
            sessionList.appendChild(li);
        });

        // If no active session, create one
        if (!currentSessionId && data.sessions.length > 0) {
            switchSession(data.sessions[0].id);
        } else if (data.sessions.length === 0) {
            createNewSession();
        }
    } catch (error) {
        console.error('Failed to load sessions:', error);
    }
}

async function createNewSession() {
    try {
        const response = await fetch('/sessions', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            currentSessionId = data.session_id;
            loadSessions();
            chatContainer.innerHTML = `
                <div class="welcome-screen">
                    <p style="text-align: center; color: #6b7280; margin-top: 10rem;">Ask anything...</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to create session:', error);
    }
}

async function switchSession(id) {
    if (currentSessionId === id) return;
    currentSessionId = id;

    // Update active state in UI
    document.querySelectorAll('.session-item').forEach(item => {
        item.classList.toggle('active', item.querySelector('.session-title').getAttribute('onclick') === `switchSession('${id}')`);
    });

    chatContainer.innerHTML = '<div class="thinking-wrapper"><div class="thinking-dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>';

    try {
        const response = await fetch(`/sessions/${id}/history`);
        const data = await response.json();

        chatContainer.innerHTML = '';
        if (data.messages.length === 0) {
            chatContainer.innerHTML = `
                <div class="welcome-screen">
                    <p style="text-align: center; color: #6b7280; margin-top: 10rem;">Ask anything...</p>
                </div>
            `;
        } else {
            data.messages.forEach(msg => {
                const content = msg.role === 'assistant' ? marked.parse(msg.content) : msg.content;
                addMessage(msg.role, content);
            });
        }
    } catch (error) {
        chatContainer.innerHTML = '<div class="error-msg">Failed to load chat history.</div>';
    }
}

async function deleteSession(event, id) {
    event.stopPropagation();
    if (!confirm('Delete this conversation?')) return;

    try {
        const response = await fetch(`/sessions/${id}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.status === 'success') {
            if (currentSessionId === id) currentSessionId = null;
            loadSessions();
        }
    } catch (error) {
        alert('Failed to delete session.');
    }
}

newChatBtn.onclick = createNewSession;

async function showSummary(filename, element) {
    const summaryId = `summary-${btoa(filename).replace(/=/g, '')}`;
    const summaryDiv = document.getElementById(summaryId);

    if (summaryDiv.style.display === 'block') {
        summaryDiv.style.display = 'none';
        return;
    }

    if (summaryDiv.innerHTML === '') {
        summaryDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Summarizing...';
        summaryDiv.style.display = 'block';

        try {
            const response = await fetch(`/summarize/${encodeURIComponent(filename)}`);
            const data = await response.json();
            if (data.status === 'success') {
                summaryDiv.innerHTML = marked.parse(data.summary);
            } else {
                summaryDiv.innerHTML = 'Failed to generate summary.';
            }
        } catch (error) {
            summaryDiv.innerHTML = 'Error connecting to server.';
        }
    } else {
        summaryDiv.style.display = 'block';
    }
}

async function deleteDocument(filename) {
    if (!confirm(`Remove ${filename} from VANT AI?`)) return;

    try {
        const response = await fetch(`/documents/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        if (data.status === 'success') {
            loadDocuments();
            addMessage('assistant', `**${filename}** has been removed from the database.`);
        }
    } catch (error) {
        console.error('Delete failed:', error);
    }
}

const uploadCard = document.querySelector('.upload-card');

uploadCard.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadCard.classList.add('drag-over');
});

uploadCard.addEventListener('dragleave', () => {
    uploadCard.classList.remove('drag-over');
});

uploadCard.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadCard.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) {
        handleFileUpload(file);
    }
});

async function handleFileUpload(file) {
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
            addMessage('assistant', marked.parse(`**${file.name}** added to the knowledge base.`));
            loadDocuments();
        } else {
            uploadStatus.innerHTML = `<span style="color: #ff4d4d; font-size: 0.75rem;">Error: ${data.message}</span>`;
        }
    } catch (error) {
        uploadStatus.textContent = 'Upload failed.';
    }
}

// Handle File Upload via Input
fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (file) handleFileUpload(file);
});

// Handle Sending Messages
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    userInput.value = '';
    userInput.style.height = 'auto';

    addMessage('user', message);

    const thinkingId = 'thinking-' + Date.now();
    addMessage('assistant', `
        <div class="thinking-wrapper">
            <div class="thinking-dots">
                <div class="dot"></div><div class="dot"></div><div class="dot"></div>
            </div>
        </div>
    `, thinkingId);

    try {
        const formData = new FormData();
        formData.append('message', message);
        formData.append('session_id', currentSessionId);

        const response = await fetch('/chat', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        const thinkingMsg = document.getElementById(thinkingId);
        const contentDiv = thinkingMsg.querySelector('.content');

        if (data.status === 'success') {
            contentDiv.innerHTML = marked.parse(data.response);

            if (data.sources && data.sources.length > 0) {
                const sourcesDiv = document.createElement('div');
                sourcesDiv.className = 'sources-container';
                data.sources.forEach(source => {
                    const badge = document.createElement('span');
                    badge.className = 'source-badge';
                    badge.textContent = source;
                    sourcesDiv.appendChild(badge);
                });
                contentDiv.appendChild(sourcesDiv);
            }
            // Title might have changed, reload sessions
            loadSessions();
        } else {
            contentDiv.innerHTML = `<span style="color: #ff4d4d;">Error: ${data.message || 'Processing failed'}</span>`;
        }
    } catch (error) {
        const msg = document.getElementById(thinkingId);
        if (msg) msg.querySelector('.content').innerHTML = 'The connection to VANT AI failed.';
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
    if (confirm('Clear current conversation?')) {
        createNewSession();
    }
});
