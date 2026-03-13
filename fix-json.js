const fs = require('fs');
const path = require('path');

// 修复损坏的 JSON 文件
async function fixCorruptedJson(filePath) {
  try {
    console.log(`正在检查文件：${filePath}`);
    
    // 读取文件内容
    const content = await fs.promises.readFile(filePath, 'utf8');
    
    // 尝试解析，如果成功说明文件完好
    try {
      JSON.parse(content);
      console.log('✓ 文件格式正确');
      return true;
    } catch (parseError) {
      console.log(`✗ 文件格式错误：${parseError.message}`);
    }
    
    // 尝试修复常见的 JSON 错误
    let fixedContent = content;
    
    // 1. 移除末尾多余的逗号
    fixedContent = fixedContent.replace(/,\s*}/g, '}');
    
    // 2. 检测并移除重复的字段
    const lines = fixedContent.split('\n');
    const seenKeys = new Set();
    const filteredLines = [];
    let braceCount = 0;
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const match = line.match(/^\s*"([^"]+)":/);
      
      if (match) {
        const key = match[1];
        
        // 如果在最外层对象中已经见过这个键，跳过这一行
        if (braceCount === 1 && seenKeys.has(key)) {
          console.log(`  发现重复字段 "${key}"，已移除`);
          continue;
        }
        
        if (braceCount === 1) {
          seenKeys.add(key);
        }
      }
      
      // 跟踪大括号层级
      braceCount += (line.match(/{/g) || []).length;
      braceCount -= (line.match(/}/g) || []).length;
      
      filteredLines.push(line);
    }
    
    fixedContent = filteredLines.join('\n');
    
    // 3. 再次验证
    try {
      const parsed = JSON.parse(fixedContent);
      console.log('✓ 文件已修复');
      
      // 写回修复后的内容
      await fs.promises.writeFile(filePath, fixedContent, 'utf8');
      console.log(`✓ 已保存修复后的文件`);
      
      return true;
    } catch (error) {
      console.error(`✗ 修复失败：${error.message}`);
      console.error('尝试手动修复或从备份恢复');
      return false;
    }
  } catch (error) {
    console.error(`✗ 读取文件失败：${error.message}`);
    return false;
  }
}

// 批量修复 .luminags 目录下的所有 JSON 文件
async function fixAllJsonFiles(luminaDir) {
  try {
    const files = await fs.promises.readdir(luminaDir);
    const jsonFiles = files.filter(f => f.endsWith('.json'));
    
    console.log(`找到 ${jsonFiles.length} 个 JSON 文件\n`);
    
    let successCount = 0;
    let failCount = 0;
    
    for (const file of jsonFiles) {
      const filePath = path.join(luminaDir, file);
      console.log(`\n处理：${file}`);
      const result = await fixCorruptedJson(filePath);
      if (result) {
        successCount++;
      } else {
        failCount++;
      }
    }
    
    console.log(`\n========== 修复完成 ==========`);
    console.log(`成功：${successCount} 个文件`);
    console.log(`失败：${failCount} 个文件`);
  } catch (error) {
    console.error(`错误：${error.message}`);
  }
}

// 主函数
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.log('用法:');
    console.log('  node fix-json.js <单个文件路径>');
    console.log('  node fix-json.js --all <.luminags 目录路径>');
    console.log('\n示例:');
    console.log('  node fix-json.js "E:\\Test\\project.json"');
    console.log('  node fix-json.js --all "E:\\Test\\.luminags"');
    process.exit(1);
  }
  
  if (args[0] === '--all') {
    const dirPath = args[1];
    if (!dirPath) {
      console.error('错误：请提供 .luminags 目录路径');
      process.exit(1);
    }
    await fixAllJsonFiles(dirPath);
  } else {
    const filePath = args[0];
    await fixCorruptedJson(filePath);
  }
}

main();
