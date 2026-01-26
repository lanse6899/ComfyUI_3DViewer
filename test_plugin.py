#!/usr/bin/env python3
"""
ComfyUI 3D查看器插件测试脚本
用于验证插件是否能正确找到和启动3D查看器
"""

import os
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.append(str(Path(__file__).parent))

def test_plugin():
    """测试插件功能"""
    print("=== ComfyUI 3D查看器插件测试 ===\n")

    # 导入插件
    try:
        from ComfyUI_3DViewer import NODE_CLASS_MAPPINGS
        print("✅ 插件导入成功")
        print(f"   注册的节点: {list(NODE_CLASS_MAPPINGS.keys())}")
    except ImportError as e:
        print(f"❌ 插件导入失败: {e}")
        return

    # 创建节点实例
    try:
        node_class = NODE_CLASS_MAPPINGS["Open3DViewer"]
        node = node_class()
        print("✅ 节点创建成功")
    except Exception as e:
        print(f"❌ 节点创建失败: {e}")
        return

    # 测试路径查找
    print("\n=== 路径查找测试 ===")

    # 当前插件目录
    plugin_dir = Path(__file__).parent
    print(f"插件目录: {plugin_dir}")

    # 可能的路径
    test_file = "ve2.html"
    possible_paths = [
        plugin_dir / test_file,
        plugin_dir.parent / test_file,
        plugin_dir.parent.parent / test_file,
        plugin_dir.parent.parent.parent / test_file
    ]

    print(f"\n查找文件: {test_file}")
    for i, path in enumerate(possible_paths, 1):
        exists = path.exists()
        status = "✅ 存在" if exists else "❌ 不存在"
        print(f"   {i}. {status}: {path}")

    # 检查实际存在的文件
    found_paths = [p for p in possible_paths if p.exists()]
    if found_paths:
        print(f"\n✅ 找到 {len(found_paths)} 个有效的文件路径")
        for path in found_paths:
            print(f"   - {path}")
    else:
        print(f"\n❌ 在标准位置没有找到 {test_file} 文件")

        # 提示用户手动指定路径
        print("\n💡 建议解决方案:")
        print("   1. 在ComfyUI节点的 'viewer_path' 参数中指定完整路径")
        print("   2. 例如: M:\\ComfyUI_windows_portable\\ve2.html")
        print("   3. 或者将文件放到以下任一位置:")
        for path in possible_paths:
            print(f"      - {path}")

    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_plugin()
