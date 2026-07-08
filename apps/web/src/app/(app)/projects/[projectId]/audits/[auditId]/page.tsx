"use client"

import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"
import { apiClient } from "@/lib/api-client"
import { useAuditEvents } from "@/lib/sse"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { format } from "date-fns"
import { FindingsTable } from "@/components/findings-table"

export default function AuditPage() {
  const params = useParams()
  const auditId = params.auditId as string

  const { data: audit, isLoading: auditLoading } = useQuery({
    queryKey: ["audit", auditId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/v1/audits/{audit_id}", {
        params: { path: { audit_id: auditId } }
      })
      if (error) throw new Error("Failed to load audit")
      return data
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return (status === "queued" || status === "crawling" || status === "analyzing") ? 3000 : false
    }
  })

  const { status: sseStatus, progressMessage } = useAuditEvents(auditId)

  if (auditLoading) {
    return <div className="p-8 space-y-4">
      <Skeleton className="h-12 w-1/3" />
      <Skeleton className="h-4 w-1/4" />
      <Skeleton className="h-64 w-full" />
    </div>
  }

  if (!audit) {
    return <div className="p-8">Audit not found</div>
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-slate-50 p-6 rounded-lg border border-slate-200">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">Audit Report</h1>
            <Badge variant={audit.status === 'done' ? 'default' : audit.status === 'failed' ? 'destructive' : 'secondary'}>
              {audit.status}
            </Badge>
          </div>
          <p className="text-slate-500 mt-2">
            Started: {format(new Date(audit.started_at || new Date()), "PPpp")}
          </p>
          {audit.finished_at && (
            <p className="text-slate-500">
              Finished: {format(new Date(audit.finished_at), "PPpp")}
            </p>
          )}
        </div>
        
        <div className="flex flex-col items-end">
          <div className="text-5xl font-extrabold text-blue-600">
            {audit.score !== null ? audit.score.toFixed(0) : "--"}
            <span className="text-2xl text-slate-400">/100</span>
          </div>
          <p className="text-sm text-slate-500 font-medium">Overall Score</p>
        </div>
      </div>

      {/* Live SSE Progress */}
      {(audit.status === "queued" || audit.status === "crawling" || audit.status === "analyzing") && (
        <div className="bg-blue-50 text-blue-800 p-4 rounded-lg flex items-center gap-3 border border-blue-200">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          <p className="font-medium">{progressMessage || "Waiting for updates..."}</p>
          <span className="text-xs ml-auto text-blue-500">SSE: {sseStatus}</span>
        </div>
      )}

      {/* Findings Table */}
      <div>
        <h2 className="text-2xl font-bold mb-4">Findings</h2>
        <FindingsTable auditId={auditId} />
      </div>
    </div>
  )
}
