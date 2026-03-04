const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');

let mainWindow;

app.whenReady().then(() => {
  console.log('✓ Electron 应用已启动');
  console.log('✓ dialog 模块:', typeof dialog);
  console.log('✓ showOpenDialog 方法:', typeof dialog.showOpenDialog);
  
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });
  
  console.log('✓ 主窗口已创建');
  console.log('✓ mainWindow 对象:', mainWindow ? '存在' : '不存在');
  
  // 测试对话框
  setTimeout(async () => {
    try {
      console.log('开始测试对话框...');
      const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory'],
        title: '测试对话框',
        defaultPath: process.cwd()
      });
      console.log('对话框返回结果:', result);
    } catch (error) {
      console.error('对话框测试失败:', error);
    }
  }, 2000);
});
