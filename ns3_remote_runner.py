"""
@Author   : wwq
@Date     ：2025/11/25
@Function :
            NS3 远程运行模块（仅共享文件夹模式）
            通过 VMware/VirtualBox 共享文件夹与 Linux 虚拟机中的 NS3 通信
"""

import os
import time
import shutil
from typing import Optional, Dict
import pandas as pd


class NS3RemoteRunner:
    """NS3远程运行器（共享文件夹模式）"""

    def __init__(self,
                 shared_folder_windows: str = None,
                 shared_folder_linux: str = None,
                 ns3_path: str = None):
        """
        初始化

        Args:
            shared_folder_windows: Windows端共享文件夹路径
            shared_folder_linux: Linux端共享文件夹路径
            ns3_path: Linux中NS3的安装路径
        """
        # 共享文件夹配置
        self.shared_folder_windows = shared_folder_windows or r"D:\PycharmProjects\satelliteProject\ns3_and_STK_demo"
        self.shared_folder_linux = shared_folder_linux or "/mnt/hgfs/sat_sim"

        # NS3配置
        self.ns3_path = ns3_path or "/home/wwq/repos_ns3/ns-3-allinone/ns-3.45"

        # 本地目录
        self.local_input_dir = "ns3_input"
        self.local_result_dir = "ns3_results"

        os.makedirs(self.local_input_dir, exist_ok=True)
        os.makedirs(self.local_result_dir, exist_ok=True)

    def setup_shared_folder(self):
        """设置共享文件夹"""
        print(f"\n📁 配置共享文件夹...")
        print(f"   Windows路径: {self.shared_folder_windows}")
        print(f"   Linux路径: {self.shared_folder_linux}")

        # 创建Windows端目录
        os.makedirs(self.shared_folder_windows, exist_ok=True)
        os.makedirs(os.path.join(self.shared_folder_windows, "ns3_input"), exist_ok=True)
        os.makedirs(os.path.join(self.shared_folder_windows, "ns3_results"), exist_ok=True)

        print("   ✅ Windows端目录已创建")

    def copy_input_files(self):
        """复制输入文件到共享文件夹"""
        print("\n📤 复制输入文件到共享文件夹...")

        src_dir = self.local_input_dir
        dst_dir = os.path.join(self.shared_folder_windows, "ns3_input")

        os.makedirs(dst_dir, exist_ok=True)

        count = 0
        for filename in os.listdir(src_dir):
            src = os.path.join(src_dir, filename)
            dst = os.path.join(dst_dir, filename)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                count += 1
                print(f"   ✅ {filename}")

        print(f"   共复制 {count} 个文件")
        return True

    def collect_results(self, result_filename: str = "flow_results.csv") -> Optional[pd.DataFrame]:
        """从共享文件夹收集仿真结果"""
        print("\n📥 收集仿真结果...")

        result_file = os.path.join(self.shared_folder_windows, "ns3_results", result_filename)

        # 等待文件生成
        max_wait = 120
        waited = 0
        while (not os.path.exists(result_file) or os.path.getsize(result_file) == 0) and waited < max_wait:
            print(f"   等待结果文件... ({waited}s)")
            time.sleep(5)
            waited += 5

        if os.path.exists(result_file) and os.path.getsize(result_file) > 0:
            try:
                df = pd.read_csv(result_file)
                # 复制到本地结果目录
                local_path = os.path.join(self.local_result_dir, result_filename)
                shutil.copy2(result_file, local_path)
                print(f"   ✅ 结果已收集: {len(df)} 条记录")
                return df
            except Exception as e:
                print(f"   ❌ 读取结果失败: {e}")
                return None
        else:
            print("   ❌ 未找到结果文件或文件为空")
            return None

class NS3SimulationManager:
    """NS3仿真管理器"""

    def __init__(self, config: Dict = None):
        """
        初始化

        Args:
            config: 配置字典，包含以下可选项：
                - shared_folder_windows: Windows共享文件夹路径
                - shared_folder_linux: Linux共享文件夹路径
                - ns3_path: NS3安装路径
        """
        self.config = config or {}

        self.runner = NS3RemoteRunner(
            shared_folder_windows=self.config.get('shared_folder_windows'),
            shared_folder_linux=self.config.get('shared_folder_linux'),
            ns3_path=self.config.get('ns3_path')
        )

    def prepare_simulation(self):
        """准备仿真环境"""
        print("\n" + "=" * 60)
        print("准备NS3仿真环境")
        print("=" * 60)

        # 设置共享文件夹
        self.runner.setup_shared_folder()

        # 复制输入文件
        self.runner.copy_input_files()

    def collect_results(self, result_filename: str = "flow_results.csv") -> Optional[pd.DataFrame]:
        """收集仿真结果"""
        return self.runner.collect_results(result_filename)

    def collect_all_slice_results(self) -> Optional[pd.DataFrame]:
        """收集所有时间片的仿真结果"""
        print("\n📥 收集所有时间片结果...")

        result_dir = os.path.join(self.runner.shared_folder_windows, "ns3_results")

        if not os.path.exists(result_dir):
            print(f"   ❌ 结果目录不存在: {result_dir}")
            return None

        import glob
        files = glob.glob(os.path.join(result_dir, "flow_results_slice_*.csv"))

        if not files:
            print("   ❌ 未找到时间片结果文件")
            return None

        all_data = []
        for f in sorted(files):
            try:
                df = pd.read_csv(f)
                # 从文件名提取 slice_id
                slice_id = int(os.path.basename(f).split('_')[-1].split('.')[0])
                df['slice_id'] = slice_id
                all_data.append(df)
                print(f"   ✅ {os.path.basename(f)}: {len(df)} 条记录")
            except Exception as e:
                print(f"   ⚠️ 读取失败 {os.path.basename(f)}: {e}")

        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            print(f"\n   📊 总计: {len(combined)} 条记录，{len(all_data)} 个时间片")
            return combined
        else:
            return None


# ==================== 配置模板 ====================
DEFAULT_CONFIG = {
    "shared_folder_windows": r"D:\PycharmProjects\satelliteProject\ns3_and_STK_demo",
    "shared_folder_linux": "/mnt/hgfs/sat_sim",
    "ns3_path": "/home/wwq/repos_ns3/ns-3-allinone/ns-3.45"
}

if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("NS3 远程运行模块测试（共享文件夹模式）")
    print("=" * 60)

    manager = NS3SimulationManager(DEFAULT_CONFIG)
    manager.prepare_simulation()
