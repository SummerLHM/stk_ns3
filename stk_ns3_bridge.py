"""
@Author   : wwq
@Date     ：2025/11/25
@Function : STK到NS3数据桥接模块
"""

import os
import json
import shutil
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class LinkParameters:
    """链路参数数据类"""
    src_sat: str
    dst_sat: str
    src_id: int = 0
    dst_id: int = 0
    distance_km: float = 0.0
    propagation_delay_ms: float = 0.0
    data_rate_mbps: float = 100.0
    data_rate_bps: int = 100000000
    packet_loss_rate: float = 0.0
    ber: float = 0.0  # BER 字段
    timestamp: str = ""


@dataclass
class NetworkTopology:
    """网络拓扑数据类"""
    num_nodes: int = 0
    nodes: List[Dict] = field(default_factory=list)
    node_id_map: Dict[str, int] = field(default_factory=dict)
    edges: List[Dict] = field(default_factory=list)
    timestamp: str = ""


class STKNS3Bridge:
    """STK与NS3数据桥接"""

    def __init__(self, config_file: str = "ns3_config.json"):
        self.config = self._load_config(config_file)

        self.stk_data_dir = self.config.get("directories", {}).get("stk_output", "data")
        self.ns3_input_dir = self.config.get("directories", {}).get("ns3_input", "ns3_input")
        self.ns3_output_dir = self.config.get("directories", {}).get("ns3_output", "ns3_results")

        shared_config = self.config.get("shared_folder", {})
        self.shared_windows = shared_config.get("windows_path", "")
        self.shared_linux = shared_config.get("linux_path", "/mnt/hgfs/sat_sim")
        self.linux_subdir = "input"

        ns3_config = self.config.get("ns3", {})
        self.ns3_root = ns3_config.get("root_path", "/repos_ns3/ns-3-allinone/ns-3.45")
        self.ns3_project = ns3_config.get("project_path", "/repos_ns3/ns-3-allinone/ns-3.45/scratch/starlink")

        self.link_params: List[LinkParameters] = []
        self.topology: NetworkTopology = NetworkTopology()

        os.makedirs(self.stk_data_dir, exist_ok=True)
        os.makedirs(self.ns3_input_dir, exist_ok=True)
        os.makedirs(self.ns3_output_dir, exist_ok=True)

    def _load_config(self, config_file: str) -> Dict:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def load_stk_data(self) -> bool:
        """加载STK导出数据"""
        print("\n📂 加载STK数据...")
        link_file = os.path.join(self.stk_data_dir, "link_status.csv")

        if not os.path.exists(link_file):
            print(f"❌ 链路状态文件不存在: {link_file}")
            return False

        try:
            link_df = pd.read_csv(link_file, encoding='utf-8-sig')
            link_df.columns = [col.split('（')[0].strip() for col in link_df.columns]
            print(f"✅ 读取链路数据: {len(link_df)} 条")
            print(f"   🔍 列名: {list(link_df.columns)}")
        except Exception as e:
            print(f"❌ 读取链路文件失败: {e}")
            return False

        self.link_params = []
        if not link_df.empty and 'TimeString' in link_df.columns:
            first_timestamp = link_df.iloc[0]['TimeString']
            print(f"ℹ️ 提取时间点: {first_timestamp} 的拓扑数据")
            link_df = link_df[link_df['TimeString'] == first_timestamp]

        for _, row in link_df.iterrows():
            src = str(row.get('Src', ''))
            dst = str(row.get('Dst', ''))
            t = str(row.get('TimeString', ''))
            if not src or not dst:
                continue

            distance = float(row.get('Range_km', 1000.0))
            delay_ms = float(row.get('Latency_ms', distance / 300.0))
            bw_mbps = float(row.get('Bandwidth_Mbps', 100.0))
            data_rate_bps = int(bw_mbps * 1e6)
            plr = float(row.get('Packet_Loss_Rate', 0.0))
            ber = float(row.get('BER', 0.0))  # 读取 BER

            param = LinkParameters(
                src_sat=src, dst_sat=dst, distance_km=distance,
                propagation_delay_ms=delay_ms, data_rate_mbps=bw_mbps,
                data_rate_bps=data_rate_bps, packet_loss_rate=plr,
                ber=ber,
                timestamp=t
            )
            self.link_params.append(param)

        if self.link_params:
            print(f"   🔍 第一条链路 BER: {self.link_params[0].ber}")

        print(f"✅ 提取 {len(self.link_params)} 条链路参数")
        return len(self.link_params) > 0

    def build_topology(self) -> NetworkTopology:
        """构建网络拓扑"""
        print("\n🔗 构建网络拓扑...")
        nodes = set()
        for param in self.link_params:
            nodes.add(param.src_sat)
            nodes.add(param.dst_sat)

        node_list = sorted(list(nodes))
        node_id_map = {name: idx for idx, name in enumerate(node_list)}

        for param in self.link_params:
            param.src_id = node_id_map[param.src_sat]
            param.dst_id = node_id_map[param.dst_sat]

        edges = []
        for param in self.link_params:
            edges.append({
                "src_id": param.src_id,
                "dst_id": param.dst_id,
                "src_name": param.src_sat,
                "dst_name": param.dst_sat,
                "delay_ms": param.propagation_delay_ms,
                "data_rate_bps": param.data_rate_bps,
                "data_rate_mbps": param.data_rate_mbps,
                "packet_loss_rate": param.packet_loss_rate,
                "ber": param.ber,  # 添加 BER
                "distance_km": param.distance_km
            })

        self.topology = NetworkTopology(
            num_nodes=len(node_list),
            nodes=[{"id": node_id_map[name], "name": name} for name in node_list],
            node_id_map=node_id_map,
            edges=edges,
            timestamp=self.link_params[0].timestamp if self.link_params else ""
        )
        print(f"✅ 拓扑: {self.topology.num_nodes} 节点, {len(edges)} 条边")
        return self.topology

    def export_for_ns3(self) -> Tuple[str, str, str]:
        """导出NS3配置文件"""
        print("\n📤 导出NS3配置文件...")

        # 1. 导出 topology.json
        topology_file = os.path.join(self.ns3_input_dir, "topology.json")
        with open(topology_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.topology), f, indent=2, ensure_ascii=False)
        print(f"   ✅ 拓扑文件: {topology_file}")

        # 2. 导出 link_params.csv（包含 BER）
        link_csv = os.path.join(self.ns3_input_dir, "link_params.csv")
        rows = []
        for edge in self.topology.edges:
            rows.append({
                "src_id": edge["src_id"],
                "dst_id": edge["dst_id"],
                "src_name": edge["src_name"],
                "dst_name": edge["dst_name"],
                "delay_ms": round(edge["delay_ms"], 6),
                "data_rate_bps": edge["data_rate_bps"],
                "packet_loss_rate": edge["packet_loss_rate"],
                "ber": edge["ber"],  # 导出 BER
                "distance_km": round(edge["distance_km"], 2)
            })

        df = pd.DataFrame(rows)
        df.to_csv(link_csv, index=False)
        print(f"   ✅ 链路参数: {link_csv} (包含 BER 列)")

        # 3. 导出 node_mapping.csv
        node_map_file = os.path.join(self.ns3_input_dir, "node_mapping.csv")
        node_rows = [{"id": node["id"], "name": node["name"]} for node in self.topology.nodes]
        pd.DataFrame(node_rows).to_csv(node_map_file, index=False)
        print(f"   ✅ 节点映射: {node_map_file}")

        self._export_ip_mapping()
        return topology_file, link_csv, node_map_file

    def _export_ip_mapping(self):
        """导出 IP 到卫星名称的映射"""
        ip_mapping = {}
        link_mapping = []
        for i, edge in enumerate(self.topology.edges):
            src_ip = f"10.0.{i}.1"
            dst_ip = f"10.0.{i}.2"
            src_name = edge["src_name"]
            dst_name = edge["dst_name"]
            ip_mapping[src_ip] = src_name
            ip_mapping[dst_ip] = dst_name
            link_mapping.append({
                "link_id": i, "src_ip": src_ip, "dst_ip": dst_ip,
                "src_satellite": src_name, "dst_satellite": dst_name,
                "src_node_id": edge["src_id"], "dst_node_id": edge["dst_id"]
            })

        simple_mapping_file = os.path.join(self.ns3_input_dir, "ip_to_satellite.json")
        with open(simple_mapping_file, 'w', encoding='utf-8') as f:
            json.dump(ip_mapping, f, indent=2, ensure_ascii=False)
        print(f"   ✅ IP映射: {simple_mapping_file}")

        detailed_mapping_file = os.path.join(self.ns3_input_dir, "link_ip_mapping.json")
        with open(detailed_mapping_file, 'w', encoding='utf-8') as f:
            json.dump(link_mapping, f, indent=2, ensure_ascii=False)

    def sync_to_shared_folder(self) -> bool:
        """同步数据到共享文件夹"""
        print("\n📁 同步到共享文件夹...")

        if not self.shared_windows:
            print("   ℹ️ 未配置共享文件夹路径，跳过同步")
            return False

        abs_input = os.path.abspath(self.ns3_input_dir)
        abs_shared = os.path.abspath(self.shared_windows)

        if abs_input.startswith(abs_shared):
            print("   ℹ️ ns3_input已在共享文件夹中，无需同步")
            return True

        try:
            shared_input = os.path.join(self.shared_windows, "ns3_input")
            if os.path.exists(os.path.dirname(shared_input)):
                os.makedirs(shared_input, exist_ok=True)
                for filename in os.listdir(self.ns3_input_dir):
                    src = os.path.join(self.ns3_input_dir, filename)
                    dst = os.path.join(shared_input, filename)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
                        print(f"   ✅ {filename}")
                return True
        except Exception as e:
            print(f"   ⚠️ 同步失败: {e}")
        return False

    def print_summary(self):
        """打印链路参数统计"""
        if not self.link_params:
            return

        delays = [p.propagation_delay_ms for p in self.link_params]
        rates = [p.data_rate_mbps for p in self.link_params]
        plrs = [p.packet_loss_rate for p in self.link_params]
        bers = [p.ber for p in self.link_params]

        print("\n" + "=" * 55)
        print("📊 链路参数统计")
        print("=" * 55)
        print(f"  链路数量: {len(self.link_params)}")
        print(f"  节点数量: {self.topology.num_nodes}")
        print(f"  平均时延: {np.mean(delays):.2f} ms")
        print(f"  平均带宽: {np.mean(rates):.2f} Mbps")
        print(f"  平均丢包: {np.mean(plrs):.2%}")
        print(f"  平均BER:  {np.mean(bers):.2e}")
        print("=" * 55)


if __name__ == "__main__":
    bridge = STKNS3Bridge()
    if bridge.load_stk_data():
        bridge.build_topology()
        bridge.export_for_ns3()
        bridge.sync_to_shared_folder()
        bridge.print_summary()
    else:
        print("❌ 无法加载数据，请先运行 STK 仿真。")
