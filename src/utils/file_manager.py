"""
虚拟电厂项目文件管理器
VPP Project File Manager

统一管理项目产生的各类文件和结果，按照调度模式、优化目标和时间进行组织
"""

import os
import shutil
import glob
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import pandas as pd

from ..models.scheduling_modes import SchedulingMode, OptimizationObjective


class VPPFileManager:
    """虚拟电厂文件管理器"""
    
    def __init__(self, base_output_dir: str = "outputs"):
        """
        初始化文件管理器
        
        Args:
            base_output_dir: 基础输出目录
        """
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(exist_ok=True)
        
        # 定义文件类型和子目录
        self.file_categories = {
            'input_data': 'data',           # 输入数据
            'optimization_results': 'results',  # 优化结果
            'economics_analysis': 'economics',   # 经济性分析
            'technical_metrics': 'metrics',      # 技术指标
            'summary_report': 'reports',         # 总结报告
            'mode_summary': 'reports',           # 模式总结
            'plots': 'plots',                    # 图表
            'comparison_report': 'comparisons',  # 对比报告
            'log_files': 'logs'                  # 日志文件
        }
        
        # 创建归档目录
        self.archive_dir = self.base_output_dir / "archive"
        self.archive_dir.mkdir(exist_ok=True)
    
    def create_session_directory(self, 
                                mode: SchedulingMode, 
                                objective: OptimizationObjective,
                                timestamp: Optional[str] = None) -> Path:
        """
        创建会话目录
        
        Args:
            mode: 调度模式
            objective: 优化目标
            timestamp: 时间戳（可选，默认使用当前时间）
            
        Returns:
            创建的会话目录路径
        """
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 格式：{mode}_{objective}_{timestamp}
        session_name = f"{mode.value}_{objective.value}_{timestamp}"
        session_dir = self.base_output_dir / session_name
        
        # 创建会话目录和子目录
        session_dir.mkdir(exist_ok=True)
        
        for category, subdir in self.file_categories.items():
            (session_dir / subdir).mkdir(exist_ok=True)
        
        return session_dir
    
    def get_file_path(self,
                     session_dir: Path,
                     file_type: str,
                     filename: str) -> Path:
        """
        获取指定类型文件的完整路径
        
        Args:
            session_dir: 会话目录
            file_type: 文件类型
            filename: 文件名
            
        Returns:
            文件完整路径
        """
        if file_type not in self.file_categories:
            raise ValueError(f"未知文件类型: {file_type}")
        
        subdir = self.file_categories[file_type]
        return session_dir / subdir / filename
    
    def save_file(self,
                 session_dir: Path,
                 file_type: str,
                 filename: str,
                 data,
                 **kwargs) -> Path:
        """
        保存文件到指定会话目录
        
        Args:
            session_dir: 会话目录
            file_type: 文件类型
            filename: 文件名
            data: 要保存的数据
            **kwargs: 额外参数
            
        Returns:
            保存的文件路径
        """
        file_path = self.get_file_path(session_dir, file_type, filename)
        
        # 根据数据类型选择保存方法
        if isinstance(data, pd.DataFrame):
            data.to_csv(file_path, index=False, encoding='utf-8-sig')
        elif isinstance(data, str):
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(data)
        elif isinstance(data, dict):
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            # 对于其他类型，尝试直接写入
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(str(data))
        
        print(f"[OK] 文件已保存: {file_path}")
        return file_path
    
    def copy_file_to_session(self,
                           source_path: Path,
                           session_dir: Path,
                           file_type: str,
                           new_filename: Optional[str] = None) -> Path:
        """
        复制文件到会话目录
        
        Args:
            source_path: 源文件路径
            session_dir: 会话目录
            file_type: 文件类型
            new_filename: 新文件名（可选）
            
        Returns:
            目标文件路径
        """
        if new_filename is None:
            new_filename = source_path.name
        
        target_path = self.get_file_path(session_dir, file_type, new_filename)
        
        shutil.copy2(source_path, target_path)
        print(f"[OK] 文件已复制: {source_path} -> {target_path}")
        
        return target_path
    
    def create_session_manifest(self, session_dir: Path, 
                              mode: SchedulingMode,
                              objective: OptimizationObjective,
                              metadata: Optional[Dict] = None) -> Path:
        """
        创建会话清单文件
        
        Args:
            session_dir: 会话目录
            mode: 调度模式
            objective: 优化目标
            metadata: 额外元数据
            
        Returns:
            清单文件路径
        """
        manifest = {
            'session_info': {
                'session_directory': str(session_dir.name),
                'creation_time': datetime.now().isoformat(),
                'scheduling_mode': mode.value,
                'optimization_objective': objective.value
            },
            'file_structure': {},
            'metadata': metadata or {}
        }
        
        # 扫描文件结构
        for category, subdir in self.file_categories.items():
            subdir_path = session_dir / subdir
            if subdir_path.exists():
                files = [f.name for f in subdir_path.glob('*') if f.is_file()]
                manifest['file_structure'][category] = {
                    'directory': subdir,
                    'files': files,
                    'count': len(files)
                }
        
        manifest_path = session_dir / "session_manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] 会话清单已创建: {manifest_path}")
        return manifest_path
    
    def cleanup_legacy_files(self, dry_run: bool = True) -> Dict[str, List[str]]:
        """
        清理旧的散乱文件
        
        Args:
            dry_run: 是否只是预览而不实际删除
            
        Returns:
            清理操作的详细信息
        """
        cleanup_info = {
            'files_to_archive': [],
            'directories_to_archive': [],
            'files_to_delete': []
        }
        
        # 扫描散乱的文件
        for pattern in ['*.csv', '*.txt', '*.png', '*.jpg']:
            for file_path in self.base_output_dir.glob(pattern):
                if file_path.is_file():
                    cleanup_info['files_to_archive'].append(str(file_path))
        
        # 扫描旧的目录结构
        legacy_patterns = ['mode_*', 'plots', 'reports']
        for pattern in legacy_patterns:
            for dir_path in self.base_output_dir.glob(pattern):
                if dir_path.is_dir() and not dir_path.name.startswith('mode_') or \
                   dir_path.name.count('_') < 3:  # 不符合新命名规则的目录
                    cleanup_info['directories_to_archive'].append(str(dir_path))
        
        if not dry_run:
            # 执行清理操作
            archive_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_session_dir = self.archive_dir / f"legacy_cleanup_{archive_timestamp}"
            archive_session_dir.mkdir(exist_ok=True)
            
            # 归档文件
            for file_path_str in cleanup_info['files_to_archive']:
                file_path = Path(file_path_str)
                if file_path.exists():
                    shutil.move(str(file_path), str(archive_session_dir / file_path.name))
            
            # 归档目录
            for dir_path_str in cleanup_info['directories_to_archive']:
                dir_path = Path(dir_path_str)
                if dir_path.exists():
                    shutil.move(str(dir_path), str(archive_session_dir / dir_path.name))
            
            print(f"[OK] 旧文件已归档到: {archive_session_dir}")
        
        return cleanup_info
    
    def list_sessions(self) -> List[Dict[str, str]]:
        """
        列出所有会话
        
        Returns:
            会话列表，包含会话信息
        """
        sessions = []
        
        # 查找符合命名规则的目录：{mode}_{objective}_{timestamp}
        for session_dir in self.base_output_dir.glob('*_*_*'):
            if session_dir.is_dir() and session_dir.name.count('_') >= 2:
                parts = session_dir.name.split('_')
                if len(parts) >= 3:
                    try:
                        mode_part = parts[0]
                        objective_part = parts[1]
                        timestamp_part = '_'.join(parts[2:])
                        
                        session_info = {
                            'directory': session_dir.name,
                            'mode': mode_part,
                            'objective': objective_part,
                            'timestamp': timestamp_part,
                            'full_path': str(session_dir)
                        }
                        
                        # 检查是否有清单文件
                        manifest_path = session_dir / "session_manifest.json"
                        if manifest_path.exists():
                            session_info['has_manifest'] = True
                        else:
                            session_info['has_manifest'] = False
                        
                        sessions.append(session_info)
                    except Exception:
                        continue
        
        # 按时间戳排序
        sessions.sort(key=lambda x: x['timestamp'], reverse=True)
        return sessions
    
    def get_session_summary(self, session_dir: Path) -> Dict:
        """
        获取会话摘要信息
        
        Args:
            session_dir: 会话目录
            
        Returns:
            会话摘要信息
        """
        summary = {
            'directory': session_dir.name,
            'file_counts': {},
            'total_files': 0,
            'total_size_mb': 0
        }
        
        # 统计文件数量和大小
        for category, subdir in self.file_categories.items():
            subdir_path = session_dir / subdir
            if subdir_path.exists():
                files = list(subdir_path.glob('*'))
                file_count = len([f for f in files if f.is_file()])
                
                # 计算总大小
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                
                summary['file_counts'][category] = file_count
                summary['total_files'] += file_count
                summary['total_size_mb'] += total_size / (1024 * 1024)
        
        return summary


class SessionContext:
    """会话上下文管理器"""
    
    def __init__(self, 
                 file_manager: VPPFileManager,
                 mode: SchedulingMode,
                 objective: OptimizationObjective,
                 timestamp: Optional[str] = None):
        """
        初始化会话上下文
        
        Args:
            file_manager: 文件管理器实例
            mode: 调度模式
            objective: 优化目标
            timestamp: 时间戳
        """
        self.file_manager = file_manager
        self.mode = mode
        self.objective = objective
        self.timestamp = timestamp or datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session_dir = None
    
    def __enter__(self):
        """进入会话上下文"""
        self.session_dir = self.file_manager.create_session_directory(
            self.mode, self.objective, self.timestamp
        )
        print(f"[DIR] 会话目录已创建: {self.session_dir}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出会话上下文"""
        if self.session_dir:
            # 创建会话清单
            self.file_manager.create_session_manifest(
                self.session_dir, self.mode, self.objective
            )
            print(f"[MANIFEST] 会话已完成: {self.session_dir.name}")
    
    def save_file(self, file_type: str, filename: str, data, **kwargs) -> Path:
        """保存文件到当前会话"""
        return self.file_manager.save_file(
            self.session_dir, file_type, filename, data, **kwargs
        )
    
    def get_file_path(self, file_type: str, filename: str) -> Path:
        """获取文件路径"""
        return self.file_manager.get_file_path(
            self.session_dir, file_type, filename
        )


# 示例使用
if __name__ == "__main__":
    # 创建文件管理器
    file_manager = VPPFileManager()
    
    # 使用会话上下文
    with SessionContext(file_manager, 
                       SchedulingMode.FULL_SYSTEM, 
                       OptimizationObjective.PROFIT_MAXIMIZATION) as session:
        
        # 保存示例数据
        import pandas as pd
        df = pd.DataFrame({'test': [1, 2, 3]})
        session.save_file('optimization_results', 'test_results.csv', df)
        
        session.save_file('summary_report', 'test_report.txt', "测试报告内容")
    
    # 列出所有会话
    sessions = file_manager.list_sessions()
    print(f"发现 {len(sessions)} 个会话")
    for session in sessions:
        print(f"  {session['directory']}")