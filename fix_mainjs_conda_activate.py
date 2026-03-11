import re

file_path = r"e:\GraduationProject\LuminaGS\gs-ir-visualization\electron\main.js"

# 读取文件
with open(file_path, 'r', encoding='utf-8') as f:
   lines = f.readlines()

# 找到要替换的行范围 (495-505 行，索引从 0 开始是 494-504)
print(f"原始代码 (行 495-505):")
for i in range(494, 506):
    print(f"{i+1}: {repr(lines[i])}")

# 构建新的代码
new_lines = []
indent = "    "  # 4 个空格

new_lines.append(lines[494])  # console.log 行
new_lines.append(lines[495])  # 空行
new_lines.append(lines[496])  # // 标记训练已激活注释
new_lines.append(lines[497])  # isTrainingActive = true;
new_lines.append(lines[498])  # 空行
new_lines.append(f"{indent}// 构建完整的命令：先激活 conda 环境，再执行 Python 脚本\n")
new_lines.append(f"{indent}const pythonScriptPath = path.join(__dirname, '../../GS-IR/train.py');\n")
new_lines.append(f"{indent}const cwd = path.join(__dirname, '../../GS-IR');\n")
new_lines.append(f"\n")
new_lines.append(f"{indent}if (process.platform === 'win32') {{\n")
new_lines.append(f"{indent}  // Windows: 使用 cmd /c \"cd /d <dir> && conda activate gsir && python train.py ...\"\n")
new_lines.append(f"{indent} const fullCommand = `cd /d \"${{cwd}}\" && conda activate gsir && \"${{envManager.pythonPath}}\" \"${{pythonScriptPath}}\" ${{args.join(' ')}}`;\n")
new_lines.append(f"{indent} console.log('执行完整命令:', fullCommand);\n")
new_lines.append(f"\n")
new_lines.append(f"{indent} trainingProcess= spawn('cmd.exe', ['/c', fullCommand], {{\n")
new_lines.append(f"{indent}  env: {{ ...process.env, PYTHONIOENCODING: 'utf-8' }}\n")
new_lines.append(f"{indent} }});\n")
new_lines.append(f"{indent}}} else {{\n")
new_lines.append(f"{indent}  // Unix/Linux/macOS: 使用 bash -c \"source activate gsir && python train.py ...\"\n")
new_lines.append(f"{indent} const fullCommand = `cd \"${{cwd}}\" && source activate gsir && \"${{envManager.pythonPath}}\" \"${{pythonScriptPath}}\" ${{args.join(' ')}}`;\n")
new_lines.append(f"{indent} console.log('执行完整命令:', fullCommand);\n")
new_lines.append(f"\n")
new_lines.append(f"{indent} trainingProcess= spawn('bash', ['-c', fullCommand], {{\n")
new_lines.append(f"{indent}  env: {{ ...process.env, PYTHONIOENCODING: 'utf-8' }}\n")
new_lines.append(f"{indent} }});\n")
new_lines.append(f"{indent}}}\n")

# 替换旧代码（删除原来的 500-505 行）
final_lines = new_lines + lines[505:]

# 保存修改后的文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print("\n✓ main.js 已成功修改，添加了 conda activate gsir 步骤")
print("修改内容:")
print("  - Windows: cd /d <dir> && conda activate gsir && python train.py ...")
print("  - Unix: cd <dir> && source activate gsir && python train.py ...")
