const fs = require('fs');

// 简单粗暴地修复 JSON - 直接读取并重新序列化
async function fixJson(filePath) {
  try {
    console.log(`正在修复：${filePath}`);
    
    // 读取文件
    const content = await fs.promises.readFile(filePath, 'utf8');
    
    // 尝试找到第一个完整的 JSON 对象
    // 通过计算大括号匹配来提取有效 JSON
    let braceCount = 0;
    let endIndex = -1;
    
    for (let i = 0; i < content.length; i++) {
      if (content[i] === '{') braceCount++;
      if (content[i] === '}') braceCount--;
      
      if (braceCount === 0 && content[i] === '}') {
        endIndex = i + 1;
        break;
      }
    }
    
    if (endIndex === -1) {
      console.error('✗ 无法找到完整的 JSON 对象');
      return false;
    }
    
    // 提取第一个完整的 JSON 对象
    const jsonStr = content.substring(0, endIndex);
    
    // 验证是否有效
    const parsed = JSON.parse(jsonStr);
    console.log('✓ JSON 解析成功');
    
    // 重新格式化并保存
    const formatted = JSON.stringify(parsed, null, 2);
    await fs.promises.writeFile(filePath, formatted, 'utf8');
    console.log('✓ 文件已修复并保存');
    
    return true;
  } catch (error) {
    console.error(`✗ 修复失败：${error.message}`);
    return false;
  }
}

// 运行
const filePath = process.argv[2];
if (!filePath) {
  console.error('用法：node simple-fix.js <json文件路径>');
  process.exit(1);
}

fixJson(filePath);
