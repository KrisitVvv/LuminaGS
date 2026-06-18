#!/bin/bash

# 遇到任何错误立即停止脚本执行
set -e

# --- 路径配置 ---
SCENE_PATH="datasets/TensoIR/lego/"
OUTPUT_PATH="outputs/lego_gt_v10"
HDRI_PATH="datasets/TensoIR/env_maps/high_res_envmaps_2k/bridge.hdr"

echo "🚀 开始 GS-IR 完整流水线实验: $OUTPUT_PATH"

# 1. 基础重建阶段 (Vanilla 30k)
echo "--- Step 1: 基础训练 (30,000 Iterations) ---"
python train.py -m $OUTPUT_PATH/ -s $SCENE_PATH --iterations 30000 -r 1 --normal_tv 0.1 --eval

# 2. 烘焙阶段 (Baking)
echo "--- Step 2: 烘焙遮挡体积 (Baking) ---"
python baking.py -m $OUTPUT_PATH/ --checkpoint $OUTPUT_PATH/chkpnt30000.pth --bound 1.5 --occlu_res 128 --occlusion 0.25

# 3. 物理反演阶段 (PBR/Indirect 35k)
echo "--- Step 3: 物理反演微调 (35,000 Iterations) ---"
python train.py -m $OUTPUT_PATH/ -s $SCENE_PATH --start_checkpoint $OUTPUT_PATH/chkpnt30000.pth --iterations 35000 -r 1 --normal_tv 0.1 --eval --gamma --indirect

# 4. 最终 PBR 渲染评估
echo "--- Step 4: 最终 PBR 渲染测试 ---"
python render.py -m $OUTPUT_PATH -s $SCENE_PATH --checkpoint $OUTPUT_PATH/chkpnt35000.pth -r 1 --eval --skip_train --pbr --gamma --indirect

# 5. 法线精度评估 (Normal Eval)
echo "--- Step 5: 法线误差评估 (Normal MAE) ---"
python normal_eval.py --output_dir $OUTPUT_PATH/test/ours_None --gt_dir $SCENE_PATH

# 6. 材质评估 (BRDF/Albedo Eval)
echo "--- Step 6: 材质解耦评估 (Albedo) ---"
python render.py -m $OUTPUT_PATH -s $SCENE_PATH --checkpoint $OUTPUT_PATH/chkpnt35000.pth -r 1 --eval --skip_train --brdf_eval

# 7. 重光照阶段 (Relighting)
#echo "--- Step 7: 重光照渲染 (Bridge HDR) ---"
#python relight.py -m $OUTPUT_PATH -s $SCENE_PATH --checkpoint $OUTPUT_PATH/chkpnt35000.pth --hdri $HDRI_PATH --eval --gamma

# 8. 重光照精度评估 (Relighting Eval)
#echo "--- Step 8: 重光照定量评估 ---"
#python relight_eval.py --output_dir $OUTPUT_PATH/test/ours_None/relight/ --gt_dir $SCENE_PATH

echo "✅ 实验全部完成！所有结果均已存入: $OUTPUT_PATH"