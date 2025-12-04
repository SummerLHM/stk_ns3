#!/bin/bash
# /home/wwq/repos_ns3/ns-3-allinone/ns-3.45/scratch/starlink/utils.sh
# 工具函数库

#=============================================================================
# 颜色定义
#=============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

#=============================================================================
# 日志函数
#=============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

log_debug() {
    if [ "$VERBOSE" = "true" ]; then
        echo -e "${PURPLE}[DEBUG]${NC} $1"
    fi
}

#=============================================================================
# 目录和文件函数
#=============================================================================

check_file() {
    local file="$1"
    if [ ! -f "$file" ]; then
        log_error "文件不存在: $file"
        return 1
    fi
    return 0
}

ensure_dir() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        log_debug "创建目录: $dir"
    fi
}

#=============================================================================
# VMware 共享文件夹函数
#=============================================================================

mount_shared() {
    local mount_point="/mnt/hgfs"
    
    # 检查是否已挂载
    if mountpoint -q "$mount_point" 2>/dev/null; then
        log_debug "共享文件夹已挂载: $mount_point"
        return 0
    fi
    
    log_info "挂载VMware共享文件夹..."
    
    if [ ! -d "$mount_point" ]; then
        sudo mkdir -p "$mount_point"
    fi
    
    if sudo vmhgfs-fuse .host:/ "$mount_point" -o allow_other 2>/dev/null; then
        log_info "挂载成功: $mount_point"
        return 0
    else
        log_warn "挂载失败，可能已挂载或未配置共享文件夹"
        return 1
    fi
}

check_shared_available() {
    local shared_path="$1"
    [ -n "$shared_path" ] && [ -d "$shared_path" ]
}

sync_input_from_shared() {
    local shared_input="$1"
    local local_input="$2"
    
    if [ ! -d "$shared_input" ]; then
        log_warn "共享输入目录不存在: $shared_input"
        return 1
    fi
    
    log_info "从共享文件夹同步输入数据..."
    
    local count=0
    
    for file in "$shared_input"/*.csv "$shared_input"/*.json; do
        if [ -f "$file" ]; then
            cp "$file" "$local_input/"
            count=$((count + 1))
        fi
    done
    
    if [ $count -gt 0 ]; then
        log_info "同步了 $count 个文件"
    else
        log_warn "没有找到要同步的文件"
    fi
    
    return 0
}

#=============================================================================
# 结果显示函数
#=============================================================================

show_csv_preview() {
    local file="$1"
    local lines="${2:-10}"
    
    if [ ! -f "$file" ]; then
        log_error "文件不存在: $file"
        return 1
    fi
    
    echo ""
    echo "📊 结果预览: $(basename "$file")"
    echo "==========================================="
    
    if command -v column >/dev/null 2>&1; then
        head -n "$lines" "$file" | column -t -s',' 2>/dev/null || head -n "$lines" "$file"
    else
        head -n "$lines" "$file"
    fi
    
    echo "==========================================="
    
    local total=$(($(wc -l < "$file") - 1))
    echo "共 $total 条数据记录"
}

show_summary() {
    local file="$1"
    
    if [ ! -f "$file" ]; then
        return 1
    fi
    
    echo ""
    echo "📈 统计摘要:"
    
    awk -F',' '
    NR > 1 && NF >= 10 {
        if ($7 ~ /^[0-9.eE+-]+$/) {
            tp += $7
            dl += $8
            pl += $10
            n++
        }
    }
    END {
        if (n > 0) {
            printf "  有效流数量: %d\n", n
            printf "  平均吞吐量: %.4f Mbps\n", tp/n
            printf "  平均时延:   %.4f ms\n", dl/n
            printf "  平均丢包率: %.6f %%\n", pl/n*100
        } else {
            print "  无有效数据"
        }
    }' "$file"
}
