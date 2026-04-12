#!/bin/bash

# 遇到任何错误立即停止脚本执行
set -e

# --- 路径配置 ---
SCENE_PATH="datasets/TensoIR/lego/"

# 消融测试参数组合
NORMAL_TVS=(0.3)
NORMAL_LOSS_WEIGHTS=(0.15)

for n_tv in "${NORMAL_TVS[@]}"; do
    for nl_w in "${NORMAL_LOSS_WEIGHTS[@]}"; do
        
        # OUTPUT_PATH="outputs/lego_gt_n${n_tv}_nl${nl_w}"
        OUTPUT_PATH="outputs/lego_step3_autoTVloss_adapted"
        echo "=========================================================================="
        echo "🚀 开始消融实验: $OUTPUT_PATH"
        echo "参数设置: --normal_tv ${n_tv} | --normal_loss_weight ${nl_w}"
        echo "=========================================================================="

        # 1. 基础重建阶段 (Vanilla 30k)
        echo "--- Step 1: 基础训练 (30,000 Iterations) ---"
        python train.py -m $OUTPUT_PATH/ -s $SCENE_PATH --iterations 30000 --normal_tv ${n_tv} --normal_loss_weight ${nl_w} --eval

        # 2. 烘焙阶段 (Baking)
        echo "--- Step 2: 烘焙遮挡体积 (Baking) ---"
        python baking.py -m $OUTPUT_PATH/ --checkpoint $OUTPUT_PATH/chkpnt30000.pth --bound 1.5 --occlu_res 128 --occlusion 0.25

        # 3. 物理反演阶段 (PBR/Indirect 35k)
        echo "--- Step 3: 物理反演微调 (35,000 Iterations) ---"
        python train.py -m $OUTPUT_PATH/ -s $SCENE_PATH --start_checkpoint $OUTPUT_PATH/chkpnt30000.pth --iterations 35000 --normal_tv ${n_tv} --normal_loss_weight ${nl_w} --eval --gamma --indirect

        # 4. 最终 PBR 渲染评估
        echo "--- Step 4: 最终 PBR 渲染测试 ---"
        python render.py -m $OUTPUT_PATH -s $SCENE_PATH --checkpoint $OUTPUT_PATH/chkpnt35000.pth --eval --skip_train --pbr --gamma --indirect

        # 5. 法线精度评估 (Normal Eval)
        echo "--- Step 5: 法线误差评估 (Normal MAE) ---"
        python normal_eval.py --output_dir $OUTPUT_PATH/test/ours_None --gt_dir $SCENE_PATH

        # 6. 材质评估 (BRDF/Albedo Eval)
        echo "--- Step 6: 材质解耦评估 (Albedo) ---"
        python render.py -m $OUTPUT_PATH -s $SCENE_PATH --checkpoint $OUTPUT_PATH/chkpnt35000.pth --eval --skip_train --brdf_eval

        echo "✅ 完成该组消融实验，结果已存入: $OUTPUT_PATH"
        echo ""

    done
done

echo "🎉 所有消融测试均已完成！"
