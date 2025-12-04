"""
@Author   : wwq
@Date     ：2025/11/26
@Time     ：14:12
@Function :
            时间片管理器
            - 将 STK 数据按时间片划分
            - 直接读取 Latency, Bandwidth, PLR, BER
            - 生成动态拓扑序列
"""

import os
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


@dataclass
class TimeSlice:
    """时间片"""
    slice_id: int
    start_time: str
    end_time: str
    duration_sec: float
    num_links: int
    num_nodes: int


@dataclass
class TrafficDemand:
    """流量需求"""
    demand_id: int
    src_node: str
    dst_node: str
    src_id: int
    dst_id: int
    data_rate_mbps: float
    start_time_sec: float
    duration_sec: float


class TimeSliceManager:
    """时间片管理器"""

    def __init__(self, slice_duration_sec: float = 60.0):
        self.slice_duration = slice_duration_sec
        self.time_slices: List[TimeSlice] = []
        self.topologies: Dict[int, Dict] = {}  # slice_id -> topology
        self.traffic_demands: List[TrafficDemand] = []

        self.output_dir = "ns3_input"
        os.makedirs(self.output_dir, exist_ok=True)

    def load_stk_data(self, link_file: str, pos_file: str = None) -> bool:
        """加载 STK 数据"""
        print(f"\n📂 加载 STK 数据...")

        if not os.path.exists(link_file):
            print(f"❌ 文件不存在: {link_file}")
            return False

        try:
            self.link_df = pd.read_csv(link_file, encoding='utf-8-sig')
            # 标准化列名
            self.link_df.columns = [col.split('（')[0].strip() for col in self.link_df.columns]
            print(f"✅ 读取链路数据: {len(self.link_df)} 条")
            print(f"   🔍 列名: {list(self.link_df.columns)}")

            # 获取时间范围
            if 'TimeString' in self.link_df.columns:
                # 尝试解析多种时间格式
                try:
                    self.link_df['TimeString'] = pd.to_datetime(self.link_df['TimeString'],
                                                                format="%d %b %Y %H:%M:%S.%f")
                except:
                    self.link_df['TimeString'] = pd.to_datetime(self.link_df['TimeString'])

                self.start_time = self.link_df['TimeString'].min()
                self.end_time = self.link_df['TimeString'].max()
                print(f"   时间范围: {self.start_time} 至 {self.end_time}")

            return True
        except Exception as e:
            print(f"❌ 读取失败: {e}")
            return False

    def create_time_slices(self, total_duration_sec: float = None) -> List[TimeSlice]:
        """创建时间片"""
        print(f"\n⏱️ 创建时间片 (每片 {self.slice_duration} 秒)...")

        if total_duration_sec is None:
            if hasattr(self, 'start_time') and hasattr(self, 'end_time'):
                total_duration_sec = (self.end_time - self.start_time).total_seconds()
            else:
                total_duration_sec = 3600.0  # 默认1小时

        num_slices = int(np.ceil(total_duration_sec / self.slice_duration))

        self.time_slices = []
        for i in range(num_slices):
            start = i * self.slice_duration
            end = min((i + 1) * self.slice_duration, total_duration_sec)

            slice_info = TimeSlice(
                slice_id=i,
                start_time=f"{start:.1f}s",
                end_time=f"{end:.1f}s",
                duration_sec=end - start,
                num_links=0,
                num_nodes=0
            )
            self.time_slices.append(slice_info)

        print(f"✅ 创建 {len(self.time_slices)} 个时间片")
        return self.time_slices

    def build_topology_for_slice(self, slice_id: int) -> Dict:
        """
        为指定时间片构建拓扑 (适配新版 CSV 字段，包含 BER)
        """
        if not hasattr(self, 'start_time') or self.start_time is None:
            print("❌ 错误：数据中无时间列")
            return {}

        # 计算目标时间点
        target_time = self.start_time + timedelta(seconds=slice_id * self.slice_duration)

        timestamp_str = target_time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"   构建切片 {slice_id} 拓扑 (目标时刻: {timestamp_str})...")

        # 设置一个小的容差窗口 (例如 +/- 0.5秒) 来匹配时间点
        time_window_start = target_time - timedelta(seconds=0.5)
        time_window_end = target_time + timedelta(seconds=0.5)

        mask = (self.link_df['TimeString'] >= time_window_start) & \
               (self.link_df['TimeString'] <= time_window_end)

        slice_df = self.link_df.loc[mask]

        if slice_df.empty:
            # 尝试寻找最近的时间点（防止容差匹配失败）
            try:
                nearest_idx = (self.link_df['TimeString'] - target_time).abs().idxmin()
                nearest_time = self.link_df.loc[nearest_idx, 'TimeString']
                # 如果最近的时间点偏差在 Step 范围内，则使用它
                if abs((nearest_time - target_time).total_seconds()) <= self.slice_duration:
                    slice_df = self.link_df[self.link_df['TimeString'] == nearest_time]
                    timestamp_str = nearest_time.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass

        # 收集节点和边
        nodes = set()
        edges = []

        for _, row in slice_df.iterrows():
            src = str(row.get('Src', ''))
            dst = str(row.get('Dst', ''))

            if not src or not dst:
                continue

            nodes.add(src)
            nodes.add(dst)

            # 1. 距离 (km)
            distance = float(row.get('Range_km', 1000.0))

            # 2. 时延 (ms) - 直接读取
            delay_ms = float(row.get('Latency_ms', distance / 299.792))

            # 3. 带宽 (Mbps) -> Bps
            bw_mbps = float(row.get('Bandwidth_Mbps', 0.0))
            data_rate_bps = int(bw_mbps * 1e6)

            # 4. 丢包率
            plr = float(row.get('Packet_Loss_Rate', 0.0))

            # 5. BER（新增）
            ber = float(row.get('BER', 0.0))

            # 模拟 SCI 论文中的极地断链 (Polar Link Switch-off)
            def get_plane_idx(sat_name):
                try:
                    return int(sat_name.split('_')[1])
                except:
                    return -1

            p1 = get_plane_idx(src)
            p2 = get_plane_idx(dst)

            # 判断是否是轨道间链路 (Inter-plane)
            if p1 != p2 and p1 != -1 and p2 != -1:
                POLAR_THRESHOLD_KM = 2000.0
                if distance < POLAR_THRESHOLD_KM:
                    # 认为在极地，强制断开
                    continue

            edges.append({
                "src_name": src,
                "dst_name": dst,
                "delay_ms": delay_ms,
                "data_rate_bps": data_rate_bps,
                "distance_km": distance,
                "packet_loss_rate": plr,
                "ber": ber  # 新增 BER
            })

        # 构建节点映射
        node_list = sorted(list(nodes))
        node_id_map = {name: idx for idx, name in enumerate(node_list)}

        # 更新边的 ID
        for edge in edges:
            edge["src_id"] = node_id_map[edge["src_name"]]
            edge["dst_id"] = node_id_map[edge["dst_name"]]

        topology = {
            "slice_id": slice_id,
            "timestamp": timestamp_str,
            "num_nodes": len(node_list),
            "num_edges": len(edges),
            "nodes": [{"id": node_id_map[name], "name": name} for name in node_list],
            "node_id_map": node_id_map,
            "edges": edges
        }

        if slice_id < len(self.time_slices):
            self.time_slices[slice_id].num_links = len(edges)
            self.time_slices[slice_id].num_nodes = len(node_list)

        self.topologies[slice_id] = topology
        return topology

    def generate_traffic_demands(self, num_demands: int = 10,
                                 demand_type: str = "random") -> List[TrafficDemand]:
        """生成流量需求"""
        print(f"\n📊 生成流量需求 (类型: {demand_type})...")

        if not self.topologies:
            print("❌ 请先构建拓扑")
            return []

        topo = self.topologies[0]
        nodes = topo["nodes"]

        if len(nodes) < 2:
            print("❌ 节点数量不足")
            return []

        self.traffic_demands = []

        # 简单的辅助函数：获取轨道号
        def get_orbit(name):
            try:
                return int(name.split('_')[1])
            except:
                return -1

        orbit_nodes = {}
        for node in nodes:
            orbit = get_orbit(node["name"])
            if orbit not in orbit_nodes:
                orbit_nodes[orbit] = []
            orbit_nodes[orbit].append(node)

        np.random.seed(42)

        for i in range(num_demands):
            src, dst = None, None

            # 简化的选择逻辑
            if demand_type == "random" or len(orbit_nodes) < 2:
                src, dst = np.random.choice(nodes, 2, replace=False)
            else:
                # 尝试跨轨道
                orbits = list(orbit_nodes.keys())
                o1, o2 = np.random.choice(orbits, 2, replace=False)
                src = np.random.choice(orbit_nodes[o1])
                dst = np.random.choice(orbit_nodes[o2])

            demand = TrafficDemand(
                demand_id=i,
                src_node=src["name"],
                dst_node=dst["name"],
                src_id=src["id"],
                dst_id=dst["id"],
                data_rate_mbps=np.random.uniform(20, 50),
                start_time_sec=1.0,
                duration_sec=8.0
            )
            self.traffic_demands.append(demand)

        print(f"✅ 生成 {len(self.traffic_demands)} 个流量需求")
        return self.traffic_demands

    def export_for_ns3(self):
        """导出 NS3 配置文件"""
        print(f"\n📤 导出 NS3 配置文件...")

        # 1. 时间片信息
        slices_file = os.path.join(self.output_dir, "time_slices.json")
        with open(slices_file, 'w') as f:
            json.dump([asdict(s) for s in self.time_slices], f, indent=2)
        print(f"   ✅ 时间片信息: {slices_file}")

        # 2. 每个时间片的拓扑
        for slice_id, topo in self.topologies.items():
            # CSV 格式 (Link Params)
            link_file = os.path.join(self.output_dir, f"link_params_slice_{slice_id}.csv")
            rows = []

            ts = topo.get("timestamp", "")

            for edge in topo["edges"]:
                rows.append({
                    "src_id": edge["src_id"],
                    "dst_id": edge["dst_id"],
                    "src_name": edge["src_name"],
                    "dst_name": edge["dst_name"],
                    "delay_ms": round(edge["delay_ms"], 4),
                    "data_rate_bps": edge["data_rate_bps"],
                    "packet_loss_rate": edge["packet_loss_rate"],
                    "ber": edge["ber"],  # 新增 BER
                    "distance_km": round(edge["distance_km"], 2),
                    "timestamp": ts
                })
            pd.DataFrame(rows).to_csv(link_file, index=False)

            # JSON 格式 (完整拓扑)
            topo_file = os.path.join(self.output_dir, f"topology_slice_{slice_id}.json")
            with open(topo_file, 'w') as f:
                json.dump(topo, f, indent=2)

        print(f"   ✅ 链路参数: {len(self.topologies)} 个切片文件 (包含 BER)")

        # 3. 流量需求
        demands_file = os.path.join(self.output_dir, "traffic_demands.csv")
        rows = [asdict(d) for d in self.traffic_demands]
        pd.DataFrame(rows).to_csv(demands_file, index=False)
        print(f"   ✅ 流量需求: {demands_file}")

        # 4. 节点映射 (使用第一个切片的映射作为全局映射)
        if self.topologies:
            topo = self.topologies[0]
            node_file = os.path.join(self.output_dir, "node_mapping.csv")
            pd.DataFrame(topo["nodes"]).to_csv(node_file, index=False)
            print(f"   ✅ 节点映射: {node_file}")

        # 5. 导出 IP 映射
        self._export_ip_mapping()

        print(f"✅ 导出完成: {self.output_dir}")

    def _export_ip_mapping(self):
        """导出 IP 映射"""
        if not self.topologies:
            return
        topo = self.topologies[0]

        ip_mapping = {}
        for i, edge in enumerate(topo["edges"]):
            src_ip = f"10.0.{i}.1"
            dst_ip = f"10.0.{i}.2"
            ip_mapping[src_ip] = edge["src_name"]
            ip_mapping[dst_ip] = edge["dst_name"]

        mapping_file = os.path.join(self.output_dir, "ip_to_satellite.json")
        with open(mapping_file, 'w') as f:
            json.dump(ip_mapping, f, indent=2)
        print(f"   ✅ IP映射: {mapping_file}")

    def print_summary(self):
        """打印汇总信息"""
        if not self.topologies:
            return

        print("\n" + "=" * 55)
        print("📊 时间片处理汇总")
        print("=" * 55)
        print(f"  时间片数量: {len(self.time_slices)}")
        print(f"  每片时长: {self.slice_duration} 秒")

        if self.topologies:
            topo = self.topologies[0]
            print(f"  节点数量: {topo['num_nodes']}")
            print(f"  边数量: {topo['num_edges']}")

            # 统计 BER
            bers = [edge["ber"] for edge in topo["edges"]]
            plrs = [edge["packet_loss_rate"] for edge in topo["edges"]]
            if bers:
                print(f"  平均BER: {np.mean(bers):.2e}")
                print(f"  平均丢包率: {np.mean(plrs):.2%}")

        print("=" * 55)


if __name__ == "__main__":
    manager = TimeSliceManager(slice_duration_sec=60.0)

    if manager.load_stk_data("data/link_status.csv"):
        manager.create_time_slices()

        # 构建所有切片的拓扑
        for i in range(len(manager.time_slices)):
            manager.build_topology_for_slice(i)

        manager.generate_traffic_demands()
        manager.export_for_ns3()
        manager.print_summary()
    else:
        print("❌ 无法加载数据，请先运行 STK 仿真。")
