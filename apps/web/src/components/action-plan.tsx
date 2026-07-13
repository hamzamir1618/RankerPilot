"use client"

import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api-client"
import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export function ActionPlan({ auditId }: { auditId: string }) {
  const { data: findings, isLoading } = useQuery({
    queryKey: ["action-plan", auditId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/v1/audits/{audit_id}/action-plan", {
        params: { path: { audit_id: auditId } }
      })
      if (error) throw new Error("Failed to load action plan")
      return data
    }
  })

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-8 w-1/4" />
          <Skeleton className="h-4 w-1/3 mt-2" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (!findings || findings.length === 0) {
    return null
  }

  // Display top 5 items max for brevity
  const topPriorities = findings.slice(0, 5)

  return (
    <Card className="border-blue-200 shadow-sm">
      <CardHeader className="bg-blue-50/50 pb-4">
        <CardTitle className="text-xl text-blue-900">Top Priorities</CardTitle>
        <CardDescription>
          Based on severity, effort, and estimated traffic impact.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <div className="divide-y divide-slate-100">
          {topPriorities.map((finding, idx) => (
            <div key={finding.id} className="p-4 hover:bg-slate-50 transition-colors flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-700 font-bold text-sm">
                  {idx + 1}
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900">{finding.title}</h4>
                  <p className="text-sm text-slate-500 mt-1 capitalize">
                    {finding.category} • {finding.agent}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant={finding.severity === "critical" ? "destructive" : "secondary"}>
                  Severity: {finding.severity}
                </Badge>
                {finding.effort && (
                  <Badge variant="outline" className="bg-white">
                    Effort: {finding.effort.replace("_", " ")}
                  </Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
