"use client"

import type React from "react"
import Image from "next/image"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { BarChart3, MessageSquare, BarChart2, Users, Settings, Activity, Home } from "lucide-react"
import { Button } from "@/components/ui/button"

interface DashboardLayoutProps {
  children: React.ReactNode
  currentPage: string
  onChangePage: (page: string) => void
}

export default function DashboardLayout({
  children,
  currentPage,
  onChangePage,
}: DashboardLayoutProps) {
  const menuItems = [
    { id: "dashboard", name: "Dashboard", icon: Home },
    { id: "forecasting", name: "Forecasting", icon: BarChart3 },
    { id: "realtime", name: "Real-time Tracking", icon: Activity },
    { id: "chat", name: "NLP Chat Assistant", icon: MessageSquare },
    { id: "reports", name: "Insights & Reports", icon: BarChart2 },
    // { id: "users", name: "User Management", icon: Users },
    // { id: "monitoring", name: "System Monitoring", icon: Settings },
  ]

  return (
    <div className="flex min-h-screen w-full overflow-x-hidden bg-background">
      <Sidebar>
        <SidebarHeader className="flex-col space-y-2 px-4 py-2">
          <div className="flex items-center space-x-3">
            <Image
              src="/logo.jpg"
              alt="Emotion Trendbox Logo"
              width={36}
              height={36}
            />
            <span className="font-bold text-xl">Trendbox</span>
          </div>
          <div className="h-[1px] bg-border w-full" />
        </SidebarHeader>
        <SidebarContent>
          {/* ... menu items ... */}
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {menuItems.map((item) => (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton onClick={() => onChangePage(item.id)} isActive={currentPage === item.id}>
                      <item.icon className="h-5 w-5" />
                      <span>{item.name}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

      </Sidebar>

      <main className="flex min-h-screen min-w-0 flex-1 flex-col overflow-hidden">
        {/* ... sisa kode tidak berubah ... */}
        <div className="flex min-w-0 items-center justify-between gap-3 border-b p-3 sm:p-4">
          <div className="flex min-w-0 items-center">
            <SidebarTrigger className="md:hidden mr-2" />
            <h1 className="truncate text-lg font-semibold sm:text-xl">
              {menuItems.find((item) => item.id === currentPage)?.name || "Dashboard"}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <Settings className="mr-2 h-4 w-4" />
              Settings
            </Button>
          </div>
        </div>

        <div className="min-w-0 flex-1 overflow-auto p-3 sm:p-4 md:p-6">{children}</div>
      </main>
    </div>
  )
}
