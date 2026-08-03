"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import {
  AlertTriangle,
  Check,
  RefreshCw,
  XCircle,
  Cpu,
  Database,
  HardDrive,
  MemoryStick,
  Activity,
  Search,
  Download,
  FileText,
  Layers,
  Bell,
} from "lucide-react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Progress } from "@/components/ui/progress"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import RealtimeEmotionChart from "../charts/realtime-emotion-chart"

// Mock service status
const SERVICES = [
  { id: 1, name: "Face Detection Service", status: "online", uptime: "99.8%", lastIssue: "None" },
  { id: 2, name: "Emotion Recognition ML Model", status: "online", uptime: "99.5%", lastIssue: "2 days ago" },
  { id: 3, name: "Video Processing Pipeline", status: "online", uptime: "98.7%", lastIssue: "12 hours ago" },
  { id: 4, name: "Database Server", status: "online", uptime: "99.9%", lastIssue: "None" },
  { id: 5, name: "API Gateway", status: "online", uptime: "99.2%", lastIssue: "1 day ago" },
]

// Mock system logs
const SYSTEM_LOGS = [
  { id: 1, level: "info", message: "Face detection service started successfully", timestamp: "10:24:32" },
  { id: 2, level: "warn", message: "High CPU usage detected (85%)", timestamp: "10:15:21" },
  { id: 3, level: "error", message: "Failed to connect to camera #3", timestamp: "09:45:16" },
  { id: 4, level: "info", message: "Database backup completed", timestamp: "09:30:00" },
  { id: 5, level: "info", message: "New user registered: john@example.com", timestamp: "09:22:45" },
  { id: 6, level: "warn", message: "Memory usage above threshold (78%)", timestamp: "09:10:12" },
  { id: 7, level: "error", message: "Emotion recognition model timeout", timestamp: "08:55:33" },
  { id: 8, level: "info", message: "System startup complete", timestamp: "08:30:00" },
]

export default function SystemMonitoringPage() {
  const [services, setServices] = useState(SERVICES)
  const [logs, setLogs] = useState(SYSTEM_LOGS)
  const [cpuUsage, setCpuUsage] = useState(45)
  const [memoryUsage, setMemoryUsage] = useState(62)
  const [diskUsage, setDiskUsage] = useState(38)
  const [networkLatency, setNetworkLatency] = useState(120)

  // Simulate changing resource usage
  useEffect(() => {
    const timer = setInterval(() => {
      setCpuUsage(Math.min(95, Math.max(30, cpuUsage + (Math.random() * 10 - 5))))
      setMemoryUsage(Math.min(95, Math.max(30, memoryUsage + (Math.random() * 8 - 4))))
      setDiskUsage(Math.min(95, Math.max(30, diskUsage + (Math.random() * 2 - 1))))
      setNetworkLatency(Math.min(500, Math.max(80, networkLatency + (Math.random() * 40 - 20))))
    }, 5000)

    return () => clearInterval(timer)
  }, [cpuUsage, memoryUsage, diskUsage, networkLatency])

  const getLevelBadge = (level: string) => {
    switch (level) {
      case "info":
        return <Badge className="bg-blue-500">Info</Badge>
      case "warn":
        return <Badge className="bg-yellow-500">Warning</Badge>
      case "error":
        return <Badge className="bg-red-500">Error</Badge>
      default:
        return <Badge>Unknown</Badge>
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "online":
        return <Check className="h-4 w-4 text-green-500" />
      case "offline":
        return <XCircle className="h-4 w-4 text-red-500" />
      case "degraded":
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />
      default:
        return null
    }
  }

  const getResourceStatus = (usage: number) => {
    if (usage < 50) return "text-green-500"
    if (usage < 80) return "text-yellow-500"
    return "text-red-500"
  }

  return (
    <div className="space-y-6">
      {/* System Status Summary */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
            <Cpu className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{cpuUsage.toFixed(1)}%</div>
            <div className="mt-2 space-y-1">
              <Progress value={cpuUsage} className="h-2" />
              <p className={`text-xs ${getResourceStatus(cpuUsage)}`}>
                {cpuUsage < 50 ? "Normal" : cpuUsage < 80 ? "Moderate" : "High"}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Memory Usage</CardTitle>
            <MemoryStick className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{memoryUsage.toFixed(1)}%</div>
            <div className="mt-2 space-y-1">
              <Progress value={memoryUsage} className="h-2" />
              <p className={`text-xs ${getResourceStatus(memoryUsage)}`}>
                {memoryUsage < 50 ? "Normal" : memoryUsage < 80 ? "Moderate" : "High"}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Disk Usage</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{diskUsage.toFixed(1)}%</div>
            <div className="mt-2 space-y-1">
              <Progress value={diskUsage} className="h-2" />
              <p className={`text-xs ${getResourceStatus(diskUsage)}`}>
                {diskUsage < 50 ? "Normal" : diskUsage < 80 ? "Moderate" : "High"}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Network Latency</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{networkLatency.toFixed(0)}ms</div>
            <div className="mt-2 space-y-1">
              <Progress value={Math.min(100, (networkLatency / 500) * 100)} className="h-2" />
              <p
                className={`text-xs ${
                  networkLatency < 150 ? "text-green-500" : networkLatency < 300 ? "text-yellow-500" : "text-red-500"
                }`}
              >
                {networkLatency < 150 ? "Low" : networkLatency < 300 ? "Moderate" : "High"}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">System Monitoring</h3>
        <Button variant="outline" size="sm">
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      <Tabs defaultValue="services" className="space-y-4">
        <TabsList>
          <TabsTrigger value="services" className="flex items-center gap-2">
            <Database className="h-4 w-4" />
            Services
          </TabsTrigger>
          <TabsTrigger value="logs" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Logs
          </TabsTrigger>
          <TabsTrigger value="performance" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Performance
          </TabsTrigger>
        </TabsList>

        <TabsContent value="services" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Service Status</CardTitle>
              <CardDescription>Current status of system services</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Service</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Uptime</TableHead>
                    <TableHead>Last Issue</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {services.map((service) => (
                    <TableRow key={service.id}>
                      <TableCell className="font-medium">{service.name}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(service.status)}
                          <span className="capitalize">{service.status}</span>
                        </div>
                      </TableCell>
                      <TableCell>{service.uptime}</TableCell>
                      <TableCell>{service.lastIssue}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Notification Settings</CardTitle>
              <CardDescription>Configure alerts for system events</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between py-2 border-b">
                  <div>
                    <Label>Service Downtime Alerts</Label>
                    <p className="text-sm text-muted-foreground">Receive alerts when services go offline</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                <div className="flex items-center justify-between py-2 border-b">
                  <div>
                    <Label>High Resource Usage Alerts</Label>
                    <p className="text-sm text-muted-foreground">Notified when CPU/Memory exceeds 80%</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                <div className="flex items-center justify-between py-2 border-b">
                  <div>
                    <Label>Error Rate Threshold</Label>
                    <p className="text-sm text-muted-foreground">Alert when error rate exceeds threshold</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                <div className="flex items-center justify-between py-2 border-b">
                  <div>
                    <Label>Daily Summary Report</Label>
                    <p className="text-sm text-muted-foreground">Receive daily summary of system health</p>
                  </div>
                  <Switch />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="logs" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>System Logs</CardTitle>
                <CardDescription>Real-time log entries from system components</CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Input placeholder="Search logs..." className="w-64" />
                <Button variant="outline" size="icon">
                  <Search className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="icon">
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border h-[400px] overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[100px]">Level</TableHead>
                      <TableHead>Message</TableHead>
                      <TableHead className="w-[100px]">Time</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {logs.map((log) => (
                      <TableRow key={log.id}>
                        <TableCell>{getLevelBadge(log.level)}</TableCell>
                        <TableCell className="font-mono text-xs">{log.message}</TableCell>
                        <TableCell>{log.timestamp}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="flex items-center justify-between mt-4">
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm">
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Refresh
                  </Button>
                  <Button variant="outline" size="sm">
                    <Bell className="mr-2 h-4 w-4" />
                    Clear Notifications
                  </Button>
                </div>
                <Button variant="outline" size="sm">
                  View More Logs
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="performance" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>System Performance</CardTitle>
              <CardDescription>Performance metrics over time</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[400px]">
                <RealtimeEmotionChart isPerformance />
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Error Rate</CardTitle>
                <CardDescription>System errors over time</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xl font-bold">1.2%</div>
                      <div className="text-xs text-muted-foreground">Current error rate</div>
                    </div>
                    <Badge className="bg-green-500">Healthy</Badge>
                  </div>
                  <div className="h-[200px] flex items-end gap-2">
                    {Array.from({ length: 24 }).map((_, i) => {
                      const height = Math.random() * 100
                      return (
                        <div
                          key={i}
                          className={`flex-1 ${height > 80 ? "bg-red-500" : height > 40 ? "bg-yellow-500" : "bg-green-500"}`}
                          style={{ height: `${Math.max(4, height)}%` }}
                        ></div>
                      )
                    })}
                  </div>
                  <div className="text-xs text-muted-foreground text-center">Last 24 hours</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Processing Speed</CardTitle>
                <CardDescription>Average frame processing time</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xl font-bold">124ms</div>
                      <div className="text-xs text-muted-foreground">Average processing time</div>
                    </div>
                    <Badge className="bg-green-500">Optimal</Badge>
                  </div>
                  <div className="h-[200px] bg-muted rounded-md p-2 flex items-end">
                    <div className="w-full relative h-full">
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Layers className="h-16 w-16 text-muted-foreground opacity-20" />
                      </div>
                      {/* Mock performance graph */}
                      <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                        <path
                          d="M0,50 C10,40 20,60 30,50 C40,40 50,70 60,50 C70,30 80,50 90,40 L90,100 L0,100 Z"
                          fill="rgba(59, 130, 246, 0.2)"
                          stroke="rgb(59, 130, 246)"
                          strokeWidth="1"
                        />
                      </svg>
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground text-center">Performance is within optimal range</div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

