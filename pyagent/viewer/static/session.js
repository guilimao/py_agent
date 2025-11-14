// 工具函数展开/折叠
function toggleAssistantTool(element) {
    const content = element.nextElementSibling;
    const toggle = element.querySelector('.assistant-tool-toggle');
    
    if (content.classList.contains('active')) {
        content.classList.remove('active');
        toggle.textContent = '展开参数 ▼';
    } else {
        content.classList.add('active');
        toggle.textContent = '折叠参数 ▲';
    }
}

// 工具结果展开/折叠
function toggleToolResult(element) {
    const content = element.nextElementSibling;
    const icon = element.querySelector('.collapsible-icon');
    
    if (content.classList.contains('active')) {
        content.classList.remove('active');
        icon.classList.remove('expanded');
    } else {
        content.classList.add('active');
        icon.classList.add('expanded');
    }
}

// 数据库导入
function importDatabase() {
    const fileInput = document.getElementById('dbFile');
    const file = fileInput.files[0];
    
    if (!file) {
        return;
    }
    
    // 验证文件类型
    if (!file.name.endsWith('.db')) {
        showError('请选择有效的数据库文件(.db)');
        return;
    }
    
    const formData = new FormData();
    formData.append('database', file);
    
    // 显示加载状态
    showLoading();
    hideMessages();
    
    // 发送请求
    fetch('/import-database', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            showSuccess(data.message);
            // 2秒后刷新页面
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showError(data.error || '导入失败');
        }
    })
    .catch(error => {
        hideLoading();
        showError('导入失败: ' + error.message);
    });
}

// 显示删除确认模态框
function showDeleteModal(sessionId, event) {
    event.preventDefault();
    event.stopPropagation();
    
    const modal = document.getElementById('deleteModal');
    const sessionInfo = document.getElementById('sessionToDelete');
    const confirmBtn = document.getElementById('confirmDelete');
    
    // 存储要删除的会话ID
    confirmBtn.setAttribute('data-session-id', sessionId);
    
    // 查找待删除会话的前后会话ID
    let previousSessionId = null;
    let nextSessionId = null;
    let found = false;
    
    const sessionElements = document.querySelectorAll('.session-item');
    for (let i = 0; i < sessionElements.length; i++) {
        const href = sessionElements[i].getAttribute('href');
        const id = href.split('/')[2];
        
        if (id === sessionId) {
            found = true;
            if (i > 0) {
                const prevHref = sessionElements[i - 1].getAttribute('href');
                previousSessionId = prevHref.split('/')[2];
            }
        } else if (found && !nextSessionId) {
            const nextHref = sessionElements[i].getAttribute('href');
            nextSessionId = nextHref.split('/')[2];
            break;
        }
    }
    
    // 确定删除后要跳转的目标会话（优先前一个，其次后一个）
    const redirectSessionId = previousSessionId || nextSessionId || null;
    confirmBtn.setAttribute('data-redirect-session', redirectSessionId);
    
    // 只显示会话ID，避免特殊字符导致的语法错误
    sessionInfo.textContent = `会话ID: ${sessionId}`;
    
    // 显示模态框
    modal.style.display = 'block';
    
    // 添加键盘事件监听
    function handleKeyPress(e) {
        if (e.key === 'Escape') {
            hideDeleteModal();
        } else if (e.key === 'Enter') {
            deleteSession();
        }
    }
    
    // 将事件处理函数存储在modal上，以便移除
    modal._keyHandler = handleKeyPress;
    document.addEventListener('keydown', handleKeyPress);
    
    // 添加点击模态框背景关闭的功能
    function handleClickOutside(e) {
        if (e.target === modal) {
            hideDeleteModal();
        }
    }
    
    modal._clickHandler = handleClickOutside;
    modal.addEventListener('click', handleClickOutside);
}

// 隐藏删除确认模态框
function hideDeleteModal() {
    const modal = document.getElementById('deleteModal');
    const confirmBtn = document.getElementById('confirmDelete');
    
    modal.style.display = 'none';
    confirmBtn.removeAttribute('data-session-id');
    confirmBtn.removeAttribute('data-redirect-session');
    confirmBtn.disabled = false;
    confirmBtn.textContent = '删除';
    
    // 移除键盘事件监听
    if (modal._keyHandler) {
        document.removeEventListener('keydown', modal._keyHandler);
        delete modal._keyHandler;
    }
    
    // 移除点击外部关闭的事件监听
    if (modal._clickHandler) {
        modal.removeEventListener('click', modal._clickHandler);
        delete modal._clickHandler;
    }
}

// 删除会话
function deleteSession() {
    const confirmBtn = document.getElementById('confirmDelete');
    const sessionId = confirmBtn.getAttribute('data-session-id');
    const redirectSessionId = confirmBtn.getAttribute('data-redirect-session');
    
    if (!sessionId) {
        showError('未选择要删除的会话');
        return;
    }
    
    // 禁用按钮并显示加载状态
    confirmBtn.disabled = true;
    confirmBtn.textContent = '删除中...';
    
    fetch(`/api/session/${sessionId}/delete`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess(data.message);
            // 先隐藏模态框，重置按钮状态，再跳转页面
            hideDeleteModal();
            
            // 延迟一下再跳转，确保DOM更新完成
            setTimeout(() => {
                const currentSession = window.location.pathname.split('/')[2];
                if (currentSession === sessionId) {
                    // 如果被删除的是当前会话
                    if (redirectSessionId) {
                        // 跳转到前后会话（优先前一个）
                        window.location.href = `/session/${redirectSessionId}`;
                    } else {
                        // 如果没有前后会话，跳转到首页
                        window.location.href = '/';
                    }
                } else {
                    // 否则只刷新页面
                    window.location.reload();
                }
            }, 100);
        } else {
            showError(data.error || '删除失败');
            hideDeleteModal();
        }
    })
    .catch(error => {
        showError('删除失败: ' + error.message);
        hideDeleteModal();
    });
}

// 显示错误消息
function showError(message) {
    const errorElement = document.getElementById('errorMessage');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
        
        // 3秒后自动隐藏
        setTimeout(() => {
            if (errorElement) {
                errorElement.style.display = 'none';
            }
        }, 5000);
    } else {
        console.error('Error:', message);
    }
}

// 显示成功消息
function showSuccess(message) {
    const successElement = document.getElementById('successMessage');
    if (successElement) {
        successElement.textContent = message;
        successElement.style.display = 'block';
        
        // 3秒后自动隐藏
        setTimeout(() => {
            if (successElement) {
                successElement.style.display = 'none';
            }
        }, 5000);
    } else {
        console.log('Success:', message);
    }
}

// 显示加载状态
function showLoading() {
    const loadingElement = document.getElementById('loading');
    if (loadingElement) {
        loadingElement.style.display = 'flex';
    }
}

// 隐藏加载状态
function hideLoading() {
    const loadingElement = document.getElementById('loading');
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
}

// 隐藏所有消息
function hideMessages() {
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('successMessage').style.display = 'none';
}

// 页面加载完成后的初始化
document.addEventListener('DOMContentLoaded', function() {
    // 添加平滑滚动
    const sidebar = document.querySelector('.session-list');
    if (sidebar) {
        sidebar.style.scrollBehavior = 'smooth';
    }
    
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.style.scrollBehavior = 'smooth';
    }
    
    // 高亮当前选中的会话
    const activeSession = document.querySelector('.session-item.active');
    if (activeSession && sidebar) {
        setTimeout(() => {
            activeSession.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    }
    
    // 添加键盘快捷键
    document.addEventListener('keydown', function(e) {
        // Ctrl + F 聚焦搜索（如果添加了搜索功能）
        if (e.ctrlKey && e.key === 'f') {
            e.preventDefault();
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.focus();
            }
        }
        
        // ESC 关闭所有展开的内容
        if (e.key === 'Escape') {
            const expandedContents = document.querySelectorAll('.assistant-tool-args.active, .tool-result-content.active');
            expandedContents.forEach(content => {
                content.classList.remove('active');
                const toggle = content.previousElementSibling.querySelector('.assistant-tool-toggle, .collapsible-icon');
                if (toggle) {
                    if (toggle.classList.contains('assistant-tool-toggle')) {
                        toggle.textContent = '展开参数 ▼';
                    } else {
                        toggle.classList.remove('expanded');
                    }
                }
            });
        }
    });
    
    // 添加消息悬停效果
    const messages = document.querySelectorAll('.message');
    messages.forEach(message => {
        message.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });
        
        message.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    // 添加会话项悬停效果
    const sessionItems = document.querySelectorAll('.session-item');
    sessionItems.forEach(item => {
        item.addEventListener('mouseenter', function() {
            if (!this.classList.contains('active')) {
                this.style.transform = 'translateY(-1px)';
            }
        });
        
        item.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    // 默认折叠工具结果
    const allToolResults = document.querySelectorAll('.tool-result-section');
    allToolResults.forEach(section => {
        const content = section.querySelector('.tool-result-content');
        const icon = section.querySelector('.collapsible-icon');
        if (content && content.classList.contains('active')) {
            content.classList.remove('active');
        }
        if (icon && icon.classList.contains('expanded')) {
            icon.classList.remove('expanded');
        }
    });
    
    // 添加点击外部关闭展开内容的功能
    document.addEventListener('click', function(e) {
        const toolCalls = document.querySelectorAll('.assistant-tool-call, .tool-result-section');
        toolCalls.forEach(toolCall => {
            if (!toolCall.contains(e.target)) {
                const content = toolCall.querySelector('.assistant-tool-args.active, .tool-result-content.active');
                if (content) {
                    content.classList.remove('active');
                    const toggle = toolCall.querySelector('.assistant-tool-toggle, .collapsible-icon');
                    if (toggle) {
                        if (toggle.classList.contains('assistant-tool-toggle')) {
                            toggle.textContent = '展开参数 ▼';
                        } else {
                            toggle.classList.remove('expanded');
                        }
                    }
                }
            }
        });
    });
});

// 添加复制功能（可选）
function addCopyButtons() {
    const codeBlocks = document.querySelectorAll('.content-text, .tool-args, .tool-result-content');
    codeBlocks.forEach(block => {
        const copyButton = document.createElement('button');
        copyButton.textContent = '复制';
        copyButton.className = 'copy-button';
        copyButton.style.cssText = `
            position: absolute;
            top: 8px;
            right: 8px;
            padding: 4px 8px;
            font-size: 12px;
            background: var(--primary-color);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            opacity: 0;
            transition: opacity 0.2s;
        `;
        
        const wrapper = document.createElement('div');
        wrapper.style.position = 'relative';
        block.parentNode.insertBefore(wrapper, block);
        wrapper.appendChild(block);
        wrapper.appendChild(copyButton);
        
        wrapper.addEventListener('mouseenter', () => {
            copyButton.style.opacity = '1';
        });
        
        wrapper.addEventListener('mouseleave', () => {
            copyButton.style.opacity = '0';
        });
        
        copyButton.addEventListener('click', () => {
            navigator.clipboard.writeText(block.textContent).then(() => {
                copyButton.textContent = '已复制!';
                setTimeout(() => {
                    copyButton.textContent = '复制';
                }, 2000);
            });
        });
    });
}

// 如果需要复制功能，取消下面的注释
// document.addEventListener('DOMContentLoaded', addCopyButtons);
