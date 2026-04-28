#!/bin/bash

# 遇到任何错误立即停止脚本执行
set -e

# --- 路径配置 ---
SCENE_PATH="datasets/TensoIR/lego/"
DA3_NORMAL_ROOT="/home/zengkun/GS-IR/datasets/TensoIR/lego/marigold_final/"
HDRI_DIR="datasets/TensoIR/env_maps/high_res_envmaps_2k"

# ==========================================================
# 🎯 锁定最佳基石参数
# ==========================================================
N_TV=0.3
NL_W=0.12
BT_W=0.5
C_TH=0.5

# ==========================================================
# 🧪 定义消融组: 加入了 0.8 和 0.3 的细粒度消融
# 格式: "组名|max_prior_alpha|是否开启flatten"
# ==========================================================
EXP_GROUPS=(
    # "GroupA_alpha1.0|1.0|False"  # 👈 GroupA 你已经跑完并评估完毕了，保持注释
    # "GroupB_alpha0.8|0.8|False"
    # "GroupC_alpha0.5|0.5|False"
    # "GroupD_alpha0.3|0.3|False"
    # "GroupE_alpha0.5_flatten|0.5|True" # 👈 完全体方案
    # "GroupF_alpha1.0_flatten|1.0|True"
    # "Group1_alpha0.5|0.5|False"
    # "Group6_alpha0.5_cos0.96|0.5|False"
    # "Group7_alpha0.5_cos0.96_flatten|0.5|True"
    # "Group9_alpha0.5_cos_0.96|0.5|False"
    # "Group10_alpha0.5_cos0.91|0.5|False"
    # "Group11_alpha0.5_cos0.96|0.5|False"
    "Group12_alpha0.5_cos0.96|0.5|False"
)

# ==========================================================
# ☀️ 定义重光照白名单 (精准指定，不浪费时间渲染无用贴图)
# 根据你的评估日志，评测代码只需要以下几种标准光照
# ==========================================================
EVAL_HDRIS=("bridge" "city" "fireplace" "forest" "night" "sunset")


for group_info in "${EXP_GROUPS[@]}"; do
    # 解析参数
    IFS='|' read -r G_NAME ALPHA USE_FLATTEN <<< "$group_info"
    
    # 动态设定输出目录和扁平化参数
    OUTPUT_PATH="outputs/lego_${G_NAME}"
    FLATTEN_FLAG=""
    if [ "$USE_FLATTEN" = "True" ]; then
        FLATTEN_FLAG="--flatten_loss --lambda_flatten 0.001"
    fi
    
    echo "=========================================================================="
    echo "🚀 开始实验组: $G_NAME"
    echo "配置: --max_prior_alpha $ALPHA | Flatten: $USE_FLATTEN"
    echo "=========================================================================="

    # 1. 基础重建阶段 (Vanilla 30k)
    echo "--- Step 1: 基础训练 (30,000 Iterations) ---"
    python train.py -m $OUTPUT_PATH/ -s $SCENE_PATH \
        --iterations 30000 \
        --use_da3_normal \
        --da3_normal_root $DA3_NORMAL_ROOT \
        --normal_tv ${N_TV} \
        --normal_loss_weight ${NL_W} \
        --brdf_tv ${BT_W} \
        --conf_thresh ${C_TH} \
        --max_prior_alpha ${ALPHA} \
        ${FLATTEN_FLAG} \
        --eval

    # 2. 烘焙阶段 (Baking)
    echo "--- Step 2: 烘焙遮挡体积 ---"
    python baking.py -m $OUTPUT_PATH/ \
        --checkpoint $OUTPUT_PATH/chkpnt30000.pth \
        --bound 1.5 --occlu_res 128 --occlusion 0.25

    # 3. 物理反演阶段 (PBR/Indirect 35k)
    echo "--- Step 3: 物理反演微调 (35,000 Iterations) ---"
    python train.py -m $OUTPUT_PATH/ -s $SCENE_PATH \
        --start_checkpoint $OUTPUT_PATH/chkpnt30000.pth \
        --iterations 35000 \
        --use_da3_normal \
        --da3_normal_root $DA3_NORMAL_ROOT \
        --normal_tv ${N_TV} \
        --normal_loss_weight ${NL_W} \
        --brdf_tv ${BT_W} \
        --conf_thresh ${C_TH} \
        --max_prior_alpha ${ALPHA} \
        ${FLATTEN_FLAG} \
        --eval --gamma --indirect

    # 4-6. 评估阶段
    echo "--- Step 4-6: 渲染与基础评估 ---"
    python render.py -m $OUTPUT_PATH -s $SCENE_PATH --checkpoint $OUTPUT_PATH/chkpnt35000.pth --eval --skip_train --pbr --gamma --indirect
    python normal_eval.py --output_dir $OUTPUT_PATH/test/ours_None --gt_dir $SCENE_PATH
    python render.py -m $OUTPUT_PATH -s $SCENE_PATH --checkpoint $OUTPUT_PATH/chkpnt35000.pth --eval --skip_train --brdf_eval

    # 7. 重光照渲染 (仅白名单环境)
    echo "--- Step 7: 重光照渲染 (白名单精简版) ---"
    for hdri_name in "${EVAL_HDRIS[@]}"; do
        hdri_file="$HDRI_DIR/${hdri_name}.hdr"
        if [ -f "$hdri_file" ]; then
            echo ">> 正在渲染环境光: $hdri_name"
            python relight.py \
                -m $OUTPUT_PATH \
                -s $SCENE_PATH \
                --checkpoint $OUTPUT_PATH/chkpnt35000.pth \
                --hdri "$hdri_file" \
                --eval \
                --gamma
        else
            echo ">> ⚠️ 警告: 找不到 $hdri_file，已跳过！"
        fi
    done

    # 8. 重光照指标评估
    echo "--- Step 8: 重光照指标评估 ---"
    python relight_eval.py \
        --output_dir $OUTPUT_PATH/test/ours_None/relight/ \
        --gt_dir $SCENE_PATH

    echo "✅ 组 $G_NAME 实验完成！"
    echo ""
done

echo "🎉 全部消融实验已完成！请对比各个 Group 的结果。"