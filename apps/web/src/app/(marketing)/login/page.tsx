"use client"

import { useState } from "react"
import { useAuth } from "@/components/auth-context"
import { apiClient } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { useRouter } from "next/navigation"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const { setToken } = useAuth()
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    
    try {
      const { data, error } = await apiClient.POST("/v1/auth/login", {
        body: { email, password }
      })
      
      if (error) {
        const detail = (error as Record<string, unknown>).detail;
        if (typeof detail === 'string') setError(detail);
        else if (Array.isArray(detail)) setError(detail[0].msg);
        else setError("Login failed");
        return
      }
      
      if (data && data.access_token) {
        setToken(data.access_token)
        // Hardcoded to project ID for the demo
        router.push("/projects")
      }
    } catch (err: unknown) {
      setError((err as Error).message || "An error occurred")
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-50">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl text-center">Login to RankerPilot</CardTitle>
          <CardDescription className="text-center">Enter your email and password to login</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input 
                id="email" 
                type="email" 
                placeholder="demo@rankerpilot.com" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input 
                id="password" 
                type="password" 
                placeholder="demo_password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-sm text-red-500">{error}</p>}
            <Button type="submit" className="w-full">Sign In</Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center">
          <p className="text-sm text-slate-500">
            Don&apos;t have an account? <a href="/register" className="text-blue-500 hover:underline">Register</a>
          </p>
        </CardFooter>
      </Card>
    </div>
  )
}
