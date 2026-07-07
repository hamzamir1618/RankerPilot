"use client"

import React, { createContext, useContext, useState, useEffect } from "react"
import { getAccessToken, setAccessToken as setApiAccessToken, apiClient } from "@/lib/api-client"
import { useRouter, usePathname } from "next/navigation"

interface AuthContextType {
  token: string | null
  setToken: (token: string | null) => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(getAccessToken())
  const router = useRouter()
  const pathname = usePathname()

  const setToken = (newToken: string | null) => {
    setTokenState(newToken)
    setApiAccessToken(newToken)
  }

  const logout = async () => {
    try {
      await apiClient.POST("/v1/auth/logout")
    } catch (e) {
      console.error("Logout failed", e)
    } finally {
      setToken(null)
      router.push("/login")
    }
  }

  // Effect to protect routes
  useEffect(() => {
    // If not on marketing pages and no token, redirect to login
    // In a real app we'd wait for silent refresh to complete on init if token is null
    if (!token && !pathname.startsWith("/login") && !pathname.startsWith("/register")) {
      router.push("/login")
    }
  }, [token, pathname, router])

  return (
    <AuthContext.Provider value={{ token, setToken, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
