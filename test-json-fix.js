// 测试 JSON 解析错误修复功能
const fs = require('fs').promises;
const path = require('path');

// 模拟损坏的 JSON 文件内容
const testCases = [
  {
    name: '正常 JSON',
    content: JSON.stringify({ name: 'test', value: 123 }, null, 2),
    shouldPass: true
  },
  {
    name: '有额外逗号的 JSON',
    content: `{
  "name": "test",
  "value": 123
},
  "status": "completed"
}`,
    shouldPass: true  // 应该能自动修复
  },
  {
    name: '重复字段',
    content: `{
  "name": "test",
  "value": 123
},
  "name": "test2",
  "value": 456
}`,
    shouldPass: true  // 应该能提取第一个完整对象
  },
  {
    name: '空文件',
    content: '',
    shouldPass: false  // 无法修复
  },
  {
    name: '不完整的 JSON',
    content: '{"name": "test"',
    shouldPass: false  // 无法修复
  }
];

// 模拟 projectManager 的修复逻辑
function tryFixJson(content) {
  console.log('\n===== 尝试修复 JSON =====');
  console.log('文件内容预览:', content.substring(0, 200));
  
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
  
  if (endIndex !== -1) {
    const jsonStr = content.substring(0, endIndex);
    console.log('提取的 JSON:', jsonStr.substring(0, 100));
    try {
      const parsed = JSON.parse(jsonStr);
      console.log('✓ JSON 修复成功');
      return { success: true, data: parsed };
    } catch (fixError) {
      console.error('✗ JSON 修复失败:', fixError.message);
      return { success: false, error: fixError.message };
    }
  } else {
    console.error('✗ 无法找到完整的 JSON 对象');
    return { success: false, error: '无法找到完整的 JSON 对象' };
  }
}

// 运行测试
async function runTests() {
  console.log('开始测试 JSON 解析错误修复功能\n');
  console.log('=' .repeat(50));
  
  let passedTests = 0;
  let totalTests = testCases.length;
  
  for (const testCase of testCases) {
    console.log(`\n测试 ${passedTests + 1}: ${testCase.name}`);
    console.log('-'.repeat(50));
    
    try {
      // 尝试直接解析
      let parsed;
      try {
        parsed = JSON.parse(testCase.content);
        console.log('✓ 直接解析成功');
      } catch (parseError) {
        console.log('✗ 直接解析失败:', parseError.message);
        
        // 尝试修复
        const fixResult = tryFixJson(testCase.content);
        if (fixResult.success) {
          parsed = fixResult.data;
        } else {
          throw new Error(`修复失败：${fixResult.error}`);
        }
      }
      
      // 检查结果是否符合预期
      if (testCase.shouldPass) {
        console.log(`✓ 测试通过（符合预期）`);
        passedTests++;
      } else {
        console.log(`✗ 测试失败（预期失败但实际成功）`);
      }
      
    } catch (error) {
      console.log(`✗ 测试失败:`, error.message);
      
      if (!testCase.shouldPass) {
        console.log(`✓ 符合预期（确实无法修复）`);
        passedTests++;
      }
    }
  }
  
  // 总结
  console.log('\n' + '='.repeat(50));
  console.log(`测试完成：${passedTests}/${totalTests} 通过`);
  console.log('='.repeat(50));
  
  if (passedTests === totalTests) {
    console.log('✓ 所有测试通过！');
  } else {
    console.log('✗ 部分测试失败，请检查修复逻辑');
  }
}

// 实际文件测试
async function testRealFile(filePath) {
  console.log('\n===== 测试真实文件 =====');
  console.log('文件路径:', filePath);
  
  try {
    const content = await fs.readFile(filePath, 'utf8');
    console.log('文件大小:', content.length, '字节');
    
    // 尝试解析
    try {
      const parsed = JSON.parse(content);
      console.log('✓ 文件解析成功');
      console.log('项目名称:', parsed.name);
      console.log('项目状态:', parsed.status);
      return true;
    } catch (parseError) {
      console.log('✗ 文件解析失败:', parseError.message);
      
      // 尝试修复
      const fixResult = tryFixJson(content);
      if (fixResult.success) {
        console.log('✓ 文件修复成功');
        console.log('修复后的项目名称:', fixResult.data.name);
        
        // 保存修复后的文件
        const repairedPath = filePath.replace('.json', '.repaired.json');
        await fs.writeFile(repairedPath, JSON.stringify(fixResult.data, null, 2), 'utf8');
        console.log('✓ 修复后的文件已保存:', repairedPath);
        return true;
      } else {
        console.log('✗ 文件修复失败');
        return false;
      }
    }
  } catch (error) {
    console.error('✗ 读取文件失败:', error.message);
    return false;
  }
}

// 主函数
(async () => {
  // 1. 运行单元测试
  await runTests();
  
  // 2. 测试真实的项目配置文件
  const realFile = 'e:/GraduationProject/Testoutput/.luminags/project_20260313_031_20260313_0318_ggu.json';
  const fileExists = await fs.access(realFile).then(() => true).catch(() => false);
  
  if (fileExists) {
    await testRealFile(realFile);
  } else {
    console.log('\n跳过真实文件测试（文件不存在）');
  }
})();
