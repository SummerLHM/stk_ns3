"""
@Author   : wwq
@Date     ：2025/12/5
@Time     ：14:37
@Function :
            统一配置管理中心
            所有仿真参数在此定义，其他模块统一导入
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Any


@dataclass
class STKConfig:
    """STK 星座仿真配置"""
    # 场景
    scenario_name: str = "StarLink_sc"
    constellation_name: str = "StarLink_con"

    # 星座轨道参数
    total_planes: int = 6
    sats_per_plane: int = 11
    inclination_deg: float = 90.0
    altitude_km: float = 780.0
    earth_radius_km: float = 6371.0
    phasing_factor: int = 1

    # 通信参数
    freq_ghz: float = 20.0
    eirp_dbw: float = 28.6
    g_over_t_dbk: float = 21.0
    data_rate_mbps: float = 50.0

    # 仿真时间
    start_time: str = "22 Nov 2025 04:00:00.000"
    stop_time: str = "22 Nov 2025 05:00:00.000"
    step_sec: float = 300.0

    # 链路计算常量
    light_speed_km_s: float = 299792.458
    packet_size_bits: int = 1024 * 8
    required_ebno_db: float = 10.6  # QPSK @ BER=1e-6

    @property
    def total_sats(self) -> int:
        return self.total_planes * self.sats_per_plane

    @property
    def semi_major_axis_km(self) -> float:
        return self.altitude_km + self.earth_radius_km


@dataclass
class TimeSliceConfig:
    """时间片处理配置"""
    slice_duration_sec: float = 300.0
    polar_threshold_km: float = 2000.0  # 极地断链距离阈值


@dataclass
class TrafficConfig:
    """流量需求配置"""
    num_demands: int = 20
    demand_type: str = "mixed"  # random/intra_orbit/inter_orbit/mixed
    data_rate_min_mbps: float = 20.0
    data_rate_max_mbps: float = 50.0
    start_time_sec: float = 1.0
    duration_sec: float = 8.0
    random_seed: int = 42


@dataclass
class NS3Config:
    """NS3 仿真配置"""
    # 仿真参数
    sim_time_sec: float = 10.0
    packet_size_bytes: int = 1024
    queue_size_packets: int = 500

    # OnOff 应用参数
    on_time_mean: float = 1.0
    off_time_mean: float = 0.5

    # 监控参数
    monitor_interval_sec: float = 0.1
    start_port: int = 9000

    # NS3 路径 (Linux)
    ns3_version: str = "3.45"
    ns3_root: str = "/home/wwq/repos_ns3/ns-3-allinone/ns-3.45"
    script_name: str = "starlink-sim"

    @property
    def project_dir(self) -> str:
        return f"{self.ns3_root}/scratch/starlink"


@dataclass
class PathConfig:
    """路径配置"""
    # Windows 端
    windows_project_dir: str = r"D:\PycharmProjects\satelliteProject\ns3_and_STK_demo"

    # 共享文件夹
    shared_folder_name: str = "sat_sim"
    shared_folder_linux: str = "/mnt/hgfs/sat_sim"

    # 子目录
    data_dir: str = "data"
    ns3_input_dir: str = "ns3_input"
    ns3_output_dir: str = "ns3_results"
    log_dir: str = "logs"

    # 文件名
    link_status_file: str = "link_status.csv"
    sat_positions_file: str = "sat_positions.csv"
    isl_pairs_file: str = "isl_design_pairs.csv"
    traffic_demands_file: str = "traffic_demands.csv"
    node_mapping_file: str = "node_mapping.csv"
    flow_results_file: str = "flow_results.csv"

    @property
    def shared_folder_windows(self) -> str:
        return self.windows_project_dir

    def get_stk_output_path(self, filename: str) -> str:
        return os.path.join(self.data_dir, filename)

    def get_ns3_input_path(self, filename: str) -> str:
        return os.path.join(self.ns3_input_dir, filename)

    def get_ns3_output_path(self, filename: str) -> str:
        return os.path.join(self.ns3_output_dir, filename)


@dataclass
class SimulationConfig:
    """主配置类 - 聚合所有配置"""
    stk: STKConfig = field(default_factory=STKConfig)
    time_slice: TimeSliceConfig = field(default_factory=TimeSliceConfig)
    traffic: TrafficConfig = field(default_factory=TrafficConfig)
    ns3: NS3Config = field(default_factory=NS3Config)
    paths: PathConfig = field(default_factory=PathConfig)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stk": asdict(self.stk),
            "time_slice": asdict(self.time_slice),
            "traffic": asdict(self.traffic),
            "ns3": asdict(self.ns3),
            "paths": asdict(self.paths)
        }

    def save_json(self, filepath: str = "simulation_config.json"):
        """保存为 JSON 文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"✅ 配置已保存: {filepath}")

    @classmethod
    def load_json(cls, filepath: str = "simulation_config.json") -> "SimulationConfig":
        """从 JSON 文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        config = cls()
        if "stk" in data:
            config.stk = STKConfig(**data["stk"])
        if "time_slice" in data:
            config.time_slice = TimeSliceConfig(**data["time_slice"])
        if "traffic" in data:
            config.traffic = TrafficConfig(**data["traffic"])
        if "ns3" in data:
            config.ns3 = NS3Config(**data["ns3"])
        if "paths" in data:
            config.paths = PathConfig(**data["paths"])

        return config

    def generate_shell_config(self, filepath: str = None) -> str:
        """生成 Shell 配置文件内容"""
        if filepath is None:
            filepath = os.path.join(self.paths.ns3_input_dir, "generated_config.sh")

        content = f'''#!/bin/bash
# 自动生成的配置文件 - 请勿手动修改
# 由 config.py 生成

#=============================================================================
# 路径配置
#=============================================================================

NS3_ROOT="{self.ns3.ns3_root}"
PROJECT_DIR="$NS3_ROOT/scratch/starlink"
DATA_DIR="$PROJECT_DIR/data"
INPUT_DIR="$DATA_DIR/input"
OUTPUT_DIR="$DATA_DIR/output"
LOG_DIR="$PROJECT_DIR/logs"

#=============================================================================
# 共享文件夹配置
#=============================================================================

SHARED_PATH="{self.paths.shared_folder_linux}"
SHARED_INPUT_DIR="$SHARED_PATH/{self.paths.ns3_input_dir}"
SHARED_OUTPUT_DIR="$SHARED_PATH/{self.paths.ns3_output_dir}"

#=============================================================================
# 仿真参数
#=============================================================================

SIM_TIME={self.ns3.sim_time_sec}
PACKET_SIZE={self.ns3.packet_size_bytes}
QUEUE_SIZE={self.ns3.queue_size_packets}
MONITOR_INTERVAL={self.ns3.monitor_interval_sec}

#=============================================================================
# 流量参数
#=============================================================================

NUM_DEMANDS={self.traffic.num_demands}
DEMAND_TYPE="{self.traffic.demand_type}"

#=============================================================================
# 时间片参数
#=============================================================================

SLICE_DURATION={self.time_slice.slice_duration_sec}

#=============================================================================
# 文件名
#=============================================================================

LINK_PARAMS_FILE="link_params.csv"
TRAFFIC_DEMANDS_FILE="{self.paths.traffic_demands_file}"
OUTPUT_FILE="{self.paths.flow_results_file}"

#=============================================================================
# 其他
#=============================================================================

VERBOSE="false"
'''

        # 保存文件
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)

        print(f"✅ Shell 配置已生成: {filepath}")
        return content

    def print_summary(self):
        """打印配置摘要"""
        print("\n" + "=" * 60)
        print("📋 仿真配置摘要")
        print("=" * 60)

        print("\n🛰️  STK 星座配置:")
        print(f"   轨道面数: {self.stk.total_planes}")
        print(f"   每面卫星: {self.stk.sats_per_plane}")
        print(f"   总卫星数: {self.stk.total_sats}")
        print(f"   轨道高度: {self.stk.altitude_km} km")
        print(f"   轨道倾角: {self.stk.inclination_deg}°")
        print(f"   数据速率: {self.stk.data_rate_mbps} Mbps")
        print(f"   仿真时长: {self.stk.start_time} ~ {self.stk.stop_time}")
        print(f"   采样步长: {self.stk.step_sec} s")

        print("\n⏱️  时间片配置:")
        print(f"   切片时长: {self.time_slice.slice_duration_sec} s")
        print(f"   极地阈值: {self.time_slice.polar_threshold_km} km")

        print("\n📊 流量配置:")
        print(f"   需求数量: {self.traffic.num_demands}")
        print(f"   流量类型: {self.traffic.demand_type}")
        print(f"   速率范围: {self.traffic.data_rate_min_mbps}-{self.traffic.data_rate_max_mbps} Mbps")
        print(f"   开始时间: {self.traffic.start_time_sec} s")
        print(f"   持续时间: {self.traffic.duration_sec} s")

        print("\n🖥️  NS3 配置:")
        print(f"   仿真时间: {self.ns3.sim_time_sec} s")
        print(f"   包大小:   {self.ns3.packet_size_bytes} bytes")
        print(f"   队列大小: {self.ns3.queue_size_packets} packets")
        print(f"   NS3 路径: {self.ns3.ns3_root}")

        print("\n📁 路径配置:")
        print(f"   Windows:  {self.paths.windows_project_dir}")
        print(f"   共享目录: {self.paths.shared_folder_linux}")
        print(f"   输入目录: {self.paths.ns3_input_dir}")
        print(f"   输出目录: {self.paths.ns3_output_dir}")

        print("=" * 60)


# ==================== 全局默认配置实例 ====================

# 默认配置
DEFAULT_CONFIG = SimulationConfig()


def get_config() -> SimulationConfig:
    """获取配置实例"""
    config_file = "simulation_config.json"
    if os.path.exists(config_file):
        return SimulationConfig.load_json(config_file)
    return DEFAULT_CONFIG


# ==================== 命令行工具 ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="配置管理工具")
    parser.add_argument("--show", action="store_true", help="显示当前配置")
    parser.add_argument("--save", action="store_true", help="保存默认配置到 JSON")
    parser.add_argument("--generate-shell", action="store_true", help="生成 Shell 配置")
    parser.add_argument("--generate-cpp", action="store_true", help="生成 C++ 头文件")
    parser.add_argument("--generate-all", action="store_true", help="生成所有配置文件")

    args = parser.parse_args()

    config = get_config()

    if args.show:
        config.print_summary()

    if args.save:
        config.save_json()

    if args.generate_shell:
        config.generate_shell_config("ns3_input/generated_config.sh")

    if args.generate_cpp:
        config.generate_ns3_header("ns3_input/sim_config.h")

    if args.generate_all:
        config.save_json()
        config.generate_shell_config("ns3_input/generated_config.sh")
        config.generate_ns3_header("ns3_input/sim_config.h")
        config.print_summary()

    if not any([args.show, args.save, args.generate_shell, args.generate_cpp, args.generate_all]):
        config.print_summary()
