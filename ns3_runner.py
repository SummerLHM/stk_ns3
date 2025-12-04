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

"""
"""
NS3仿真管理器
"""

import os
import glob
import pandas as pd


class NS3SimulationManager:
    """NS3仿真管理器"""

    def __init__(self, config_file: str = "ns3_config.json"):
        self.config_file = config_file
        self.results_dir = "ns3_results"

    def _sort_by_slice_id(self, files: list) -> list:
        """按时间片编号排序"""
        return sorted(files, key=lambda x: int(x.split("slice_")[1].replace(".csv", "")))

    def check_results_available(self) -> bool:
        """检查NS3结果是否可用"""
        result_files = glob.glob(f"{self.results_dir}/flow_results_slice_*.csv")

        if result_files:
            result_files = self._sort_by_slice_id(result_files)
            print(f"✅ 找到 {len(result_files)} 个结果文件")
            for f in result_files:
                print(f"   - {f}")
            return True

        print("❌ 未找到结果文件")
        return False

    def analyze_results(self):
        """分析NS3结果"""
        result_files = glob.glob(f"{self.results_dir}/flow_results_slice_*.csv")

        if not result_files:
            print("❌ 没有结果文件")
            return

        result_files = self._sort_by_slice_id(result_files)

        # 合并所有时间片结果
        all_results = []
        for f in result_files:
            try:
                df = pd.read_csv(f)
                if df.empty:
                    continue
                slice_id = int(f.split("slice_")[1].replace(".csv", ""))
                df['slice_id'] = slice_id
                all_results.append(df)
                print(f"📊 加载: {f} ({len(df)} 条流)")
            except Exception as e:
                print(f"⚠️ 读取失败 {f}: {e}")

        if not all_results:
            print("❌ 没有有效数据")
            return

        combined = pd.concat(all_results, ignore_index=True)

        print("\n" + "=" * 60)
        print("📈 仿真结果汇总")
        print("=" * 60)
        print(f"总时间片数: {len(result_files)}")
        print(f"总流量数: {len(combined)}")

        # 平均时延
        if 'delay_sum_ns' in combined.columns and 'rx_packets' in combined.columns:
            valid = combined[combined['rx_packets'] > 0]
            if len(valid) > 0:
                avg_delay = (valid['delay_sum_ns'] / valid['rx_packets']).mean() / 1e6
                print(f"平均时延: {avg_delay:.2f} ms")

        # 丢包率
        if 'tx_packets' in combined.columns and 'rx_packets' in combined.columns:
            total_tx = combined['tx_packets'].sum()
            total_rx = combined['rx_packets'].sum()
            if total_tx > 0:
                loss_rate = (total_tx - total_rx) / total_tx * 100
                print(f"丢包率: {loss_rate:.2f}%")

        # 吞吐量
        if 'rx_bytes' in combined.columns:
            total_bytes = combined['rx_bytes'].sum()
            print(f"总吞吐量: {total_bytes / 1e6:.2f} MB")

        # 保存
        combined.to_csv(f"{self.results_dir}/combined_results.csv", index=False)
        print(f"\n💾 已保存: {self.results_dir}/combined_results.csv")
