const toggleLogin = document.getElementById('toggleLogin');
const toggleSignup = document.getElementById('toggleSignup');
const authToggle = document.querySelector('.auth-toggle');
const loginForm = document.getElementById('loginForm');
const signupForm = document.getElementById('signupForm');
const messageBox = document.getElementById('messageBox');

// Toggle between Login and Signup
toggleLogin.onclick = () => {
    toggleLogin.classList.add('active');
    toggleSignup.classList.remove('active');
    authToggle.classList.remove('signup-active');
    authToggle.classList.add('login-active');
    loginForm.classList.add('active');
    signupForm.classList.remove('active');
    messageBox.textContent = '';
};

toggleSignup.onclick = () => {
    toggleSignup.classList.add('active');
    toggleLogin.classList.remove('active');
    authToggle.classList.remove('login-active');
    authToggle.classList.add('signup-active');
    signupForm.classList.add('active');
    loginForm.classList.remove('active');
    messageBox.textContent = '';
};

// Handle Login
loginForm.onsubmit = async (e) => {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;

    messageBox.textContent = 'Authenticating...';
    messageBox.className = 'message-box';

    try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch('/login', {
            method: 'POST',
            body: formData,
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem('vant_token', data.access_token);
            localStorage.setItem('vant_user', username);
            messageBox.textContent = 'Welcome back!';
            messageBox.className = 'message-box success';
            setTimeout(() => window.location.href = '/', 1000);
        } else {
            messageBox.textContent = data.detail || 'Invalid credentials';
            messageBox.className = 'message-box error';
        }
    } catch (err) {
        messageBox.textContent = 'Server connection failed';
        messageBox.className = 'message-box error';
    }
};

// Handle Signup
signupForm.onsubmit = async (e) => {
    e.preventDefault();
    const username = document.getElementById('signupUsername').value;
    const email = document.getElementById('signupEmail').value;
    const password = document.getElementById('signupPassword').value;

    messageBox.textContent = 'Creating account...';
    messageBox.className = 'message-box';

    try {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('email', email);
        formData.append('password', password);

        const response = await fetch('/signup', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            messageBox.textContent = 'Account created! Please log in.';
            messageBox.className = 'message-box success';
            setTimeout(() => toggleLogin.click(), 2000);
        } else {
            messageBox.textContent = data.message || 'Signup failed';
            messageBox.className = 'message-box error';
        }
    } catch (err) {
        messageBox.textContent = 'Server connection failed';
        messageBox.className = 'message-box error';
    }
};

// Check if already logged in
if (localStorage.getItem('vant_token')) {
    window.location.href = '/';
}
