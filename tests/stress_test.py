# stress_test.py - 压力测试脚本
import asyncio
import json
import random
import time
from datetime import datetime
from typing import Dict, List

import httpx

test_host = "http://35.162.200.109:8444/"

class StressTestClient:
    """压力测试客户端"""
    
    def __init__(self, base_url: str = test_host):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.results = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limited": 0,
            "response_times": [],
            "errors": [],
            "task_ids": []
        }
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
    
    async def submit_data_processing_task(self, data: Dict, priority: int = 0) -> Dict:
        """提交数据处理任务"""
        url = f"{self.base_url}/api/v1/foo/tasks/data-processing"
        payload = {
            "data": data,
            "options": {"batch_id": f"batch_{random.randint(1000, 9999)}"}
        }
        
        start_time = time.time()
        try:
            response = await self.client.post(
                url,
                json=payload,
                params={"priority": priority, "timeout": 60}
            )
            
            response_time = time.time() - start_time
            self.results["response_times"].append(response_time)
            self.results["total_requests"] += 1
            
            if response.status_code == 200:
                self.results["successful_requests"] += 1
                result = response.json()
                if result.get("success") and result.get("data", {}).get("task_id"):
                    self.results["task_ids"].append(result["data"]["task_id"])
                return {"success": True, "response": result, "response_time": response_time}
            
            elif response.status_code == 429:
                self.results["rate_limited"] += 1
                return {"success": False, "error": "rate_limited", "response_time": response_time}
            
            else:
                self.results["failed_requests"] += 1
                return {"success": False, "error": f"HTTP {response.status_code}", "response_time": response_time}
                
        except Exception as e:
            response_time = time.time() - start_time
            self.results["response_times"].append(response_time)
            self.results["total_requests"] += 1
            self.results["failed_requests"] += 1
            self.results["errors"].append(str(e))
            return {"success": False, "error": str(e), "response_time": response_time}
    
    async def submit_file_processing_task(self, file_path: str, file_size: int = None) -> Dict:
        """提交文件处理任务"""
        url = f"{self.base_url}/api/v1/foo/tasks/file-processing"
        payload = {
            "file_path": file_path,
            "file_size": file_size or random.randint(1000, 50000),
            "format": random.choice(["text", "json", "xml", "csv"])
        }
        
        start_time = time.time()
        try:
            response = await self.client.post(
                url,
                json=payload,
                params={"priority": random.randint(-1, 2), "timeout": 120}
            )
            
            response_time = time.time() - start_time
            self.results["response_times"].append(response_time)
            self.results["total_requests"] += 1
            
            if response.status_code == 200:
                self.results["successful_requests"] += 1
                result = response.json()
                if result.get("success") and result.get("data", {}).get("task_id"):
                    self.results["task_ids"].append(result["data"]["task_id"])
                return {"success": True, "response": result, "response_time": response_time}
            
            elif response.status_code == 429:
                self.results["rate_limited"] += 1
                return {"success": False, "error": "rate_limited", "response_time": response_time}
            
            else:
                self.results["failed_requests"] += 1
                return {"success": False, "error": f"HTTP {response.status_code}", "response_time": response_time}
                
        except Exception as e:
            response_time = time.time() - start_time
            self.results["response_times"].append(response_time)
            self.results["total_requests"] += 1
            self.results["failed_requests"] += 1
            return {"success": False, "error": str(e), "response_time": response_time}
    
    async def submit_external_api_task(self, api_endpoint: str) -> Dict:
        """提交外部API任务（用于测试重试）"""
        url = f"{self.base_url}/api/v1/foo/tasks/external-api"
        payload = {
            "api_endpoint": api_endpoint,
            "params": {"test_param": random.randint(1, 1000)}
        }
        
        start_time = time.time()
        try:
            response = await self.client.post(
                url,
                json=payload,
                params={"priority": 1, "timeout": 30}
            )
            
            response_time = time.time() - start_time
            self.results["response_times"].append(response_time)
            self.results["total_requests"] += 1
            
            if response.status_code == 200:
                self.results["successful_requests"] += 1
                result = response.json()
                if result.get("success") and result.get("data", {}).get("task_id"):
                    self.results["task_ids"].append(result["data"]["task_id"])
                return {"success": True, "response": result, "response_time": response_time}
            
            elif response.status_code == 429:
                self.results["rate_limited"] += 1
                return {"success": False, "error": "rate_limited", "response_time": response_time}
            
            else:
                self.results["failed_requests"] += 1
                return {"success": False, "error": f"HTTP {response.status_code}", "response_time": response_time}
                
        except Exception as e:
            response_time = time.time() - start_time
            self.results["response_times"].append(response_time)
            self.results["total_requests"] += 1
            self.results["failed_requests"] += 1
            return {"success": False, "error": str(e), "response_time": response_time}
    
    async def get_task_status(self, task_id: str) -> Dict:
        """获取任务状态"""
        url = f"{self.base_url}/api/v1/tasks/{task_id}/status"
        
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                return {"success": True, "response": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_task_statistics(self) -> Dict:
        """获取任务统计"""
        url = f"{self.base_url}/api/v1/tasks/statistics"
        
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                return {"success": True, "response": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_test_data(self, size: str = "medium") -> Dict:
        """生成测试数据"""
        if size == "small":
            return {"numbers": [random.random() for _ in range(10)], "text": "small test"}
        elif size == "large":
            return {
                "numbers": [random.random() for _ in range(1000)],
                "text": "large test data " * 100,
                "nested": {"data": [{"id": i, "value": random.random()} for i in range(100)]}
            }
        else:  # medium
            return {
                "numbers": [random.random() for _ in range(100)],
                "text": "medium test data " * 10,
                "metadata": {"timestamp": datetime.now().isoformat()}
            }
    
    def print_results(self):
        """打印测试结果"""
        print("\n" + "="*60)
        print("压力测试结果")
        print("="*60)
        print(f"总请求数: {self.results['total_requests']}")
        print(f"成功请求: {self.results['successful_requests']}")
        print(f"失败请求: {self.results['failed_requests']}")
        print(f"限流请求: {self.results['rate_limited']}")
        print(f"提交的任务: {len(self.results['task_ids'])}")
        
        if self.results["response_times"]:
            avg_response_time = sum(self.results["response_times"]) / len(self.results["response_times"])
            max_response_time = max(self.results["response_times"])
            min_response_time = min(self.results["response_times"])
            print(f"平均响应时间: {avg_response_time:.3f}s")
            print(f"最大响应时间: {max_response_time:.3f}s")
            print(f"最小响应时间: {min_response_time:.3f}s")
        
        if self.results["errors"]:
            print(f"错误类型: {set(self.results['errors'])}")
        
        success_rate = self.results['successful_requests'] / self.results['total_requests'] * 100 if self.results['total_requests'] > 0 else 0
        print(f"成功率: {success_rate:.1f}%")


async def run_basic_stress_test():
    """运行基础压力测试"""
    print("开始基础压力测试...")
    
    client = StressTestClient()
    
    try:
        # 并发提交不同类型的任务
        tasks = []
        
        # 数据处理任务 (50个)
        for i in range(50):
            test_data = client.generate_test_data(random.choice(["small", "medium", "large"]))
            priority = random.randint(-2, 2)
            tasks.append(client.submit_data_processing_task(test_data, priority))
        
        # 文件处理任务 (30个)
        for i in range(30):
            file_path = f"/test/file_{i}.txt"
            tasks.append(client.submit_file_processing_task(file_path))
        
        # 外部API任务 (20个，测试重试)
        for i in range(20):
            api_endpoint = f"https://api.example.com/endpoint_{i}"
            tasks.append(client.submit_external_api_task(api_endpoint))
        
        print(f"并发提交 {len(tasks)} 个任务...")
        
        # 并发执行所有任务
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        print(f"任务提交完成，耗时: {total_time:.2f}s")
        
        # 等待一些任务完成
        print("等待任务执行...")
        await asyncio.sleep(5)
        
        # 检查任务状态
        print("检查任务状态...")
        status_tasks = []
        for task_id in client.results["task_ids"][:10]:  # 检查前10个任务
            status_tasks.append(client.get_task_status(task_id))
        
        status_results = await asyncio.gather(*status_tasks, return_exceptions=True)
        
        completed_tasks = 0
        running_tasks = 0
        for result in status_results:
            if isinstance(result, dict) and result.get("success"):
                status = result["response"]["data"]["status"]
                if status in ["success", "failed", "cancelled"]:
                    completed_tasks += 1
                elif status == "running":
                    running_tasks += 1
        
        print(f"检查的任务中: {completed_tasks} 个已完成, {running_tasks} 个运行中")
        
        # 获取系统统计
        stats_result = await client.get_task_statistics()
        if stats_result.get("success"):
            stats = stats_result["response"]["data"]
            print(f"系统统计: 总任务 {stats.get('total_tasks', 0)}, "
                  f"运行中 {stats.get('running_tasks', 0)}, "
                  f"已完成 {stats.get('completed_tasks', 0)}")
        
        # 打印测试结果
        client.print_results()
        
    finally:
        await client.close()


async def run_rate_limit_test():
    """运行限流测试"""
    print("\n开始限流测试...")
    
    client = StressTestClient()
    
    try:
        # 快速连续请求同一个接口，触发限流
        print("快速连续发送请求以触发限流...")
        
        tasks = []
        test_data = client.generate_test_data("small")
        
        # 在1秒内发送100个请求，应该会触发限流（限制是50/分钟）
        for i in range(100):
            tasks.append(client.submit_data_processing_task(test_data, 0))
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        print(f"发送100个请求耗时: {total_time:.2f}s")
        client.print_results()
        
        print(f"限流测试结果: {client.results['rate_limited']} 个请求被限流")
        
    finally:
        await client.close()


async def run_retry_test():
    """运行重试测试"""
    print("\n开始重试测试...")
    
    client = StressTestClient()
    
    try:
        # 提交外部API任务，这些任务有15%的失败率和3次重试
        print("提交外部API任务以测试重试机制...")
        
        tasks = []
        for i in range(20):
            api_endpoint = f"https://unreliable-api.example.com/endpoint_{i}"
            tasks.append(client.submit_external_api_task(api_endpoint))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        print("等待任务执行和重试...")
        await asyncio.sleep(10)  # 等待更长时间让重试完成
        
        # 检查任务最终状态
        final_status_tasks = []
        for task_id in client.results["task_ids"]:
            final_status_tasks.append(client.get_task_status(task_id))
        
        final_results = await asyncio.gather(*final_status_tasks, return_exceptions=True)
        
        success_count = 0
        failed_count = 0
        for result in final_results:
            if isinstance(result, dict) and result.get("success"):
                status = result["response"]["data"]["status"]
                if status == "success":
                    success_count += 1
                elif status == "failed":
                    failed_count += 1
        
        print(f"重试测试结果: {success_count} 个成功, {failed_count} 个失败")
        client.print_results()
        
    finally:
        await client.close()


async def main():
    """主函数"""
    print("FastAPI DDD Framework 压力测试")
    print(f"确保服务正在运行在 {test_host}")
    print("="*60)
    
    # 检查服务是否运行
    client = StressTestClient()
    try:
        response = await client.client.get(f"{client.base_url}/api/v1/health/ping")
        if response.status_code != 200:
            print("❌ 服务未运行或不可访问")
            return
        print("✅ 服务运行正常，开始测试...")
    except Exception as e:
        print(f"❌ 无法连接到服务: {e}")
        return
    finally:
        await client.close()
    
    # 运行各种测试
    await run_basic_stress_test()
    await asyncio.sleep(2)
    
    await run_rate_limit_test()
    await asyncio.sleep(2)
    
    await run_retry_test()
    
    print("\n所有测试完成!")


if __name__ == "__main__":
    asyncio.run(main())