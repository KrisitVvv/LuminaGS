# 修复 main.js 中的训练启动命令，添加 conda activate gsir

$filePath = "e:\GraduationProject\LuminaGS\gs-ir-visualization\electron\main.js"

# 读取文件内容
$content = Get-Content -Path $filePath -Raw -Encoding UTF8

# 定义旧代码块（要替换的内容）
$oldCode = @'
   console.log('启动训练进程:', envManager.pythonPath, args.join(' '));
    
    // 标记训练已激活
    isTrainingActive = true;
    
    // 使用环境管理器运行 Python 脚本
   trainingProcess= envManager.runPythonScript(
      path.join(__dirname, '../../GS-IR/train.py'),
     args,
      { cwd: path.join(__dirname, '../../GS-IR') }
    );
'@

# 定义新代码块（替换后的内容）
$newCode = @'
   console.log('启动训练进程:', envManager.pythonPath, args.join(' '));
    
    // 标记训练已激活
    isTrainingActive = true;
    
    // 构建完整的命令：先激活 conda 环境，再执行 Python 脚本
  const pythonScriptPath = path.join(__dirname, '../../GS-IR/train.py');
  const cwd = path.join(__dirname, '../../GS-IR');
    
  if (process.platform === 'win32') {
      // Windows: 使用 cmd /c "cd /d <dir> && conda activate gsir && python train.py ..."
    const fullCommand = `cd /d "${cwd}" && conda activate gsir && "${envManager.pythonPath}" "${pythonScriptPath}" ${args.join(' ')}`;
    console.log('执行完整命令:', fullCommand);
      
    trainingProcess= spawn('cmd.exe', ['/c', fullCommand], {
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
      });
    } else {
      // Unix/Linux/macOS: 使用 bash -c "source activate gsir && python train.py ..."
    const fullCommand = `cd "${cwd}" && source activate gsir && "${envManager.pythonPath}" "${pythonScriptPath}" ${args.join(' ')}`;
    console.log('执行完整命令:', fullCommand);
      
    trainingProcess = spawn('bash', ['-c', fullCommand], {
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
      });
    }
'@

# 执行替换
$newContent = $content.Replace($oldCode, $newCode)

# 检查是否成功替换
if ($newContent -eq $content) {
    Write-Host "错误：未找到匹配的代码块，替换失败" -ForegroundColor Red
    exit 1
}

# 保存修改后的文件
$newContent | Out-File -FilePath $filePath -Encoding UTF8 -NoNewline

Write-Host "✓ main.js 已成功修改，添加了 conda activate gsir 步骤" -ForegroundColor Green
Write-Host "修改内容:" -ForegroundColor Yellow
Write-Host "  - Windows: cd /d <dir> && conda activate gsir && python train.py ..."
Write-Host "  - Unix: cd <dir> && source activate gsir && python train.py ..."
