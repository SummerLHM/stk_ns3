#!/bin/bash
# /repos_ns3/ns-3-allinone/ns-3.45/scratch/starlink/setup.sh
# 环境配置脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "==========================================="
echo "  Starlink NS3 环境配置"
echo "==========================================="
echo ""

#=============================================================================
# 1. 验证NS3
#=============================================================================

echo "[1/5] 验证NS3环境..."

NS3_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ ! -f "$NS3_ROOT/ns3" ]; then
    echo "❌ 未检测到NS3: $NS3_ROOT"
    exit 1
fi

echo "✅ NS3路径: $NS3_ROOT"

#=============================================================================
# 2. 创建目录
#=============================================================================

echo ""
echo "[2/5] 创建目录结构..."

mkdir -p "$SCRIPT_DIR/data/input"
mkdir -p "$SCRIPT_DIR/data/output"
mkdir -p "$SCRIPT_DIR/logs"

echo "✅ 目录结构已创建"

#=============================================================================
# 3. 配置共享文件夹
#=============================================================================

echo ""
echo "[3/5] 配置共享文件夹..."

echo ""
echo "当前配置:"
echo "  共享文件夹名称: sat_sim"
echo "  Linux挂载路径:  /mnt/hgfs/sat_sim"
echo "  Windows路径:    D:\\PycharmProjects\\satelliteProject\\ns3_and_STK_demo"
echo ""

# 检查vmhgfs-fuse
if ! command -v vmhgfs-fuse &>/dev/null; then
    echo "正在安装open-vm-tools..."
    sudo apt update
    sudo apt install -y open-vm-tools open-vm-tools-desktop
fi

# 创建挂载点
if [ ! -d "/mnt/hgfs" ]; then
    sudo mkdir -p /mnt/hgfs
fi

# 尝试挂载
echo "尝试挂载共享文件夹..."
if sudo vmhgfs-fuse .host:/ /mnt/hgfs -o allow_other 2>/dev/null; then
    echo "✅ 挂载成功"
elif mountpoint -q /mnt/hgfs 2>/dev/null; then
    echo "✅ 已挂载"
else
    echo "⚠️ 挂载失败"
fi

# 检查共享文件夹
if [ -d "/mnt/hgfs/sat_sim" ]; then
    echo "✅ 共享文件夹可访问: /mnt/hgfs/sat_sim"
    ls -la /mnt/hgfs/sat_sim/ 2>/dev/null || true
else
    echo "⚠️ 共享文件夹不存在: /mnt/hgfs/sat_sim"
    echo ""
    echo "请在VMware中配置:"
    echo "  1. 虚拟机 -> 设置 -> 选项 -> 共享文件夹"
    echo "  2. 启用共享文件夹"
    echo "  3. 添加共享:"
    echo "     名称: sat_sim"
    echo "     主机路径: D:\\PycharmProjects\\satelliteProject\\ns3_and_STK_demo"
fi

#=============================================================================
# 4. 更新配置文件
#=============================================================================

echo ""
echo "[4/5] 检查配置文件..."

if [ -f "$SCRIPT_DIR/config.sh" ]; then
    echo "✅ 配置文件存在: $SCRIPT_DIR/config.sh"
else
    echo "⚠️ 配置文件不存在，请创建"
fi

#=============================================================================
# 5. 测试编译
#=============================================================================

echo ""
echo "[5/5] 测试编译..."

cd "$NS3_ROOT"

if ./ns3 build scratch/starlink/starlink-sim 2>&1 | tail -3; then
    echo ""
    echo "✅ 编译测试通过"
else
    echo ""
    echo "❌ 编译失败"
    exit 1
fi

#=============================================================================
# 完成
#=============================================================================


