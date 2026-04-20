#!/bin/bash

# ==========================================
# 只需修改以下变量即可使用
# ==========================================
OUTPUT_DIR="outputs/lego_dense_ours1"  # 你的输出目录
DATASET_DIR="datasets/TensoIR/lego"      # 数据集路径
HDRI_PATH="datasets/TensoIR/env_maps/high_res_envmaps_2k/bridge.hdr"  # 重光照HDRI路径

# 训练参数
GEOM_ITER=30000                           # 几何训练迭代数
TOTAL_ITER=35000                          # 总迭代数

# 烘焙参数
BAKE_BOUND=1.5                             # 烘焙边界
BAKE_OCCLU_RES=128                         # 遮挡体分辨率
BAKE_OCCLUSION=0.25                        # 遮挡阈值

# ==========================================
# 以下内容无需修改，按顺序自动执行
# ==========================================
echo "=========================================="
echo "开始完整流程：几何训练 -> 烘焙 -> BRDF训练 -> 渲染 -> 评估"
echo "输出目录: $OUTPUT_DIR"
echo "=========================================="

# 1. 第一阶段：初始几何训练（0 -> 30k）
GEOM_CKPT="$OUTPUT_DIR/chkpnt${GEOM_ITER}.pth"
if [ -f "$GEOM_CKPT" ]; then
    echo ">>> [1/9] ⏭️  跳过几何训练：检查点已存在 ($GEOM_CKPT)"
else
    echo ">>> [1/9] 第一阶段：初始几何训练 (0 -> ${GEOM_ITER} iter)..."
    python train.py \
    -m $OUTPUT_DIR \
    -s $DATASET_DIR \
    --iterations $GEOM_ITER \
    --eval || { echo "几何训练失败！"; exit 1; }
fi

# 2. 烘焙阶段（Baking）
OCCLUSION_FILE="$OUTPUT_DIR/occlusion_volumes.pth"
if [ -f "$OCCLUSION_FILE" ]; then
    echo ">>> [2/9] ⏭️  跳过烘焙：遮挡体文件已存在 ($OCCLUSION_FILE)"
else
    echo ">>> [2/9] 第二阶段：烘焙遮挡体..."
    python baking.py \
    -m $OUTPUT_DIR \
    --checkpoint $OUTPUT_DIR/chkpnt${GEOM_ITER}.pth \
    --bound $BAKE_BOUND \
    --occlu_res $BAKE_OCCLU_RES \
    --occlusion $BAKE_OCCLUSION || { echo "烘焙失败！"; exit 1; }
fi

# 3. 第二阶段：BRDF/光照训练（30k -> 35k）
FINAL_CKPT="$OUTPUT_DIR/chkpnt${TOTAL_ITER}.pth"
if [ -f "$FINAL_CKPT" ]; then
    echo ">>> [3/9] ⏭️  跳过BRDF训练：检查点已存在 ($FINAL_CKPT)"
else
    echo ">>> [3/9] 第三阶段：BRDF/光照训练 (${GEOM_ITER} -> ${TOTAL_ITER} iter)..."
    python train.py \
    -m $OUTPUT_DIR \
    -s $DATASET_DIR \
    --start_checkpoint $OUTPUT_DIR/chkpnt${GEOM_ITER}.pth \
    --iterations $TOTAL_ITER \
    --indirect \
    --gamma \
    --eval || { echo "BRDF训练失败！"; exit 1; }
fi

# 4. PBR 渲染
echo ">>> [4/9] 执行 PBR 渲染..."
python render.py \
-m $OUTPUT_DIR \
-s $DATASET_DIR \
--checkpoint $OUTPUT_DIR/chkpnt${TOTAL_ITER}.pth \
--eval \
--skip_train \
--pbr \
--gamma \
--indirect || { echo "PBR 渲染失败！"; exit 1; }

# 5. 法线评估
echo ">>> [5/9] 执行法线评估..."
python normal_eval.py \
--output_dir $OUTPUT_DIR/test/ours_None \
--gt_dir $DATASET_DIR || { echo "法线评估失败！"; exit 1; }

# 6. BRDF 反照率评估
echo ">>> [6/9] 执行 BRDF 反照率评估..."
python render.py \
-m $OUTPUT_DIR \
-s $DATASET_DIR \
--checkpoint $OUTPUT_DIR/chkpnt${TOTAL_ITER}.pth \
--eval \
--skip_train \
--brdf_eval || { echo "BRDF 评估失败！"; exit 1; }

# 7. 重光照渲染
echo ">>> [7/9] 执行重光照渲染..."
python relight.py \
-m $OUTPUT_DIR \
-s $DATASET_DIR \
--checkpoint $OUTPUT_DIR/chkpnt${TOTAL_ITER}.pth \
--hdri $HDRI_PATH \
--eval \
--gamma || { echo "重光照渲染失败！"; exit 1; }

# 8. 重光照评估
echo ">>> [8/9] 执行重光照评估..."
python relight_eval.py \
--output_dir $OUTPUT_DIR/test/ours_None/relight/ \
--gt_dir $DATASET_DIR || { echo "重光照评估失败！"; exit 1; }

echo "=========================================="
echo "✅ 所有流程执行完成！"
echo "输出目录: $OUTPUT_DIR"
echo "=========================================="