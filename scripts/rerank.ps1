# tei-rerank 重排序模型服务按需启停
# 用法: .\scripts\rerank.ps1 start | stop | status
param(
  [Parameter(Mandatory = $false)]
  [ValidateSet('start', 'stop', 'status')]
  [string]$Action = 'status'
)

$name = 'tei-rerank'

switch ($Action) {
  'start' {
    Write-Host "启动 $name（约需 10-30 秒模型加载，占用约 5.6GB 内存）..." -ForegroundColor Cyan
    docker start $name
    Write-Host "已启动: http://localhost:8080 （不再开机自动运行，用完请 stop）" -ForegroundColor Green
  }
  'stop' {
    Write-Host "停止 $name（释放约 5.6GB 内存）..." -ForegroundColor Cyan
    docker stop $name
    Write-Host "已停止。" -ForegroundColor Green
  }
  'status' {
    docker ps -a --filter "name=$name" --format '{{.Names}}: {{.Status}} (restart={{.Label "restart"}})'
    docker inspect $name --format '重启策略: {{.HostConfig.RestartPolicy.Name}}'
  }
}
