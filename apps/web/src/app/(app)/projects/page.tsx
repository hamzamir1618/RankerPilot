"use client"

import { apiClient } from "@/lib/api-client"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useRouter } from "next/navigation"

export default function ProjectsPage() {
  // Hardcoded project ID from seed script for demonstration
  const projectId = "8a527bfa-7925-4c93-807c-4ea672d415ef"
  const auditId = "bd5182c1-b64f-4ba7-9cc8-469e94855c99"
  const [url, setUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const handleStartAudit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url) return
    
    setLoading(true)
    try {
      const { data, error } = await apiClient.POST("/v1/projects/{project_id}/audits", {
        params: { path: { project_id: projectId } },
        body: { url, mode: "single_page", page_limit: 1 } as never
      })
      
      if (data && (data as Record<string, unknown>).audit_id) {
        router.push(`/projects/${projectId}/audits/${String((data as Record<string, unknown>).audit_id)}`)
      } else if (error) {
        alert("Failed to start audit: " + JSON.stringify(error))
      }
    } catch {
      alert("Error starting audit")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container mx-auto py-12">
      <h1 className="text-3xl font-bold mb-8">Your Projects</h1>
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Example.com</CardTitle>
            <CardDescription>example.com</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Link href={`/projects/${projectId}/audits/${auditId}`}>
              <Button variant="outline" className="w-full">View Latest Seeded Audit</Button>
            </Link>
            
            <div className="pt-4 border-t">
              <h3 className="font-semibold mb-2">Run New Audit</h3>
              <form onSubmit={handleStartAudit} className="space-y-3">
                <div>
                  <Label htmlFor="url">Page URL</Label>
                  <Input 
                    id="url" 
                    type="url" 
                    placeholder="https://example.com/pricing" 
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    required
                  />
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? "Starting..." : "Start Audit"}
                </Button>
              </form>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
