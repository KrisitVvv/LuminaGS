import re
with open('/home/zengkun/LuminaGS/GS-IR/train.py', 'r') as f:
    content = f.read()

old_block = """            # Densification
            should_densify = iteration < opt.densify_until_iter if dataset.is_baseline else (iteration < opt.densify_until_iter and iteration <= 15000)
            if should_densify:
                # --- 2. 硬件防爆断路器 (Circuit Breaker) ---
                current_gaussians_count = gaussians.get_xyz.shape[0]
                
                if dataset.is_baseline:
                    dynamic_threshold = opt.densify_grad_threshold
                else:
                    dynamic_threshold = opt.densify_grad_threshold if iteration <= 5000 else opt.densify_grad_threshold * 2.0
                    # 12GB 显存红线保护机制，超过 300W 停止分裂
                    # if current_gaussians_count > 3000000:
                    #     dynamic_threshold = float('inf')
                
                # Keep track of max radii in image-space for pruning
                gaussians.max_radii2D[visibility_filter] = torch.max(
                    gaussians.max_radii2D[visibility_filter], radii[visibility_filter]
                )
                gaussians.add_densification_stats(viewspace_point_tensor, visibility_filter)

                if (
                    iteration > opt.densify_from_iter
                    and iteration % opt.densification_interval == 0
                ):
                    size_threshold = 20 if iteration > opt.opacity_reset_interval else None
                    grads = gaussians.xyz_gradient_accum / gaussians.denom
                    grads[grads.isnan()] = 0.0

                    # 保留原版克隆和切分逻辑
                    gaussians.densify_and_clone(grads, opt.densify_grad_threshold, scene.cameras_extent)
                    gaussians.densify_and_split(grads, opt.densify_grad_threshold, scene.cameras_extent)
                    
                    # 🚀 替换为调用新的自适应剪枝策略！
                    if iteration < int(opt.iterations * 0.8):
                        gaussians.prune_gs_ir_custom(
                            min_opacity=opt.min_opacity,
                            extent=scene.cameras_extent,
                            max_screen_size=size_threshold,
                            prune_quantile=opt.prune_quantile
                        )

                if iteration % opt.opacity_reset_interval == 0 or ("""

new_block = """            # Densification
            if iteration < opt.densify_until_iter:
                # Keep track of max radii in image-space for pruning
                gaussians.max_radii2D[visibility_filter] = torch.max(
                    gaussians.max_radii2D[visibility_filter], radii[visibility_filter]
                )
                gaussians.add_densification_stats(viewspace_point_tensor, visibility_filter)

                if (
                    iteration > opt.densify_from_iter
                    and iteration % opt.densification_interval == 0
                ):
                    size_threshold = 20 if iteration > opt.opacity_reset_interval else None
                    grads = gaussians.xyz_gradient_accum / gaussians.denom
                    grads[grads.isnan()] = 0.0

                    gaussians.densify_and_clone(grads, opt.densify_grad_threshold, scene.cameras_extent)
                    gaussians.densify_and_split(grads, opt.densify_grad_threshold, scene.cameras_extent)
                    
                    if iteration < int(opt.iterations * 0.8):
                        gaussians.prune_gs_ir_custom(
                            min_opacity=opt.min_opacity,
                            extent=scene.cameras_extent,
                            max_screen_size=size_threshold,
                            prune_quantile=opt.prune_quantile
                        )

                if iteration % opt.opacity_reset_interval == 0 or ("""

# Replace preserving newlines
content = content.replace(old_block, new_block)
with open('/home/zengkun/LuminaGS/GS-IR/train.py', 'w') as f:
    f.write(content)
