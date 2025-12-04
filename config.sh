#!/bin/bash
# /repos_ns3/ns-3-allinone/ns-3.45/scratch/starlink/config.sh
# 配置文件

#=============================================================================
# 路径配置
#=============================================================================

# NS3根目录
NS3_ROOT="/home/wwq/repos_ns3/ns-3-allinone/ns-3.45"

# 项目目录
PROJECT_DIR="$NS3_ROOT/scratch/starlink"

# 本地数据目录
DATA_DIR="$PROJECT_DIR/data"
INPUT_DIR="$DATA_DIR/input"
OUTPUT_DIR="$DATA_DIR/output"
LOG_DIR="$PROJECT_DIR/logs"

#=============================================================================
# VMware 共享文件夹配置
#=============================================================================

# 共享文件夹路径
SHARED_PATH="/mnt/hgfs/sat_sim"

# 共享文件夹中的子目录
SHARED_INPUT_DIR="$SHARED_PATH/ns3_input"
SHARED_OUTPUT_DIR="$SHARED_PATH/ns3_results"

#=============================================================================
# 仿真参数
#=============================================================================

# 仿真时间(秒)
SIM_TIME=10

# 数据包大小(字节)
PACKET_SIZE=1024

# 应用层数据发送速率
DATA_RATE="5Mbps"

# 流数量
NUM_FLOWS=5

# 是否详细输出
VERBOSE="false"

#=============================================================================
# 文件名配置
#=============================================================================

# 链路参数文件名
LINK_PARAMS_FILE="link_params.csv"

# 输出结果文件名
OUTPUT_FILE="flow_results.csv"

# 日志文件名
BUILD_LOG="build.log"
RUN_LOG="run.log"
