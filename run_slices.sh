#!/bin/bash
# run_slices.sh - 批量切片仿真脚本

#=============================================================================
# 配置
#=============================================================================

PROJECT_DIR="/home/wwq/repos_ns3/ns-3-allinone/ns-3.45/scratch/starlink"
INPUT_DIR="$PROJECT_DIR/data/input"
OUTPUT_DIR="$PROJECT_DIR/data/output"

SHARED_ROOT="/mnt/hgfs/sat_sim"
SHARED_INPUT="$SHARED_ROOT/ns3_input"
SHARED_OUTPUT="$SHARED_ROOT/ns3_results"

#=============================================================================
# 挂载共享文件夹
#=============================================================================

if [ ! -d "$SHARED_ROOT" ]; then
    sudo vmhgfs-fuse .host:/ /mnt/hgfs -o allow_other >/dev/null 2>&1
fi

echo "=================================================="
echo "🚀 Starlink 动态仿真 (Slice Mode)"
echo "=================================================="

#=============================================================================
# 同步输入数据
#=============================================================================

echo -n "🔄 正在同步数据 (Windows -> Linux) ... "
rm -f "$INPUT_DIR"/* "$OUTPUT_DIR"/*
mkdir -p "$INPUT_DIR" "$OUTPUT_DIR"
cp "$SHARED_INPUT"/* "$INPUT_DIR/" 2>/dev/null
count=$(ls "$INPUT_DIR"/link_params_slice_*.csv 2>/dev/null | wc -l)

if [ "$count" -gt 0 ]; then
    echo "✅ 完成 (加载 $count 个切片)"
else
    echo "❌ 失败 (未找到切片文件)"
    exit 1
fi

echo "--------------------------------------------------"

#=============================================================================
# 批量运行仿真
#=============================================================================

files=$(ls -v "$INPUT_DIR"/link_params_slice_*.csv)

for file in $files; do
    filename=$(basename "$file")
    slice_id=$(echo "$filename" | grep -oP '(?<=slice_)\d+')
    
    result_file="flow_results_slice_${slice_id}.csv"
    route_file="route_paths_slice_${slice_id}.csv"
    monitor_file="link_monitor_slice_${slice_id}.csv"
    stats_file="link_stats_slice_${slice_id}.csv"
    
    echo -n "   ⏳ Slice $slice_id ... "
    
    bash "$PROJECT_DIR/run.sh" \
        --input "$filename" \
        --output "$result_file" \
        --no-build \
        --no-sync > "$PROJECT_DIR/logs/slice_${slice_id}.log" 2>&1
    
    if [ $? -eq 0 ]; then
        # 重命名输出文件
        [ -f "$OUTPUT_DIR/route_paths.csv" ] && mv "$OUTPUT_DIR/route_paths.csv" "$OUTPUT_DIR/$route_file"
        [ -f "$OUTPUT_DIR/link_monitor.csv" ] && mv "$OUTPUT_DIR/link_monitor.csv" "$OUTPUT_DIR/$monitor_file"
        [ -f "$OUTPUT_DIR/link_stats.csv" ] && mv "$OUTPUT_DIR/link_stats.csv" "$OUTPUT_DIR/$stats_file"
        
        echo "✅ 完成"
    else
        echo "❌ 失败 (查看 logs/slice_${slice_id}.log)"
    fi
done

echo "--------------------------------------------------"

#=============================================================================
# 回传结果
#=============================================================================

echo -n "📤 正在回传结果 (Linux -> Windows) ... "
mkdir -p "$SHARED_OUTPUT"

cp "$OUTPUT_DIR"/flow_results_slice_*.csv "$SHARED_OUTPUT/" 2>/dev/null
cp "$OUTPUT_DIR"/route_paths_slice_*.csv "$SHARED_OUTPUT/" 2>/dev/null
cp "$OUTPUT_DIR"/link_monitor_slice_*.csv "$SHARED_OUTPUT/" 2>/dev/null
cp "$OUTPUT_DIR"/link_stats_slice_*.csv "$SHARED_OUTPUT/" 2>/dev/null

echo "✅ 完成"
echo "=================================================="
