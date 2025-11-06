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

// 显示错误消息
function showError(message) {
    const errorElement = document.getElementById('errorMessage');
    errorElement.textContent = message;
    errorElement.style.display = 'block';
    
    // 3秒后自动隐藏
    setTimeout(() => {
        errorElement.style.display = 'none';
    }, 5000);
}

// 显示成功消息
function showSuccess(message) {
    const successElement = document.getElementById('successMessage');
    successElement.textContent = message;
    successElement.style.display = 'block';
    
    // 3秒后自动隐藏
    setTimeout(() => {
        successElement.style.display = 'none';
    }, 5000);
}

// 显示加载状态
function showLoading() {
    document.getElementById('loading').style.display = 'flex';
}

// 隐藏加载状态
function hideLoading() {
    document.getElementById('loading').style.display = 'none';
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
    
    // 自动展开第一个工具调用（可选）
    const firstToolCall = document.querySelector('.assistant-tool-call');
    if (firstToolCall) {
        const header = firstToolCall.querySelector('.assistant-tool-header');
        if (header) {
            // 延迟一点再展开，让用户看到动画
            setTimeout(() => {
                toggleAssistantTool(header);
            }, 500);
        }
    }
    
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
