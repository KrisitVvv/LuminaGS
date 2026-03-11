# 读取文件
file_path = r"e:\GraduationProject\LuminaGS\gs-ir-visualization\electron\main.js"
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 替换第 500-505 行（索引 499-504）
# 保留 495-499 行不变
# 从 506 行开始保留不变

new_code = [
    "   console.log('启动训练进程:', envManager.pythonPath, args.join(' '));\n",
    "    \n",
    "    // 标记训练已激活\n",
    "    isTrainingActive = true;\n",
    "    \n",
    "    // 构建完整的命令：先激活 conda 环境，再执行 Python 脚本\n",
    "   const pythonScriptPath = path.join(__dirname, '../../GS-IR/train.py');\n",
    "   const cwd = path.join(__dirname, '../../GS-IR');\n",
    "    \n",
    "   if (process.platform === 'win32') {\n",
    "        // Windows: 使用 cmd /c \"cd /d <dir> && conda activate gsir && python train.py ...\"\n",
    "       const fullCommand = `cd /d \"${cwd}\" && conda activate gsir && \"${envManager.pythonPath}\" \"${pythonScriptPath}\" ${args.join(' ')}`;\n",
    "       console.log('执行完整命令:', fullCommand);\n",
    "        \n",
    "       trainingProcess = spawn('cmd.exe', ['/c', fullCommand], {\n",
    "           env: { ...process.env, PYTHONIOENCODING: 'utf-8' }\n",
    "        });\n",
    "    } else {\n",
    "        // Unix/Linux/macOS: 使用 bash -c \"source activate gsir && python train.py ...\"\n",
    "       const fullCommand = `cd \"${cwd}\" && source activate gsir && \"${envManager.pythonPath}\" \"${pythonScriptPath}\" ${args.join(' ')}`;\n",
    "       console.log('执行完整命令:', fullCommand);\n",
    "        \n",
    "       trainingProcess = spawn('bash', ['-c', fullCommand], {\n",
    "           env: { ...process.env, PYTHONIOENCODING: 'utf-8' }\n",
    "        });\n",
    "    }\n",
]

# 构建新的文件内容
final_lines = lines[:494] + new_code + lines[505:]

# 保存
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print("✓ main.js 已成功修改")
print(f"原行数：{len(lines)}, 新行数：{len(final_lines)}")
