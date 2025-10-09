"""
M6 Monitoring - FastAPI监控服务
提供HTTP接口：健康检查、指标导出、业务统计、告警查询
"""

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from pathlib import Path

from src.monitoring.metrics import metrics_collector
from src.monitoring.stats_aggregator import stats_aggregator
from src.monitoring.alert_engine import alert_engine
from src.core.logging import get_logger

logger = get_logger(__name__)

# FastAPI应用
app = FastAPI(
    title="Reddit Comment System - Monitoring Dashboard",
    description="M6 监控指挥中心 - 实时指标 + 告警 + 降频控制",
    version="0.6.0"
)

# 挂载静态文件目录（前端资源）
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """监控首页（重定向到监控面板）"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Monitoring Dashboard</title>
        <meta http-equiv="refresh" content="0; url=/dashboard">
    </head>
    <body>
        <p>Redirecting to <a href="/dashboard">Monitoring Dashboard</a>...</p>
    </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """
    系统健康检查

    Returns:
        健康状态和摘要
    """
    try:
        health_summary = stats_aggregator.get_health_summary()

        return {
            "status": health_summary['status'],
            "score": health_summary['score'],
            "details": {
                "account_availability": health_summary['account_availability'],
                "publish_success_rate": health_summary['publish_success_rate'],
                "delete_rate": health_summary['delete_rate']
            },
            "timestamp": health_summary['timestamp']
        }

    except Exception as e:
        logger.error("健康检查失败", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/metrics")
async def metrics():
    """
    Prometheus指标导出

    Returns:
        Prometheus文本格式指标
    """
    try:
        metrics_data = generate_latest()
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )

    except Exception as e:
        logger.error("指标导出失败", error=str(e))
        return Response(
            content=f"# Error: {str(e)}",
            media_type="text/plain",
            status_code=500
        )


@app.get("/stats")
async def stats():
    """
    业务统计数据

    Returns:
        完整的业务统计JSON
    """
    try:
        full_stats = stats_aggregator.get_full_stats()
        return full_stats

    except Exception as e:
        logger.error("统计数据获取失败", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/stats/discovery")
async def stats_discovery():
    """M2发现模块统计"""
    return stats_aggregator.get_discovery_stats()


@app.get("/stats/screening")
async def stats_screening():
    """M3筛选模块统计"""
    return stats_aggregator.get_screening_stats()


@app.get("/stats/generation")
async def stats_generation():
    """M4生成模块统计"""
    return stats_aggregator.get_generation_stats()


@app.get("/stats/publishing")
async def stats_publishing():
    """M5发布模块统计"""
    return stats_aggregator.get_publishing_stats()


@app.get("/stats/accounts")
async def stats_accounts():
    """账号池统计"""
    return stats_aggregator.get_account_pool_stats()


@app.get("/stats/performance")
async def stats_performance():
    """性能统计"""
    return stats_aggregator.get_performance_stats()


@app.get("/alerts")
async def alerts():
    """
    告警查询

    Returns:
        活跃告警列表和摘要
    """
    try:
        # 先执行一次告警检查
        alert_engine.check_all_rules()

        # 返回告警摘要
        alert_summary = alert_engine.get_alert_summary()

        return alert_summary

    except Exception as e:
        logger.error("告警查询失败", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.post("/alerts/check")
async def check_alerts():
    """
    手动触发告警检查

    Returns:
        本次检查触发的告警
    """
    try:
        triggered_alerts = alert_engine.check_all_rules()

        return {
            "triggered_count": len(triggered_alerts),
            "alerts": [alert.to_dict() for alert in triggered_alerts]
        }

    except Exception as e:
        logger.error("告警检查失败", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.delete("/alerts/{rule_name}")
async def clear_alert(rule_name: str):
    """
    清除指定告警

    Args:
        rule_name: 告警规则名称
    """
    try:
        alert_engine.clear_alert(rule_name)

        return {
            "status": "success",
            "message": f"告警已清除: {rule_name}"
        }

    except Exception as e:
        logger.error(f"清除告警失败: {rule_name}", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """
    监控面板HTML页面

    Returns:
        监控面板HTML
    """
    # 尝试从templates目录加载
    template_path = Path(__file__).parent / "templates" / "dashboard.html"

    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())

    # 如果模板不存在，返回简单的监控页面
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>M6 Monitoring Dashboard</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 20px; }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .header h1 { font-size: 24px; margin-bottom: 5px; }
            .header p { font-size: 14px; opacity: 0.8; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .card h2 { font-size: 18px; margin-bottom: 15px; color: #2c3e50; }
            .metric { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }
            .metric:last-child { border-bottom: none; }
            .metric-label { color: #666; font-size: 14px; }
            .metric-value { font-weight: bold; font-size: 16px; color: #2c3e50; }
            .status-healthy { color: #27ae60; }
            .status-warning { color: #f39c12; }
            .status-critical { color: #e74c3c; }
            .alert-box { background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin-top: 10px; border-radius: 4px; }
            .loading { text-align: center; padding: 40px; color: #999; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎯 M6 Monitoring Dashboard</h1>
            <p>Reddit Comment System - 实时监控指挥中心</p>
        </div>

        <div id="loading" class="loading">正在加载监控数据...</div>
        <div id="dashboard" style="display: none;">
            <div class="grid">
                <div class="card">
                    <h2>🏥 系统健康</h2>
                    <div id="health-metrics"></div>
                </div>

                <div class="card">
                    <h2>👥 账号池状态</h2>
                    <div id="account-metrics"></div>
                </div>

                <div class="card">
                    <h2>📊 M2 发现模块</h2>
                    <div id="discovery-metrics"></div>
                </div>

                <div class="card">
                    <h2>🔍 M3 筛选模块</h2>
                    <div id="screening-metrics"></div>
                </div>

                <div class="card">
                    <h2>✍️ M4 生成模块</h2>
                    <div id="generation-metrics"></div>
                </div>

                <div class="card">
                    <h2>🚀 M5 发布模块</h2>
                    <div id="publishing-metrics"></div>
                </div>
            </div>

            <div class="card" style="margin-top: 20px;">
                <h2>⚠️ 活跃告警</h2>
                <div id="alerts-container"></div>
            </div>
        </div>

        <script>
            async function loadStats() {
                try {
                    const response = await fetch('/stats');
                    const data = await response.json();

                    // 系统健康
                    const health = data.health;
                    const healthClass = health.status === 'healthy' ? 'status-healthy' :
                                       health.status === 'degraded' ? 'status-warning' : 'status-critical';
                    document.getElementById('health-metrics').innerHTML = `
                        <div class="metric">
                            <span class="metric-label">状态</span>
                            <span class="metric-value ${healthClass}">${health.status.toUpperCase()}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">健康评分</span>
                            <span class="metric-value">${health.score.toFixed(1)}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">发布成功率</span>
                            <span class="metric-value">${(health.publish_success_rate * 100).toFixed(2)}%</span>
                        </div>
                    `;

                    // 账号池
                    const accounts = data.accounts;
                    document.getElementById('account-metrics').innerHTML = `
                        <div class="metric">
                            <span class="metric-label">总账号数</span>
                            <span class="metric-value">${accounts.total_accounts}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">可用账号</span>
                            <span class="metric-value">${accounts.available_accounts}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">可用性</span>
                            <span class="metric-value">${(accounts.availability_rate * 100).toFixed(2)}%</span>
                        </div>
                    `;

                    // M2 发现
                    const discovery = data.discovery;
                    document.getElementById('discovery-metrics').innerHTML = `
                        <div class="metric">
                            <span class="metric-label">已发现帖子</span>
                            <span class="metric-value">${discovery.total_discovered}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">去重后</span>
                            <span class="metric-value">${discovery.unique_posts}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">重复率</span>
                            <span class="metric-value">${(discovery.duplicate_rate * 100).toFixed(2)}%</span>
                        </div>
                    `;

                    // M3 筛选
                    const screening = data.screening;
                    document.getElementById('screening-metrics').innerHTML = `
                        <div class="metric">
                            <span class="metric-label">已筛选</span>
                            <span class="metric-value">${screening.total_screened}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">通过</span>
                            <span class="metric-value">${screening.approved}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">通过率</span>
                            <span class="metric-value">${(screening.approval_rate * 100).toFixed(2)}%</span>
                        </div>
                    `;

                    // M4 生成
                    const generation = data.generation;
                    document.getElementById('generation-metrics').innerHTML = `
                        <div class="metric">
                            <span class="metric-label">已生成</span>
                            <span class="metric-value">${generation.total_generated}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">失败</span>
                            <span class="metric-value">${generation.total_failures}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">成功率</span>
                            <span class="metric-value">${(generation.success_rate * 100).toFixed(2)}%</span>
                        </div>
                    `;

                    // M5 发布
                    const publishing = data.publishing;
                    document.getElementById('publishing-metrics').innerHTML = `
                        <div class="metric">
                            <span class="metric-label">已发布</span>
                            <span class="metric-value">${publishing.total_published}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">成功</span>
                            <span class="metric-value">${publishing.success}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">成功率</span>
                            <span class="metric-value">${(publishing.success_rate * 100).toFixed(2)}%</span>
                        </div>
                    `;

                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('dashboard').style.display = 'block';

                } catch (error) {
                    document.getElementById('loading').innerHTML = `<p style="color: #e74c3c;">加载失败: ${error.message}</p>`;
                }
            }

            async function loadAlerts() {
                try {
                    const response = await fetch('/alerts');
                    const data = await response.json();

                    const container = document.getElementById('alerts-container');

                    if (data.total_active_alerts === 0) {
                        container.innerHTML = '<p style="color: #27ae60;">✅ 暂无活跃告警</p>';
                    } else {
                        container.innerHTML = data.alerts.map(alert => `
                            <div class="alert-box">
                                <strong>${alert.severity.toUpperCase()}</strong>: ${alert.message}
                                <br><small>${alert.timestamp}</small>
                            </div>
                        `).join('');
                    }
                } catch (error) {
                    console.error('加载告警失败:', error);
                }
            }

            // 初始加载
            loadStats();
            loadAlerts();

            // 每30秒刷新
            setInterval(() => {
                loadStats();
                loadAlerts();
            }, 30000);
        </script>
    </body>
    </html>
    """)


# 启动信息
@app.on_event("startup")
async def startup_event():
    logger.info("M6监控服务启动", version="0.6.0", port=8086)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("M6监控服务关闭")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8086,
        log_level="info"
    )
