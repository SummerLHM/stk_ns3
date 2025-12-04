#!/bin/bash
# /home/wwq/repos_ns3/ns-3-allinone/ns-3.45/scratch/starlink/utils.sh
# 工具函数库

#=============================================================================
# 颜色定义
#=============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

check_dir() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        log_error "目录不存在: $dir"
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
# 共享文件夹函数
#=============================================================================

mount_vmware_shared() {
    local mount_point="/mnt/hgfs"
    
    # 检查是否已挂载
    if mountpoint -q "$mount_point" 2>/dev/null; then
        log_debug "共享文件夹已挂载: $mount_point"
        return 0
    fi
    
    log_info "挂载VMware共享文件夹..."
    
    # 创建挂载点
    if [ ! -d "$mount_point" ]; then
        sudo mkdir -p "$mount_point"
    fi
    
    # 尝试挂载
    if sudo vmhgfs-fuse .host:/ "$mount_point" -o allow_other 2>/dev/null; then
        log_info "挂载成功: $mount_point"
        return 0
    else
        log_warn "挂载失败，可能已挂载或未配置共享文件夹"
        return 1
    fi
}

mount_shared() {
    local type="$1"
    
    case "$type" in
        vmware)
            mount_vmware_shared
            ;;
        virtualbox)
            log_info "VirtualBox共享文件夹请确保已在fstab中配置或手动挂载"
            ;;
        *)
            log_debug "不使用共享文件夹"
            ;;
    esac
}

check_shared_available() {
    local shared_path="$1"
    
    if [ -z "$shared_path" ]; then
        return 1
    fi
    
    if [ -d "$shared_path" ]; then
        return 0
    else
        return 1
    fi
}

sync_input_from_shared() {
    local shared_input="$1"
    local local_input="$2"
    
    if [ ! -d "$shared_input" ]; then
        log_warn "共享输入目录不存在: $shared_input"
        return 1
    fi
    
    log_info "从共享文件夹同步输入数据..."
    log_info "  源: $shared_input"
    log_info "  目标: $local_input"
    
    local count=0
    
    # 复制CSV文件
    for file in "$shared_input"/*.csv; do
        if [ -f "$file" ]; then
            cp "$file" "$local_input/"
            count=$((count + 1))
        fi
    done
    
    # 复制JSON文件
    for file in "$shared_input"/*.json; do
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

sync_output_to_shared() {
    local local_output="$1"
    local shared_output="$2"
    
    if [ -z "$shared_output" ]; then
        log_debug "未配置共享输出目录"
        return 0
    fi
    
    # 创建共享输出目录
    if [ ! -d "$shared_output" ]; then
        mkdir -p "$shared_output" 2>/dev/null
        if [ $? -ne 0 ]; then
            log_warn "无法创建共享输出目录: $shared_output"
            return 1
        fi
    fi
    
    log_info "同步输出到共享文件夹..."
    log_info "  源: $local_output"
    log_info "  目标: $shared_output"
    
    local count=0
    
    # 复制CSV文件
    for file in "$local_output"/*.csv; do
        if [ -f "$file" ]; then
            cp "$file" "$shared_output/"
            count=$((count + 1))
        fi
    done
    
    # 复制JSON文件
    for file in "$local_output"/*.json; do
        if [ -f "$file" ]; then
            cp "$file" "$shared_output/"
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
    
    # 尝试使用column格式化
    if command -v column >/dev/null 2>&1; then
        head -n "$lines" "$file" | column -t -s',' 2>/dev/null || head -n "$lines" "$file"
    else
        head -n "$lines" "$file"
    fi
    
    echo "==========================================="
    
    # 统计数据行数
    local total
    total=$(wc -l < "$file")
    total=$((total - 1))
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

#=============================================================================
# 时间函数
#=============================================================================

get_timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

calc_duration() {
    local start="$1"
    local end="$2"
    echo $((end - start))
}
