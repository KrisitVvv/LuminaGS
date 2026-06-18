#!/bin/bash

# 遇到任何错误立即停止脚本执行
set -e

# --- 路径配置 ---
SCENE_PATH="datasets/TensoIR/lego/"
DA3_NORMAL_ROOT="/home/zengkun/LuminaGS/GS-IR-main/GS-IR/datasets/TensoIR/lego/da3_normal"

# --- DA3法线优化参数（基于GT版微调）---
NORMAL_TVS=(0.5)          
NORMAL_LOSS_WEIGHTS=(0.06) 
BRDF_TVS=(0.35)             

for n_tv in "${NORMAL_TVS[@]}"; do
    for nl_w in "${NORMAL_LOSS_WEIGHTS[@]}"; do
        for bt_w in "${BRDF_TVS[@]}"; do
            OUTPUT_PATH="outputs/lego_da3_n${n_tv}_nl${nl_w}_bt${bt_w}"
            echo "=========================================================================="
            echo "🚀 开始DA3法线实验: $OUTPUT_PATH"
            echo "参数设置: --normal_tv ${n_tv} | --normal_loss_weight ${nl_w} | --brdf_tv ${bt_w}"
            echo "=========================================================================="

            # 1. 基础重建阶段 (Vanilla 30k)
            echo "--- Step 1: 基础训练 (30,000 Iterations) ---"
            python train.py \
                -m $OUTPUT_PATH/ \
                -s $SCENE_PATH \
                --iterations 30000 \
                --normal_tv ${n_tv} \
                --normal_loss_weight ${nl_w} \
                --brdf_tv ${bt_w} \
                --conf_thresh 0.5 \
                --depth_grad_thresh 0.08 \
                --use_da3_normal \
                --da3_normal_root $DA3_NORMAL_ROOT \
                --eval

            # 2. 烘焙阶段 (Baking)
            echo "--- Step 2: 烘焙遮挡体积 (Baking) ---"
            python baking.py \
                -m $OUTPUT_PATH/ \
                --checkpoint $OUTPUT_PATH/chkpnt30000.pth \
                --bound 1.5 \
                --occlu_res 128 \
                --occlusion 0.25

            # 3. 物理反演阶段 (PBR/Indirect 35k)
            echo "--- Step 3: 物理反演微调 (35,000 Iterations) ---"
            python train.py \
                -m $OUTPUT_PATH/ \
                -s $SCENE_PATH \
                --start_checkpoint $OUTPUT_PATH/chkpnt30000.pth \
                --iterations 35000 \
                --normal_tv ${n_tv} \
                --normal_loss_weight ${nl_w} \
                --brdf_tv ${bt_w} \
                --conf_thresh 0.5 \
                --depth_grad_thresh 0.08 \
                --use_da3_normal \
                --da3_normal_root $DA3_NORMAL_ROOT \
                --eval \
                --gamma \
                --indirect

            # 4. 最终 PBR 渲染评估
            echo "--- Step 4: 最终 PBR 渲染测试 ---"
            python render.py \
                -m $OUTPUT_PATH \
                -s $SCENE_PATH \
                --checkpoint $OUTPUT_PATH/chkpnt35000.pth \
                --eval \
                --skip_train \
                --pbr \
                --gamma \
                --indirect

            # 5. 法线精度评估 (Normal Eval)
            echo "--- Step 5: 法线误差评估 (Normal MAE) ---"
            python normal_eval.py --output_dir $OUTPUT_PATH/test/ours_None --gt_dir $SCENE_PATH

            # 6. 材质评估 (BRDF/Albedo Eval)
            echo "--- Step 6: 材质解耦评估 (Albedo) ---"
            python render.py -m $OUTPUT_PATH -s $SCENE_PATH --checkpoint $OUTPUT_PATH/chkpnt35000.pth --eval --skip_train --brdf_eval
        done
    done
done
