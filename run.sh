#!/bin/bash
# run.sh - NS-3 仿真运行脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 加载配置
source "$SCRIPT_DIR/config.sh"
source "$SCRIPT_DIR/utils.sh"

#=============================================================================
# 参数解析
#=============================================================================

NO_BUILD=false
NO_SYNC=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--input)   LINK_PARAMS_FILE="$2"; shift 2 ;;
        -o|--output)  OUTPUT_FILE="$2"; shift 2 ;;
        --no-build)   NO_BUILD=true; shift ;;
        --no-sync)    NO_SYNC=true; shift ;;
        *) shift ;;
    esac
done

#=============================================================================
# 主程序
#=============================================================================

echo ""
echo "==========================================="
echo "  🛰️  Starlink NS3 网络仿真"
echo "==========================================="
echo ""

#-----------------------------------------------------------------------------
# Step 1: 准备目录
#-----------------------------------------------------------------------------

log_step "1/6 准备环境"

ensure_dir "$INPUT_DIR"
ensure_dir "$OUTPUT_DIR"
ensure_dir "$LOG_DIR"

log_info "NS3路径:  $NS3_ROOT"
log_info "项目路径: $PROJECT_DIR"

#-----------------------------------------------------------------------------
# Step 2: 同步共享文件夹
#-----------------------------------------------------------------------------

if [ "$NO_SYNC" = false ] && [ -n "$SHARED_PATH" ]; then
    log_step "2/6 同步共享文件夹"
    
    mount_shared
    
    if check_shared_available "$SHARED_PATH"; then
        log_info "共享文件夹: $SHARED_PATH"
        
        if [ -d "$SHARED_INPUT_DIR" ]; then
            sync_input_from_shared "$SHARED_INPUT_DIR" "$INPUT_DIR"
        fi
    else
        log_warn "共享文件夹不可用"
    fi
else
    log_step "2/6 跳过共享文件夹同步"
fi

#-----------------------------------------------------------------------------
# Step 3: 检查输入文件
#-----------------------------------------------------------------------------

log_step "3/6 检查输入文件"

INPUT_FILE="$INPUT_DIR/$LINK_PARAMS_FILE"
DEMANDS_PATH="$INPUT_DIR/traffic_demands.csv"

if [ ! -f "$INPUT_FILE" ]; then
    log_error "链路参数文件不存在: $INPUT_FILE"
    exit 1
fi

log_info "链路文件: $INPUT_FILE"
LINE_COUNT=$(($(wc -l < "$INPUT_FILE") - 1))
log_info "链路数量: $LINE_COUNT"

if [ -f "$DEMANDS_PATH" ]; then
    DEMAND_COUNT=$(($(wc -l < "$DEMANDS_PATH") - 1))
    log_info "流量需求文件: $DEMANDS_PATH"
    log_info "需求数量: $DEMAND_COUNT"
else
    log_error "流量需求文件不存在: $DEMANDS_PATH"
    exit 1
fi

#-----------------------------------------------------------------------------
# Step 4: 编译NS3
#-----------------------------------------------------------------------------

if [ "$NO_BUILD" = false ]; then
    log_step "4/6 编译NS3脚本"
    
    cd "$NS3_ROOT"
    
    if ./ns3 build scratch/starlink/starlink-sim 2>&1 | tee "$LOG_DIR/$BUILD_LOG"; then
        log_info "编译成功"
    else
        log_error "编译失败"
        exit 1
    fi
else
    log_step "4/6 跳过编译 (--no-build)"
fi

#-----------------------------------------------------------------------------
# Step 5: 运行仿真
#-----------------------------------------------------------------------------

log_step "5/6 运行仿真"

cd "$NS3_ROOT"

OUTPUT_PATH="$OUTPUT_DIR/$OUTPUT_FILE"

echo ""
echo "┌─────────────────────────────────────────┐"
echo "│ 仿真参数                                │"
echo "├─────────────────────────────────────────┤"
printf "│ %-15s %22s │\n" "链路数量:" "$LINE_COUNT"
printf "│ %-15s %22s │\n" "需求数量:" "$DEMAND_COUNT"
printf "│ %-15s %22s │\n" "仿真时间:" "$SIM_TIME 秒"
echo "└─────────────────────────────────────────┘"
echo ""

# 构建运行参数
RUN_ARGS="--linkParams=$INPUT_FILE"
RUN_ARGS="$RUN_ARGS --demands=$DEMANDS_PATH"
RUN_ARGS="$RUN_ARGS --output=$OUTPUT_PATH"
RUN_ARGS="$RUN_ARGS --simTime=$SIM_TIME"

log_info "启动NS3仿真..."

START_TIME=$(date +%s)

if ./ns3 run "scratch/starlink/starlink-sim $RUN_ARGS" 2>&1 | tee "$LOG_DIR/$RUN_LOG"; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    log_info "仿真完成, 耗时: ${DURATION} 秒"
else
    log_error "仿真失败"
    exit 1
fi

#-----------------------------------------------------------------------------
# Step 6: 处理结果
#-----------------------------------------------------------------------------

log_step "6/6 处理结果"

if [ -f "$OUTPUT_PATH" ]; then
    log_info "结果文件: $OUTPUT_PATH"
    
    show_csv_preview "$OUTPUT_PATH" 10
    show_summary "$OUTPUT_PATH"
    
    if [ "$NO_SYNC" = false ] && check_shared_available "$SHARED_PATH"; then
        ensure_dir "$SHARED_OUTPUT_DIR"
        cp "$OUTPUT_PATH" "$SHARED_OUTPUT_DIR/"
        log_info "已同步: $SHARED_OUTPUT_DIR/$OUTPUT_FILE"
    fi
else
    log_error "结果文件未生成"
    exit 1
fi

#-----------------------------------------------------------------------------
# 完成
#-----------------------------------------------------------------------------

echo ""
echo "==========================================="
echo "  ✅ 仿真完成!"
echo "==========================================="
echo ""
echo "📁 输出文件: $OUTPUT_PATH"
echo ""
