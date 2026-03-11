# 读取文件
file_path = r"e:\GraduationProject\LuminaGS\gs-ir-visualization\electron\main.js"
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 替换第 504-520 行（索引 503-519）- Windows 部分使用 PowerShell
new_code = [
    "  if (process.platform === 'win32') {\n",
    "        // Windows: 使用 PowerShell 执行 conda activate && python train.py\n",
    "      const fullCommand = `Set-Location -LiteralPath '${cwd}'; conda activate gsir; & '${envManager.pythonPath}' '${pythonScriptPath}' ${args.join(' ')}`;\n",
    "      console.log('执行完整命令:', fullCommand);\n",
    "        \n",
    "      trainingProcess = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', fullCommand], {\n",
    "          env: { ...process.env, PYTHONIOENCODING: 'utf-8' }\n",
    "        });\n",
    "    } else {\n",
    "        // Unix/Linux/macOS: 使用 bash -c \"source activate gsir && python train.py ...\"\n",
    "      const fullCommand = `cd '${cwd}' && source activate gsir && '${envManager.pythonPath}' '${pythonScriptPath}' ${args.join(' ')}`;\n",
    "      console.log('执行完整命令:', fullCommand);\n",
    "        \n",
    "      trainingProcess = spawn('bash', ['-c', fullCommand], {\n",
    "          env: { ...process.env, PYTHONIOENCODING: 'utf-8' }\n",
    "        });\n",
    "    }\n",
]

# 构建新的文件内容
final_lines = lines[:503] + new_code + lines[520:]

# 保存
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print("✓ main.js 已成功修改，改用 PowerShell 执行命令")
print(f"原行数：{len(lines)}, 新行数：{len(final_lines)}")
