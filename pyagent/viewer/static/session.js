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
    document.getElementById('loading').style.display = 'block';
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('successMessage').style.display = 'none';
    
    // 发送请求
    fetch('/import-database', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('loading').style.display = 'none';
        
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
        document.getElementById('loading').style.display = 'none';
        showError('导入失败: ' + error.message);
    });
}

function showError(message) {
    const errorElement = document.getElementById('errorMessage');
    errorElement.textContent = message;
    errorElement.style.display = 'block';
}

function showSuccess(message) {
    const successElement = document.getElementById('successMessage');
    successElement.textContent = message;
    successElement.style.display = 'block';
}