// page.tsx (atau file root Anda yang berisi komponen Home)

"use client"

import { useEffect, useState } from "react"
import { SidebarProvider } from "@/components/ui/sidebar"
import DashboardLayout from "@/components/dashboard-layout"
import EmotionDashboard from "@/components/dashboard/emotion-dashboard"
import ForecastingPage from "@/components/dashboard/forecasting-page"
import RealtimeTrackingPage from "@/components/dashboard/realtime-tracking-page"
import NlpChatPage from "@/components/dashboard/nlp-chat-page"
import ReportsPage from "@/components/dashboard/reports-page"
import UserManagementPage from "@/components/dashboard/user-management-page"
import SystemMonitoringPage from "@/components/dashboard/system-monitoring-page"

export default function Home() {
  const [currentUser, setCurrentUser] = useState<any>(null)
  const [currentPage, setCurrentPage] = useState("dashboard")

  useEffect(() => {
    const user = localStorage.getItem("emotionDashboardUser")
    if (user) {
      setCurrentUser(JSON.parse(user))
    }
  }, [])

  const renderPage = () => {
    switch (currentPage) {
      case "dashboard":
        return <EmotionDashboard />
      case "forecasting":
        return <ForecastingPage />
      case "realtime":
        return <RealtimeTrackingPage />

      case "chat":
        return <NlpChatPage currentUser={currentUser} />

      case "reports":
        return <ReportsPage />
      case "users":
        return <UserManagementPage />
      case "monitoring":
        return <SystemMonitoringPage />
      default:
        return <EmotionDashboard />
    }
  }

  return (
    <SidebarProvider>
      <DashboardLayout
        currentPage={currentPage}
        onChangePage={setCurrentPage}
      >
        {renderPage()}
      </DashboardLayout>
    </SidebarProvider>
  )
}
