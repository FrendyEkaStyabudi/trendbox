"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Switch } from "@/components/ui/switch"
import {
  UserPlus,
  Settings,
  UserCog,
  Users,
  Camera,
  Trash2,
  Edit,
  MoreHorizontal,
  Lock,
  AlertTriangle,
  FileText,
} from "lucide-react"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"

// Mock users data
const USERS_DATA = [
  {
    id: 1,
    name: "Alice Johnson",
    email: "alice@example.com",
    role: "Admin",
    status: "active",
    lastActive: "5 mins ago",
  },
  { id: 2, name: "Bob Smith", email: "bob@example.com", role: "Analyst", status: "active", lastActive: "2 hours ago" },
  {
    id: 3,
    name: "Carol Williams",
    email: "carol@example.com",
    role: "Viewer",
    status: "inactive",
    lastActive: "3 days ago",
  },
  {
    id: 4,
    name: "David Brown",
    email: "david@example.com",
    role: "Analyst",
    status: "active",
    lastActive: "1 hour ago",
  },
  { id: 5, name: "Eva Davis", email: "eva@example.com", role: "Viewer", status: "pending", lastActive: "Never" },
]

// Mock cameras data
const CAMERAS_DATA = [
  { id: 1, name: "Webcam C920", location: "Main Office", status: "active", type: "webcam" },
  { id: 2, name: "IP Camera", location: "Meeting Room", status: "active", type: "ip" },
  { id: 3, name: "Security Camera", location: "Lobby", status: "inactive", type: "security" },
  { id: 4, name: "USB Camera", location: "Dev Room", status: "active", type: "usb" },
]

// Role permissions
const ROLE_PERMISSIONS = {
  Admin: {
    "View Dashboard": true,
    "Export Data": true,
    "Manage Users": true,
    "Configure Cameras": true,
    "Access API": true,
    "Delete Data": true,
  },
  Analyst: {
    "View Dashboard": true,
    "Export Data": true,
    "Manage Users": false,
    "Configure Cameras": false,
    "Access API": true,
    "Delete Data": false,
  },
  Viewer: {
    "View Dashboard": true,
    "Export Data": false,
    "Manage Users": false,
    "Configure Cameras": false,
    "Access API": false,
    "Delete Data": false,
  },
}

export default function UserManagementPage() {
  const [users, setUsers] = useState(USERS_DATA)
  const [cameras, setCameras] = useState(CAMERAS_DATA)
  const [selectedRole, setSelectedRole] = useState("Admin")
  const [showAddUser, setShowAddUser] = useState(false)
  const [showAddCamera, setShowAddCamera] = useState(false)

  return (
    <div className="space-y-6">
      <Tabs defaultValue="users" className="space-y-4">
        <div className="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="users" className="flex items-center gap-2">
              <Users className="h-4 w-4" />
              Users
            </TabsTrigger>
            <TabsTrigger value="cameras" className="flex items-center gap-2">
              <Camera className="h-4 w-4" />
              Cameras
            </TabsTrigger>
            <TabsTrigger value="roles" className="flex items-center gap-2">
              <UserCog className="h-4 w-4" />
              Roles & Permissions
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="users" className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium">User Management</h3>
            <Button onClick={() => setShowAddUser(true)}>
              <UserPlus className="mr-2 h-4 w-4" />
              Add User
            </Button>
          </div>

          {showAddUser ? (
            <Card>
              <CardHeader>
                <CardTitle>Add New User</CardTitle>
                <CardDescription>Create a new user account and assign a role</CardDescription>
              </CardHeader>
              <CardContent>
                <form className="space-y-4">
                  <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="name">Full Name</Label>
                      <Input id="name" placeholder="John Doe" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">Email</Label>
                      <Input id="email" type="email" placeholder="john@example.com" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="password">Password</Label>
                      <Input id="password" type="password" placeholder="********" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="role">Role</Label>
                      <Select defaultValue="Viewer">
                        <SelectTrigger>
                          <SelectValue placeholder="Select role" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Admin">Admin</SelectItem>
                          <SelectItem value="Analyst">Analyst</SelectItem>
                          <SelectItem value="Viewer">Viewer</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="flex justify-end space-x-2">
                    <Button variant="outline" onClick={() => setShowAddUser(false)}>
                      Cancel
                    </Button>
                    <Button>Add User</Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last Active</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Avatar>
                              <AvatarImage src={`https://ui-avatars.com/api/?name=${user.name}`} alt={user.name} />
                              <AvatarFallback>{user.name.charAt(0)}</AvatarFallback>
                            </Avatar>
                            <div>
                              <div className="font-medium">{user.name}</div>
                              <div className="text-sm text-muted-foreground">{user.email}</div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={user.role === "Admin" ? "default" : "outline"}>{user.role}</Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div
                              className={`h-2 w-2 rounded-full ${
                                user.status === "active"
                                  ? "bg-green-500"
                                  : user.status === "inactive"
                                    ? "bg-gray-400"
                                    : "bg-yellow-500"
                              }`}
                            ></div>
                            <span className="capitalize">{user.status}</span>
                          </div>
                        </TableCell>
                        <TableCell>{user.lastActive}</TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon">
                                <MoreHorizontal className="h-4 w-4" />
                                <span className="sr-only">Actions</span>
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem>
                                <Edit className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem>
                                <Lock className="mr-2 h-4 w-4" />
                                Reset Password
                              </DropdownMenuItem>
                              <DropdownMenuItem>
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="cameras" className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium">Camera Management</h3>
            <Button onClick={() => setShowAddCamera(true)}>
              <Camera className="mr-2 h-4 w-4" />
              Add Camera
            </Button>
          </div>

          {showAddCamera ? (
            <Card>
              <CardHeader>
                <CardTitle>Add New Camera</CardTitle>
                <CardDescription>Configure a new camera for emotion recognition</CardDescription>
              </CardHeader>
              <CardContent>
                <form className="space-y-4">
                  <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="camera-name">Camera Name</Label>
                      <Input id="camera-name" placeholder="Meeting Room Camera" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="camera-location">Location</Label>
                      <Input id="camera-location" placeholder="Meeting Room" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="camera-type">Camera Type</Label>
                      <Select defaultValue="webcam">
                        <SelectTrigger>
                          <SelectValue placeholder="Select camera type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="webcam">Webcam</SelectItem>
                          <SelectItem value="ip">IP Camera</SelectItem>
                          <SelectItem value="usb">USB Camera</SelectItem>
                          <SelectItem value="security">Security Camera</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="camera-url">Stream URL/Device ID</Label>
                      <Input id="camera-url" placeholder="rtsp:// or device ID" />
                    </div>
                  </div>
                  <div className="flex justify-end space-x-2">
                    <Button variant="outline" onClick={() => setShowAddCamera(false)}>
                      Cancel
                    </Button>
                    <Button>Add Camera</Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Camera</TableHead>
                      <TableHead>Location</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {cameras.map((camera) => (
                      <TableRow key={camera.id}>
                        <TableCell>
                          <div className="font-medium">{camera.name}</div>
                        </TableCell>
                        <TableCell>{camera.location}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div
                              className={`h-2 w-2 rounded-full ${
                                camera.status === "active" ? "bg-green-500" : "bg-gray-400"
                              }`}
                            ></div>
                            <span className="capitalize">{camera.status}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {camera.type === "webcam"
                              ? "Webcam"
                              : camera.type === "ip"
                                ? "IP Camera"
                                : camera.type === "usb"
                                  ? "USB Camera"
                                  : "Security Camera"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon">
                                <MoreHorizontal className="h-4 w-4" />
                                <span className="sr-only">Actions</span>
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem>
                                <Settings className="mr-2 h-4 w-4" />
                                Configure
                              </DropdownMenuItem>
                              <DropdownMenuItem>
                                <AlertTriangle className="mr-2 h-4 w-4" />
                                Test Connection
                              </DropdownMenuItem>
                              <DropdownMenuItem>
                                <Trash2 className="mr-2 h-4 w-4" />
                                Remove
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="roles" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Role Management</CardTitle>
              <CardDescription>Configure permissions for each role</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div>
                  <Label>Select Role</Label>
                  <Select value={selectedRole} onValueChange={setSelectedRole}>
                    <SelectTrigger className="mt-2 w-[200px]">
                      <SelectValue placeholder="Select role" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Admin">Admin</SelectItem>
                      <SelectItem value="Analyst">Analyst</SelectItem>
                      <SelectItem value="Viewer">Viewer</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="font-medium">Permissions for {selectedRole} Role</h4>
                    <Button variant="outline" size="sm">
                      <FileText className="mr-2 h-4 w-4" />
                      Save Changes
                    </Button>
                  </div>

                  <div className="space-y-4">
                    {Object.entries(ROLE_PERMISSIONS[selectedRole as keyof typeof ROLE_PERMISSIONS]).map(
                      ([permission, isEnabled]) => (
                        <div key={permission} className="flex items-center justify-between py-2 border-b">
                          <div>
                            <div className="font-medium">{permission}</div>
                            <div className="text-sm text-muted-foreground">{getPermissionDescription(permission)}</div>
                          </div>
                          <Switch
                            checked={isEnabled}
                            disabled={selectedRole === "Admin" && permission === "View Dashboard"}
                          />
                        </div>
                      ),
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function getPermissionDescription(permission: string): string {
  switch (permission) {
    case "View Dashboard":
      return "Access to view emotion data dashboards and reports"
    case "Export Data":
      return "Ability to export emotion data in various formats"
    case "Manage Users":
      return "Create, edit, and delete user accounts"
    case "Configure Cameras":
      return "Add, edit, and manage camera configurations"
    case "Access API":
      return "Access to the emotion recognition API endpoints"
    case "Delete Data":
      return "Permanently delete emotion data records"
    default:
      return ""
  }
}

