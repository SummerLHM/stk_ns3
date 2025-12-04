"""
@Author   : wwq
@Date     ：2025/11/25
@Time     ：10:03
@Function :
            NS3 仿真运行与结果收集模块
            - 结果收集与分析
            - 支持共享文件夹数据交换
            - 生成分析报告
            - NS3 仿真运行与结果收集模块
            - 支持 IP 地址到卫星名称的映射

            适配环境:
            - 共享文件夹: sat_sim
            - NS3版本: 3.45
            - NS3路径: /repos_ns3/ns-3-allinone/ns-3.45
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class FlowResult:
    """单条流的仿真结果"""
    flow_id: int
    src_addr: str
    dst_addr: str
    src_satellite: str
    dst_satellite: str
    tx_packets: int
    rx_packets: int
    lost_packets: int
    throughput_mbps: float
    mean_delay_ms: float
    mean_jitter_ms: float
    packet_loss_rate: float


@dataclass
class SimulationSummary:
    """仿真结果摘要"""
    timestamp: str
    flow_count: int
    total_tx_packets: int
    total_rx_packets: int
    total_lost_packets: int
    avg_throughput_mbps: float
    max_throughput_mbps: float
    min_throughput_mbps: float
    avg_delay_ms: float
    max_delay_ms: float
    min_delay_ms: float
    avg_packet_loss_rate: float
    max_packet_loss_rate: float


class NS3ResultCollector:
    """NS3结果收集器"""

    def __init__(self, config_file: str = "ns3_config.json"):
        # 根据ns_config.json文件，取出对应的属性值
        self.config = self._load_config(config_file)
        # 读取属性，括号里第二个字段表示当不存在时返回的默认值
        self.ns3_input_dir = self.config.get("directories", {}).get("ns3_input", "ns3_input")
        self.ns3_output_dir = self.config.get("directories", {}).get("ns3_output", "ns3_results")

        shared = self.config.get("shared_folder", {})
        self.shared_windows = shared.get("windows_path", "")
        self.shared_linux = shared.get("linux_path", "")
        # 告诉要用的人，self.results 将来会存一堆 FlowResult 实例，初始是空列表。要么放 SimulationSummary 对象，要么什么都没有（None），引号后面是声明类型
        self.results: List[FlowResult] = []
        self.summary: Optional[SimulationSummary] = None
        # IP 到卫星名称的映射
        self.ip_to_satellite: Dict[str, str] = {}
        # 链路详细映射
        self.link_mapping: List[Dict] = []
        # 创建目录，如果目录已存则跳过
        os.makedirs(self.ns3_output_dir, exist_ok=True)

    """读取文件内容，并把JSON内容反序列化成Python字典"""
    def _load_config(self, config_file: str) -> Dict:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def load_ip_mapping(self) -> bool:
        """加载 IP 到卫星名称的映射"""
        print("\n📂 加载IP映射...")

        # 方法1: 从简单映射文件加载
        simple_mapping_file = os.path.join(self.ns3_input_dir, "ip_to_satellite.json")
        if os.path.exists(simple_mapping_file):
            try:
                with open(simple_mapping_file, 'r', encoding='utf-8') as f:
                    self.ip_to_satellite = json.load(f)
                print(f"   ✅ 从 ip_to_satellite.json 加载: {len(self.ip_to_satellite)} 条映射")
                return True
            except Exception as e:
                print(f"   ⚠️ 加载失败: {e}")

        # 方法2: 从详细链路映射文件加载
        detailed_mapping_file = os.path.join(self.ns3_input_dir, "link_ip_mapping.json")
        if os.path.exists(detailed_mapping_file):
            try:
                with open(detailed_mapping_file, 'r', encoding='utf-8') as f:
                    self.link_mapping = json.load(f)

                # 构建 IP -> 卫星名称映射
                for link in self.link_mapping:
                    self.ip_to_satellite[link["src_ip"]] = link["src_satellite"]
                    self.ip_to_satellite[link["dst_ip"]] = link["dst_satellite"]

                print(f"   ✅ 从 link_ip_mapping.json 加载: {len(self.ip_to_satellite)} 条映射")
                return True
            except Exception as e:
                print(f"   ⚠️ 加载失败: {e}")

        # 方法3: 从 link_params.csv 推断
        link_params_file = os.path.join(self.ns3_input_dir, "link_params.csv")
        if os.path.exists(link_params_file):
            try:
                df = pd.read_csv(link_params_file)
                for i, row in df.iterrows():
                    src_ip = f"10.0.{i}.1"
                    dst_ip = f"10.0.{i}.2"
                    self.ip_to_satellite[src_ip] = str(row.get('src_name', f'Node_{row.get("src_id", i)}'))
                    self.ip_to_satellite[dst_ip] = str(row.get('dst_name', f'Node_{row.get("dst_id", i)}'))

                print(f"   ✅ 从 link_params.csv 推断: {len(self.ip_to_satellite)} 条映射")
                return True
            except Exception as e:
                print(f"   ⚠️ 推断失败: {e}")

        print("   ❌ 未找到任何映射文件")
        return False

    def collect_results(self, result_file: str = None) -> Optional[pd.DataFrame]:
        """收集NS3仿真结果"""
        print("\n📥 收集NS3仿真结果...")

        if result_file is None:
            result_file = os.path.join(self.ns3_output_dir, "flow_results.csv")

        if not os.path.exists(result_file):
            print(f"   ⚠️ 结果文件不存在: {result_file}")
            return None

        try:
            df = pd.read_csv(result_file)
            print(f"   ✅ 读取结果: {len(df)} 条流数据")
        except Exception as e:
            print(f"   ❌ 读取失败: {e}")
            return None

        self.results = []
        for _, row in df.iterrows():
            try:
                result = FlowResult(
                    flow_id=int(row.get('FlowId', 0)),
                    src_addr=str(row.get('SrcAddr', '')),
                    dst_addr=str(row.get('DstAddr', '')),
                    src_satellite=str(row.get('SrcSatellite', 'Unknown')),  # 直接读取
                    dst_satellite=str(row.get('DstSatellite', 'Unknown')),  # 直接读取
                    tx_packets=int(row.get('TxPackets', 0)),
                    rx_packets=int(row.get('RxPackets', 0)),
                    lost_packets=int(row.get('LostPackets', 0)),
                    throughput_mbps=float(row.get('Throughput_Mbps', 0)),
                    mean_delay_ms=float(row.get('MeanDelay_ms', 0)),
                    mean_jitter_ms=float(row.get('MeanJitter_ms', 0)),
                    packet_loss_rate=float(row.get('PacketLossRate', 0))
                )
                self.results.append(result)
            except Exception as e:
                print(f"   ⚠️ 解析失败: {e}")

        return df
    def generate_summary(self) -> SimulationSummary:
        """生成仿真结果摘要"""
        if not self.results:
            print("⚠️ 无结果数据")
            return None

        throughputs = [r.throughput_mbps for r in self.results if r.throughput_mbps > 0]
        delays = [r.mean_delay_ms for r in self.results if r.mean_delay_ms > 0]
        plrs = [r.packet_loss_rate for r in self.results]

        self.summary = SimulationSummary(
            timestamp=datetime.now().isoformat(),
            flow_count=len(self.results),
            total_tx_packets=sum(r.tx_packets for r in self.results),
            total_rx_packets=sum(r.rx_packets for r in self.results),
            total_lost_packets=sum(r.lost_packets for r in self.results),
            avg_throughput_mbps=np.mean(throughputs) if throughputs else 0,
            max_throughput_mbps=max(throughputs) if throughputs else 0,
            min_throughput_mbps=min(throughputs) if throughputs else 0,
            avg_delay_ms=np.mean(delays) if delays else 0,
            max_delay_ms=max(delays) if delays else 0,
            min_delay_ms=min(delays) if delays else 0,
            avg_packet_loss_rate=np.mean(plrs) if plrs else 0,
            max_packet_loss_rate=max(plrs) if plrs else 0
        )

        return self.summary

    def save_analysis_report(self, output_file: str = None):
        """保存分析报告（包含卫星名称）"""
        if output_file is None:
            output_file = os.path.join(self.ns3_output_dir, "analysis_report.json")

        if not self.summary:
            self.generate_summary()

        if self.summary:
            report = {
                "summary": asdict(self.summary),
                "flows": [asdict(r) for r in self.results],
                "ip_mapping": self.ip_to_satellite
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            print(f"\n✅ 分析报告已保存: {output_file}")

    def print_results(self):
        """打印结果摘要（包含卫星名称）"""
        if not self.summary:
            self.generate_summary()

        if not self.summary:
            print("⚠️ 无结果数据")
            return

        s = self.summary

        print("\n" + "=" * 70)
        print("📊 NS3 仿真结果分析")
        print("=" * 70)

        print(f"\n📈 整体统计:")
        print(f"   流数量:     {s.flow_count}")
        print(f"   总发送包:   {s.total_tx_packets:,}")
        print(f"   总接收包:   {s.total_rx_packets:,}")
        print(f"   总丢失包:   {s.total_lost_packets:,}")

        print(f"\n📶 吞吐量 (Mbps):")
        print(f"   平均: {s.avg_throughput_mbps:.4f}")
        print(f"   最大: {s.max_throughput_mbps:.4f}")
        print(f"   最小: {s.min_throughput_mbps:.4f}")

        print(f"\n⏱️ 时延 (ms):")
        print(f"   平均: {s.avg_delay_ms:.4f}")
        print(f"   最大: {s.max_delay_ms:.4f}")
        print(f"   最小: {s.min_delay_ms:.4f}")

        print(f"\n📉 丢包率:")
        print(f"   平均: {s.avg_packet_loss_rate * 100:.2f}%")
        print(f"   最大: {s.max_packet_loss_rate * 100:.2f}%")

        # 打印各流详情（带卫星名称）
        print("\n" + "-" * 70)
        print("📋 各流详情 (卫星间通信)")
        print("-" * 70)

        for r in self.results:
            status = "✅" if r.packet_loss_rate < 1.0 else "❌"

            print(f"\n{status} 流 {r.flow_id}:")
            print(f"   ┌─────────────────────────────────────────────────────")
            print(f"   │ 源卫星:     {r.src_satellite}")
            print(f"   │ 源IP:       {r.src_addr}")
            print(f"   │ ─────────── → ───────────")
            print(f"   │ 目的卫星:   {r.dst_satellite}")
            print(f"   │ 目的IP:     {r.dst_addr}")
            print(f"   ├─────────────────────────────────────────────────────")
            print(f"   │ 吞吐量:     {r.throughput_mbps:.4f} Mbps")
            print(f"   │ 时延:       {r.mean_delay_ms:.4f} ms")
            print(f"   │ 抖动:       {r.mean_jitter_ms:.4f} ms")
            print(f"   │ 丢包率:     {r.packet_loss_rate * 100:.2f}%")
            print(f"   │ 收发包:     TX={r.tx_packets}, RX={r.rx_packets}, Lost={r.lost_packets}")
            print(f"   └─────────────────────────────────────────────────────")

        print("\n" + "=" * 70)

        # 打印通信失败的链路
        failed_flows = [r for r in self.results if r.packet_loss_rate >= 1.0]
        if failed_flows:
            print("\n⚠️ 完全丢包的链路:")
            for r in failed_flows:
                print(f"   流 {r.flow_id}: {r.src_satellite} → {r.dst_satellite}")

        # 打印成功的链路
        success_flows = [r for r in self.results if r.packet_loss_rate < 1.0]
        if success_flows:
            print(f"\n✅ 成功通信的链路 ({len(success_flows)}/{len(self.results)}):")
            for r in success_flows:
                print(f"   流 {r.flow_id}: {r.src_satellite} → {r.dst_satellite} "
                      f"(丢包率: {r.packet_loss_rate * 100:.1f}%)")


class NS3SimulationManager:
    """NS3仿真管理器"""

    def __init__(self, config_file: str = "ns3_config.json"):
        self.config_file = config_file
        self.collector = NS3ResultCollector(config_file)

    def check_results_available(self) -> bool:
        result_file = os.path.join(self.collector.ns3_output_dir, "flow_results.csv")
        return os.path.exists(result_file)

    def analyze_results(self) -> Optional[SimulationSummary]:
        df = self.collector.collect_results()

        if df is None or df.empty:
            return None

        self.collector.generate_summary()
        self.collector.print_results()
        self.collector.save_analysis_report()

        return self.collector.summary

    def generate_mock_results(self) -> pd.DataFrame:
        """生成模拟结果（用于测试）"""
        print("\n📝 生成模拟测试数据...")

        # 同时生成模拟的 IP 映射
        mock_mapping = {}
        mock_data = []

        satellite_pairs = [
            ("Sat_0_0", "Sat_0_1"),
            ("Sat_1_0", "Sat_1_1"),
            ("Sat_2_0", "Sat_2_1"),
            ("Sat_3_0", "Sat_3_1"),
            ("Sat_4_0", "Sat_4_1"),
        ]

        for i, (src_sat, dst_sat) in enumerate(satellite_pairs):
            src_ip = f"10.0.{i}.1"
            dst_ip = f"10.0.{i}.2"

            mock_mapping[src_ip] = src_sat
            mock_mapping[dst_ip] = dst_sat

            # 随机生成一些完全丢包的流
            if i in [1, 4]:  # 流2和流5完全丢包
                mock_data.append({
                    'FlowId': i + 1,
                    'SrcAddr': src_ip,
                    'DstAddr': dst_ip,
                    'TxPackets': 5187,
                    'RxPackets': 0,
                    'LostPackets': 5187,
                    'Throughput_Mbps': 0.0,
                    'MeanDelay_ms': 0.0,
                    'MeanJitter_ms': 0.0,
                    'PacketLossRate': 1.0
                })
            else:
                mock_data.append({
                    'FlowId': i + 1,
                    'SrcAddr': src_ip,
                    'DstAddr': dst_ip,
                    'TxPackets': 5187,
                    'RxPackets': 2000 + np.random.randint(0, 100),
                    'LostPackets': 3100 + np.random.randint(0, 100),
                    'Throughput_Mbps': 1.9 + np.random.random() * 0.2,
                    'MeanDelay_ms': 13.0,
                    'MeanJitter_ms': 0.0,
                    'PacketLossRate': 0.6 + np.random.random() * 0.02
                })

        # 保存模拟的 IP 映射
        os.makedirs(self.collector.ns3_input_dir, exist_ok=True)
        mapping_file = os.path.join(self.collector.ns3_input_dir, "ip_to_satellite.json")
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(mock_mapping, f, indent=2)
        print(f"   ✅ 模拟IP映射已保存: {mapping_file}")

        # 保存模拟的流结果
        df = pd.DataFrame(mock_data)
        output_file = os.path.join(self.collector.ns3_output_dir, "flow_results.csv")
        df.to_csv(output_file, index=False)
        print(f"   ✅ 模拟数据已保存: {output_file}")

        return df


if __name__ == "__main__":
    manager = NS3SimulationManager()

    if manager.check_results_available():
        manager.analyze_results()
    else:
        print("⚠️ NS3结果不可用，生成模拟数据进行测试...")
        manager.generate_mock_results()
        manager.analyze_results()
