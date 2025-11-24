class App {
    constructor() {
        this.currentUser = null;
        this.currentConversation = null;
        this.conversations = [];
        this.users = [];
        this.apiBase = '/api';
        this.isLoadingConversation = false;
        this.activityInterval = null;
        this.messageRefreshInterval = null;
        this.lastMessageCount = 0;

        this.loadCurrentUser();
        this.setupEventListeners();
    }

    loadCurrentUser() {
        const stored = localStorage.getItem('currentUser');
        if (stored) {
            this.currentUser = JSON.parse(stored);
            this.init();
        } else {
            this.showAuthModal();
        }
    }

    init() {
        this.render();
        this.loadConversations();
        this.loadUsers();
        this.startActivityTracking();
    }

    startActivityTracking() {
        if (this.activityInterval) clearInterval(this.activityInterval);

        this.trackActivity();

        this.activityInterval = setInterval(() => {
            this.trackActivity();
            this.refreshUserStatus();
            this.loadConversations();
            this.refreshMessages();
        }, 3000);

        document.addEventListener('mousemove', () => this.trackActivity());
        document.addEventListener('keypress', () => this.trackActivity());
    }

    async trackActivity() {
        if (!this.currentUser) return;
        try {
            await fetch(`${this.apiBase}/users/track_activity/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: this.currentUser.id })
            });
        } catch (e) {
            console.error('Error tracking activity:', e);
        }
    }

    async refreshUserStatus() {
        await this.loadUsers();
    }

    async refreshMessages() {
        if (!this.currentConversation) return;
        try {
            const response = await fetch(`${this.apiBase}/conversations/${this.currentConversation.id}/`);
            const data = await response.json();

            if (data.messages && data.messages.length !== this.lastMessageCount) {
                this.currentConversation = data;
                this.renderMessages();
                this.lastMessageCount = data.messages.length;
            }
        } catch (e) {
            console.error('Error refreshing messages:', e);
        }
    }

    setupEventListeners() {
        document.addEventListener('click', (e) => {
            const target = e.target;

            if (target.classList.contains('btn-new-chat')) {
                e.preventDefault();
                e.stopPropagation();
                this.showNewChatModal();
            }

            if (target.classList.contains('btn-new-group')) {
                e.preventDefault();
                e.stopPropagation();
                this.showCreateGroupModal();
            }

            const chatItem = target.closest('.chat-item');
            if (chatItem && !this.isLoadingConversation) {
                e.preventDefault();
                e.stopPropagation();
                this.isLoadingConversation = true;
                this.openConversation(chatItem.dataset.conversationId).finally(() => {
                    this.isLoadingConversation = false;
                });
            }

            if (target.classList.contains('btn-send')) {
                e.preventDefault();
                e.stopPropagation();
                this.sendMessage();
            }

            if (target.classList.contains('btn-file')) {
                e.preventDefault();
                e.stopPropagation();
                document.getElementById('file-input').click();
            }

            if (target.classList.contains('download-btn')) {
                e.preventDefault();
                e.stopPropagation();
                this.downloadFile(target.dataset.fileId);
            }

            if (target.classList.contains('profile-btn')) {
                e.preventDefault();
                e.stopPropagation();
                this.toggleProfileMenu();
            }

            if (target.id === 'logout-btn') {
                e.preventDefault();
                e.stopPropagation();
                this.logout();
            }

            if (target.id === 'modal-overlay' && target.classList.contains('active')) {
                e.preventDefault();
                e.stopPropagation();
                this.hideModal();
            }

            if (target.id === 'create-group-btn') {
                e.preventDefault();
                e.stopPropagation();
                this.createGroupSubmit();
            }

            if (target.id === 'cancel-group-btn' || target.classList.contains('modal-btn-cancel')) {
                e.preventDefault();
                e.stopPropagation();
                this.hideModal();
            }

            if (target.classList.contains('start-chat-btn')) {
                e.preventDefault();
                e.stopPropagation();
                const userId = target.dataset.userId;
                const user = this.users.find(u => u.id === userId);
                if (user) {
                    this.startChat(user);
                }
            }

            const startChatBtn = target.closest('.start-chat-btn');
            if (startChatBtn && !target.classList.contains('start-chat-btn')) {
                e.preventDefault();
                e.stopPropagation();
                const userId = startChatBtn.dataset.userId;
                const user = this.users.find(u => u.id === userId);
                if (user) {
                    this.startChat(user);
                }
            }
        });

        document.addEventListener('input', (e) => {
            if (e.target.classList.contains('search-input')) {
                this.filterChats(e.target.value);
            }
        });

        document.addEventListener('keypress', (e) => {
            if (e.target.classList.contains('message-input') && e.key === 'Enter') {
                e.preventDefault();
                this.sendMessage();
            }
        });

        document.addEventListener('change', (e) => {
            if (e.target.id === 'file-input') {
                this.uploadFile(e.target.files[0]);
            }
        });
    }

    render() {
        const app = document.getElementById('app');
        if (!this.currentUser) return;

        app.innerHTML = `
            <div class="container">
                <div class="sidebar">
                    <div class="sidebar-header">
                        <h1>Messages</h1>
                        <button class="btn-new-chat">+</button>
                        <button class="profile-btn">⋯</button>
                        <div class="profile-menu">
                            <button id="logout-btn">Logout</button>
                        </div>
                    </div>
                    <div class="search-box">
                        <input type="text" class="search-input" placeholder="Search...">
                    </div>
                    <ul class="chat-list" id="chat-list"></ul>
                </div>
                <div class="main-content">
                    <div id="welcome-screen" class="welcome-screen">
                        <div>
                            <h2>Select a chat to start messaging</h2>
                        </div>
                    </div>
                </div>
            </div>
            <div id="modal-overlay" class="modal-overlay"></div>
            <input type="file" id="file-input" class="file-input" accept="*">
        `;

        this.renderChatList();
    }

    renderChatList() {
        const chatList = document.getElementById('chat-list');
        chatList.innerHTML = '';

        this.conversations.forEach(conv => {
            const lastMessage = conv.messages[conv.messages.length - 1];
            const preview = lastMessage ? lastMessage.content.substring(0, 40) : 'No messages yet';

            let chatName = '';
            if (conv.type === 'group') {
                chatName = conv.name || 'Group Chat';
            } else {
                const otherParticipant = conv.participants.find(p => p.user.id !== this.currentUser.id);
                chatName = otherParticipant?.user.username || 'Unknown';
            }

            const li = document.createElement('li');
            li.className = 'chat-item';
            li.dataset.conversationId = conv.id;
            if (this.currentConversation?.id === conv.id) {
                li.classList.add('active');
            }

            li.innerHTML = `
                <div class="chat-item-name">${chatName}</div>
                <div class="chat-item-preview">${preview}</div>
            `;

            chatList.appendChild(li);
        });
    }

    renderChatWindow() {
        if (!this.currentConversation) return;

        const mainContent = document.querySelector('.main-content');

        let headerTitle = 'Chat';
        if (this.currentConversation.type === 'group') {
            headerTitle = this.currentConversation.name || 'Group Chat';
        } else {
            const otherParticipant = this.currentConversation.participants.find(
                p => p.user.id !== this.currentUser.id
            );
            headerTitle = otherParticipant?.user.username || 'Chat';
        }

        let memberInfo = '';
        if (this.currentConversation.type === 'group') {
            const memberCount = this.currentConversation.participants.length;
            const limit = this.currentConversation.group_member_limit;
            memberInfo = `<div class="group-info">${memberCount}/${limit} members • ${this.currentConversation.group_privacy}</div>`;
        }

        mainContent.innerHTML = `
            <div class="chat-window active">
                <div class="chat-header">
                    <h2>${headerTitle}</h2>
                    ${memberInfo}
                </div>
                <div class="messages-container" id="messages-container"></div>
                <div class="input-area">
                    <button class="btn-file">📎</button>
                    <input type="text" class="message-input" placeholder="Type a message...">
                    <button class="btn-send">➤</button>
                </div>
            </div>
        `;

        this.renderMessages();
    }

    renderMessages() {
        const container = document.getElementById('messages-container');
        container.innerHTML = '';

        this.currentConversation.messages.forEach(msg => {
            const isOwn = msg.sender.id === this.currentUser.id;
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${isOwn ? 'sent' : 'received'}`;

            if (msg.content_type === 'file' || msg.content_type === 'image' || msg.content_type === 'video') {
                const contentDiv = document.createElement('div');
                contentDiv.style.display = 'flex';
                contentDiv.style.flexDirection = 'column';
                contentDiv.style.gap = '4px';

                const fileDiv = document.createElement('div');
                fileDiv.className = 'file-message';
                fileDiv.innerHTML = `
                    <div class="file-icon">${this.getFileIcon(msg.content_type)}</div>
                    <div class="file-info">
                        <div class="file-name">${msg.content}</div>
                        <div class="file-size">${this.formatFileSize(msg.file?.size_bytes || 0)}</div>
                    </div>
                    <button class="download-btn" data-file-id="${msg.file?.id}">↓</button>
                `;

                const timeDiv = document.createElement('div');
                timeDiv.className = 'message-time';
                timeDiv.textContent = new Date(msg.sent_at).toLocaleTimeString();

                contentDiv.appendChild(fileDiv);
                contentDiv.appendChild(timeDiv);
                msgDiv.appendChild(contentDiv);
            } else {
                const contentDiv = document.createElement('div');
                contentDiv.style.display = 'flex';
                contentDiv.style.flexDirection = 'column';
                contentDiv.style.gap = '4px';

                const bubble = document.createElement('div');
                bubble.className = 'message-bubble';
                bubble.textContent = msg.content;

                const timeDiv = document.createElement('div');
                timeDiv.className = 'message-time';
                timeDiv.textContent = new Date(msg.sent_at).toLocaleTimeString();

                contentDiv.appendChild(bubble);
                contentDiv.appendChild(timeDiv);
                msgDiv.appendChild(contentDiv);
            }

            container.appendChild(msgDiv);
        });

        container.scrollTop = container.scrollHeight;
    }

    async openConversation(conversationId) {
        try {
            const response = await fetch(`${this.apiBase}/conversations/${conversationId}/`);
            const data = await response.json();
            this.currentConversation = data;
            this.lastMessageCount = data.messages.length;
            this.renderChatWindow();
            this.renderChatList();

            const welcomeScreen = document.getElementById('welcome-screen');
            if (welcomeScreen) {
                welcomeScreen.style.display = 'none';
            }
        } catch (e) {
            console.error('Error opening conversation:', e);
            alert('Error opening conversation: ' + e.message);
        }
    }

    async sendMessage() {
        const input = document.querySelector('.message-input');
        const content = input.value.trim();

        if (!content) return;

        try {
            const response = await fetch(`${this.apiBase}/messages/send/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: this.currentConversation.id,
                    sender_id: this.currentUser.id,
                    content: content,
                    content_type: 'text'
                })
            });

            if (response.ok) {
                input.value = '';
                await this.openConversation(this.currentConversation.id);
            }
        } catch (e) {
            alert('Error sending message: ' + e.message);
        }
    }

    async uploadFile(file) {
        if (!file) return;

        const maxSize = 1024 * 1024 * 1024;
        if (file.size > maxSize) {
            alert('File size exceeds 1GB limit');
            return;
        }

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('conversation_id', this.currentConversation.id);
            formData.append('sender_id', this.currentUser.id);

            const response = await fetch(`${this.apiBase}/files/upload/`, {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                await this.openConversation(this.currentConversation.id);
            } else {
                alert('File upload failed');
            }
        } catch (e) {
            alert('Error uploading file: ' + e.message);
        }
    }

    async downloadFile(fileId) {
        try {
            const response = await fetch(`${this.apiBase}/files/download/?file_id=${fileId}`);
            const data = await response.json();

            const binaryString = atob(data.file);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            const blob = new Blob([bytes], { type: data.mime_type });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = data.filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (e) {
            alert('Error downloading file: ' + e.message);
        }
    }

    async loadConversations() {
        try {
            const response = await fetch(`${this.apiBase}/conversations/by_user/?user_id=${this.currentUser.id}`);
            const data = await response.json();
            this.conversations = data;
            this.renderChatList();
        } catch (e) {
            console.error('Error loading conversations:', e);
        }
    }

    async loadUsers() {
        try {
            const response = await fetch(`${this.apiBase}/users/list_users/`);
            const data = await response.json();
            this.users = data.filter(u => u.id !== this.currentUser.id);
        } catch (e) {
            console.error('Error loading users:', e);
        }
    }

    filterChats(query) {
        const items = document.querySelectorAll('.chat-item');
        items.forEach(item => {
            const name = item.querySelector('.chat-item-name').textContent.toLowerCase();
            if (name.includes(query.toLowerCase())) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    }

    showAuthModal() {
        const app = document.getElementById('app');
        app.innerHTML = `
            <div class="modal-overlay active">
                <div class="modal">
                    <h2>Login / Sign Up</h2>
                    <input type="text" id="auth-username" placeholder="Enter your username" autocomplete="off">
                    <button class="modal-btn" id="auth-btn">Login</button>
                    <div id="auth-error"></div>
                </div>
            </div>
        `;

        document.getElementById('auth-btn').addEventListener('click', () => this.handleAuth());
        document.getElementById('auth-username').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleAuth();
        });
    }

    async handleAuth() {
        const username = document.getElementById('auth-username').value.trim();
        const errorDiv = document.getElementById('auth-error');

        if (!username) {
            errorDiv.innerHTML = '<div class="error">Username required</div>';
            return;
        }

        try {
            let response = await fetch(`${this.apiBase}/users/login/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username })
            });

            if (!response.ok) {
                response = await fetch(`${this.apiBase}/users/signup/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username })
                });
            }

            if (response.ok) {
                const user = await response.json();
                this.currentUser = user;
                localStorage.setItem('currentUser', JSON.stringify(user));
                this.init();
            } else {
                errorDiv.innerHTML = '<div class="error">Error with authentication</div>';
            }
        } catch (e) {
            errorDiv.innerHTML = '<div class="error">Connection error</div>';
        }
    }

    showNewChatModal() {
        const overlay = document.getElementById('modal-overlay');
        overlay.innerHTML = `
            <div class="modal">
                <h2>New Chat</h2>
                <div style="margin-bottom: 16px;">
                    <p style="font-size: 13px; color: #999; margin-bottom: 12px;">Select a person to message:</p>
                    <div id="users-list" style="max-height: 250px; overflow-y: auto; margin-bottom: 16px;"></div>
                </div>
                <button class="modal-btn btn-new-group" style="background: #25d366; color: white; margin-bottom: 8px;">+ Create Group</button>
                <button class="modal-btn modal-btn-cancel">Close</button>
            </div>
        `;

        const usersList = document.getElementById('users-list');
        if (this.users.length === 0) {
            usersList.innerHTML = '<p style="color: #999; text-align: center; padding: 16px;">No users available</p>';
        } else {
            this.users.forEach(user => {
                const userDiv = document.createElement('div');
                userDiv.style.marginBottom = '8px';
                userDiv.style.padding = '12px';
                userDiv.style.border = '1px solid #e0e0e0';
                userDiv.style.borderRadius = '8px';
                userDiv.style.display = 'flex';
                userDiv.style.justifyContent = 'space-between';
                userDiv.style.alignItems = 'center';

                const statusColor = user.is_online ? '#25d366' : '#999';
                const statusText = user.is_online ? 'Online' : `Offline: ${user.offline_minutes}`;

                userDiv.innerHTML = `
                    <button class="start-chat-btn" data-user-id="${user.id}" style="flex: 1; background: none; border: none; text-align: left; cursor: pointer; font-size: 14px; padding: 0; margin: 0;">
                        ${user.username}
                    </button>
                    <span style="color: ${statusColor}; font-size: 12px; margin-left: 8px; white-space: nowrap;">
                        ${statusText}
                    </span>
                `;
                usersList.appendChild(userDiv);
            });
        }

        overlay.classList.add('active');
    }

    showCreateGroupModal() {
        const overlay = document.getElementById('modal-overlay');
        overlay.innerHTML = `
            <div class="modal">
                <h2>Create Group Chat</h2>
                <input type="text" id="group-name" placeholder="Group name" autocomplete="off">
                <textarea id="group-desc" placeholder="Description (optional)" style="width: 100%; padding: 12px; border: 1px solid #e0e0e0; border-radius: 8px; font-family: inherit; margin-bottom: 16px; min-height: 60px; resize: none;"></textarea>
                <label style="display: block; margin-bottom: 16px; font-size: 13px; font-weight: 500;">
                    Privacy Type:
                    <select id="group-privacy" style="width: 100%; padding: 10px; margin-top: 6px; border: 1px solid #e0e0e0; border-radius: 4px; font-family: inherit;">
                        <option value="public">Public - Anyone can join</option>
                        <option value="invite">Invite Only</option>
                        <option value="closed">Closed - Admin only</option>
                    </select>
                </label>
                <label style="display: block; margin-bottom: 16px; font-size: 13px; font-weight: 500;">
                    Member Limit:
                    <select id="group-limit" style="width: 100%; padding: 10px; margin-top: 6px; border: 1px solid #e0e0e0; border-radius: 4px; font-family: inherit;">
                        <option value="5">5 members</option>
                        <option value="10">10 members</option>
                        <option value="15">15 members</option>
                        <option value="50">50 members</option>
                    </select>
                </label>
                <label style="display: block; margin-bottom: 16px; font-size: 13px; font-weight: 500;">
                    Add Members:
                    <div id="group-members" style="max-height: 120px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; padding: 8px; margin-top: 6px; background: #f9f9f9;"></div>
                </label>
                <button class="modal-btn" id="create-group-btn">Create Group</button>
                <button class="modal-btn modal-btn-cancel" id="cancel-group-btn">Cancel</button>
                <div id="group-error"></div>
            </div>
        `;

        const membersList = document.getElementById('group-members');
        if (this.users.length === 0) {
            membersList.innerHTML = '<p style="color: #999; font-size: 12px;">No users to add</p>';
        } else {
            this.users.forEach(user => {
                if (user.id !== this.currentUser.id) {
                    const label = document.createElement('label');
                    label.style.display = 'block';
                    label.style.marginBottom = '6px';
                    label.style.cursor = 'pointer';
                    label.style.fontSize = '13px';
                    label.innerHTML = `
                        <input type="checkbox" value="${user.id}" class="group-member-check" style="margin-right: 6px;"> ${user.username}
                    `;
                    membersList.appendChild(label);
                }
            });
        }

        overlay.classList.add('active');
        document.getElementById('group-name').focus();
    }

    async createGroupSubmit() {
        const groupName = document.getElementById('group-name').value.trim();
        const groupDesc = document.getElementById('group-desc').value.trim();
        const groupPrivacy = document.getElementById('group-privacy').value;
        const groupLimit = parseInt(document.getElementById('group-limit').value);
        const errorDiv = document.getElementById('group-error');

        if (!groupName) {
            errorDiv.innerHTML = '<div class="error">Group name required</div>';
            return;
        }

        const memberIds = Array.from(document.querySelectorAll('.group-member-check:checked'))
            .map(cb => cb.value);

        try {
            const response = await fetch(`${this.apiBase}/conversations/create_group/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.currentUser.id,
                    group_name: groupName,
                    description: groupDesc,
                    group_privacy: groupPrivacy,
                    group_member_limit: groupLimit,
                    member_ids: memberIds
                })
            });

            if (response.ok) {
                const group = await response.json();
                this.hideModal();
                await this.loadConversations();
                this.openConversation(group.id);
            } else {
                const error = await response.json();
                errorDiv.innerHTML = `<div class="error">${error.error || 'Error creating group'}</div>`;
            }
        } catch (e) {
            errorDiv.innerHTML = `<div class="error">Error: ${e.message}</div>`;
        }
    }

    async startChat(user) {
        try {
            const response = await fetch(`${this.apiBase}/conversations/get_or_create/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.currentUser.id,
                    other_user_id: user.id
                })
            });

            if (response.ok) {
                const conv = await response.json();
                this.hideModal();
                await this.loadConversations();
                await this.openConversation(conv.id);
            } else {
                const error = await response.json();
                alert('Error starting chat: ' + (error.error || 'Unknown error'));
            }
        } catch (e) {
            console.error('Error starting chat:', e);
            alert('Error starting chat: ' + e.message);
        }
    }

    toggleProfileMenu() {
        const menu = document.querySelector('.profile-menu');
        menu.classList.toggle('active');
    }

    logout() {
        localStorage.removeItem('currentUser');
        this.currentUser = null;
        this.showAuthModal();
    }

    hideModal() {
        document.getElementById('modal-overlay').classList.remove('active');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
    }

    getFileIcon(contentType) {
        const icons = {
            'image': '🖼️',
            'video': '🎥',
            'file': '📄',
            'text': '📝'
        };
        return icons[contentType] || '📎';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new App();
});
