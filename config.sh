#!/bin/bash
# config.sh - 配置文件

#=============================================================================
# 路径配置
#=============================================================================

NS3_ROOT="/home/wwq/repos_ns3/ns-3-allinone/ns-3.45"
PROJECT_DIR="$NS3_ROOT/scratch/starlink"

DATA_DIR="$PROJECT_DIR/data"
INPUT_DIR="$DATA_DIR/input"
OUTPUT_DIR="$DATA_DIR/output"
LOG_DIR="$PROJECT_DIR/logs"

#=============================================================================
# VMware 共享文件夹配置
#=============================================================================

SHARED_PATH="/mnt/hgfs/sat_sim"
SHARED_INPUT_DIR="$SHARED_PATH/ns3_input"
SHARED_OUTPUT_DIR="$SHARED_PATH/ns3_results"

#=============================================================================
# 仿真参数
#=============================================================================

SIM_TIME=10

#=============================================================================
# 文件名配置
#=============================================================================

LINK_PARAMS_FILE="link_params.csv"
OUTPUT_FILE="flow_results.csv"
BUILD_LOG="build.log"
RUN_LOG="run.log"
