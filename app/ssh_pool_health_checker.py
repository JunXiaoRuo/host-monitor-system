"""
SSH连接池健康检查工具
提供连接池健康状态监控和诊断功能
"""

import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class HealthCheckResult:
    """健康检查结果"""
    server: str
    is_healthy: bool
    response_time: float
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class SSHPoolHealthChecker:
    """SSH连接池健康检查器"""
    
    def __init__(self, ssh_manager):
        self.ssh_manager = ssh_manager
        self.health_history: Dict[str, List[HealthCheckResult]] = {}
        self.max_history_size = 100
    
    def check_pool_health(self) -> Dict[str, Any]:
        """检查整个连接池的健康状态"""
        if not hasattr(self.ssh_manager, 'ssh_pool') or not self.ssh_manager.ssh_pool:
            return {
                'status': 'disabled',
                'message': '连接池未启用',
                'timestamp': datetime.now().isoformat()
            }
        
        pool_stats = self.ssh_manager.get_pool_stats()
        health_results = []
        
        # 检查每个服务器的连接健康状态
        for conn_info, pool in self.ssh_manager.ssh_pool.pools.items():
            server_key = f"{conn_info.host}:{conn_info.port}"
            
            # 统计该服务器的连接状态
            total_connections = len(pool)
            healthy_connections = sum(1 for conn in pool if conn.is_healthy)
            in_use_connections = sum(1 for conn in pool if conn.is_in_use)
            
            # 执行健康检查
            health_result = self._check_server_health(conn_info)
            health_results.append({
                'server': server_key,
                'total_connections': total_connections,
                'healthy_connections': healthy_connections,
                'in_use_connections': in_use_connections,
                'health_check': health_result.__dict__
            })
            
            # 保存健康检查历史
            self._save_health_history(server_key, health_result)
        
        # 计算整体健康分数
        overall_health = self._calculate_overall_health(health_results, pool_stats)
        
        return {
            'status': 'healthy' if overall_health['score'] >= 0.8 else 'unhealthy',
            'overall_health': overall_health,
            'pool_statistics': pool_stats,
            'server_health': health_results,
            'timestamp': datetime.now().isoformat()
        }
    
    def _check_server_health(self, conn_info) -> HealthCheckResult:
        """检查单个服务器的健康状态"""
        server_key = f"{conn_info.host}:{conn_info.port}"
        start_time = time.time()
        
        try:
            # 尝试获取一个连接并执行简单命令
            with self.ssh_manager.get_connection(conn_info.host, conn_info.port, 
                                               conn_info.username, conn_info.password, 
                                               conn_info.private_key_path) as ssh:
                stdin, stdout, stderr = ssh.exec_command('echo "health_check"', timeout=5)
                result = stdout.read().decode().strip()
                
                response_time = time.time() - start_time
                
                if result == "health_check":
                    return HealthCheckResult(
                        server=server_key,
                        is_healthy=True,
                        response_time=response_time
                    )
                else:
                    return HealthCheckResult(
                        server=server_key,
                        is_healthy=False,
                        response_time=response_time,
                        error_message=f"意外的响应: {result}"
                    )
                    
        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                server=server_key,
                is_healthy=False,
                response_time=response_time,
                error_message=str(e)
            )
    
    def _save_health_history(self, server_key: str, result: HealthCheckResult):
        """保存健康检查历史"""
        if server_key not in self.health_history:
            self.health_history[server_key] = []
        
        self.health_history[server_key].append(result)
        
        # 限制历史记录大小
        if len(self.health_history[server_key]) > self.max_history_size:
            self.health_history[server_key] = self.health_history[server_key][-self.max_history_size:]
    
    def _calculate_overall_health(self, health_results: List[Dict], pool_stats: Dict) -> Dict[str, Any]:
        """计算整体健康分数"""
        if not health_results:
            return {
                'score': 0.0,
                'status': 'no_servers',
                'details': '没有服务器连接'
            }
        
        # 计算健康服务器比例
        healthy_servers = sum(1 for result in health_results 
                            if result['health_check']['is_healthy'])
        total_servers = len(health_results)
        server_health_ratio = healthy_servers / total_servers if total_servers > 0 else 0
        
        # 计算连接健康比例
        total_connections = sum(result['total_connections'] for result in health_results)
        healthy_connections = sum(result['healthy_connections'] for result in health_results)
        connection_health_ratio = healthy_connections / total_connections if total_connections > 0 else 0
        
        # 计算平均响应时间
        response_times = [result['health_check']['response_time'] 
                         for result in health_results 
                         if result['health_check']['is_healthy']]
        avg_response_time = sum(response_times) / len(response_times) if response_times else float('inf')
        
        # 计算综合健康分数 (0-1)
        # 服务器健康权重: 40%
        # 连接健康权重: 40%
        # 响应时间权重: 20% (响应时间越短分数越高)
        response_score = max(0, 1 - (avg_response_time / 10))  # 10秒以上响应时间得0分
        
        overall_score = (
            server_health_ratio * 0.4 +
            connection_health_ratio * 0.4 +
            response_score * 0.2
        )
        
        return {
            'score': round(overall_score, 3),
            'server_health_ratio': round(server_health_ratio, 3),
            'connection_health_ratio': round(connection_health_ratio, 3),
            'avg_response_time': round(avg_response_time, 3),
            'healthy_servers': healthy_servers,
            'total_servers': total_servers,
            'healthy_connections': healthy_connections,
            'total_connections': total_connections
        }
    
    def get_health_trends(self, server: Optional[str] = None, hours: int = 24) -> Dict[str, Any]:
        """获取健康状态趋势"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        trends = {}
        
        servers_to_check = [server] if server else list(self.health_history.keys())
        
        for server_key in servers_to_check:
            if server_key not in self.health_history:
                continue
                
            # 过滤指定时间范围内的记录
            recent_results = [
                result for result in self.health_history[server_key]
                if result.timestamp >= cutoff_time
            ]
            
            if not recent_results:
                continue
            
            # 计算趋势统计
            total_checks = len(recent_results)
            successful_checks = sum(1 for result in recent_results if result.is_healthy)
            success_rate = successful_checks / total_checks if total_checks > 0 else 0
            
            response_times = [result.response_time for result in recent_results if result.is_healthy]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            # 最近的错误
            recent_errors = [
                result.error_message for result in recent_results[-10:]
                if not result.is_healthy and result.error_message
            ]
            
            trends[server_key] = {
                'total_checks': total_checks,
                'success_rate': round(success_rate, 3),
                'avg_response_time': round(avg_response_time, 3),
                'recent_errors': recent_errors,
                'last_check': recent_results[-1].timestamp.isoformat() if recent_results else None
            }
        
        return trends
    
    def diagnose_issues(self) -> List[Dict[str, Any]]:
        """诊断连接池问题"""
        issues = []
        
        if not hasattr(self.ssh_manager, 'ssh_pool') or not self.ssh_manager.ssh_pool:
            issues.append({
                'type': 'configuration',
                'severity': 'warning',
                'message': 'SSH连接池未启用',
                'recommendation': '启用连接池以提高性能和稳定性'
            })
            return issues
        
        pool_stats = self.ssh_manager.get_pool_stats()
        
        # 检查连接池利用率
        if pool_stats['total_connections'] == 0:
            issues.append({
                'type': 'usage',
                'severity': 'info',
                'message': '连接池中没有活跃连接',
                'recommendation': '这可能是正常的，如果系统刚启动或没有监控任务'
            })
        
        # 检查连接失败率
        stats = pool_stats.get('statistics', {})
        total_created = stats.get('total_connections_created', 0)
        total_closed = stats.get('total_connections_closed', 0)
        
        if total_created > 0:
            failure_rate = total_closed / total_created
            if failure_rate > 0.3:  # 30%以上的连接被关闭
                issues.append({
                    'type': 'reliability',
                    'severity': 'warning',
                    'message': f'连接失败率较高: {failure_rate:.1%}',
                    'recommendation': '检查网络连接和服务器配置'
                })
        
        # 检查健康检查失败
        failed_health_checks = stats.get('failed_health_checks', 0)
        total_health_checks = stats.get('total_health_checks', 0)
        
        if total_health_checks > 0:
            health_failure_rate = failed_health_checks / total_health_checks
            if health_failure_rate > 0.2:  # 20%以上的健康检查失败
                issues.append({
                    'type': 'health',
                    'severity': 'error',
                    'message': f'健康检查失败率: {health_failure_rate:.1%}',
                    'recommendation': '检查服务器状态和网络连接'
                })
        
        # 检查连接池命中率
        pool_hits = stats.get('pool_hits', 0)
        pool_misses = stats.get('pool_misses', 0)
        total_requests = pool_hits + pool_misses
        
        if total_requests > 0:
            hit_rate = pool_hits / total_requests
            if hit_rate < 0.5:  # 命中率低于50%
                issues.append({
                    'type': 'performance',
                    'severity': 'warning',
                    'message': f'连接池命中率较低: {hit_rate:.1%}',
                    'recommendation': '考虑增加最大连接数或调整连接保持时间'
                })
        
        return issues