"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { apiDownload, apiGet, apiPost, saveFile, type QueryParams } from "@/lib/api/client";
import { STALE_TIME_CATALOG_MS, STATUS_POLL_MS } from "@/lib/constants";
import type {
  CompareRequest,
  CompareResponse,
  DictionaryResponse,
  EarthApplicationsResponse,
  EarthSector,
  ExportRequest,
  ExtractRequest,
  FacetsResponse,
  GapsResponse,
  InvestigationDetail,
  InvestigationListParams,
  InvestigationSummary,
  LineageGraph,
  Page,
  PresetsResponse,
  ProjectOut,
  PublicationOut,
  RankRequest,
  RankResponse,
  RubricResponse,
  RunItem,
  SafetyTechResponse,
  ScenarioRequest,
  ScenarioResponse,
  StatsResponse,
  StatusResponse,
  Table,
  VariablesResponse,
} from "@/lib/api/types";

const catalog = { staleTime: STALE_TIME_CATALOG_MS } as const;
const encode = encodeURIComponent;

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => apiGet<{ status: string }>("/health"),
    ...catalog,
  });
}

export function useReady() {
  return useQuery({
    queryKey: ["ready"],
    queryFn: () => apiGet<{ status: string }>("/ready"),
    ...catalog,
  });
}

export function useStats() {
  return useQuery({
    queryKey: ["meta", "stats"],
    queryFn: () => apiGet<StatsResponse>("/meta/stats"),
    ...catalog,
  });
}

export function useStatus() {
  return useQuery({
    queryKey: ["meta", "status"],
    queryFn: () => apiGet<StatusResponse>("/meta/status"),
    staleTime: 0,
    refetchInterval: STATUS_POLL_MS,
  });
}

export function useRubric() {
  return useQuery({
    queryKey: ["meta", "rubric"],
    queryFn: () => apiGet<RubricResponse>("/meta/rubric"),
    ...catalog,
  });
}

export function usePresets() {
  return useQuery({
    queryKey: ["meta", "presets"],
    queryFn: () => apiGet<PresetsResponse>("/meta/presets"),
    ...catalog,
  });
}

export function useInvestigations(params: InvestigationListParams) {
  return useQuery({
    queryKey: ["investigations", params],
    queryFn: () => apiGet<Page<InvestigationSummary>>("/investigations", params as QueryParams),
    placeholderData: keepPreviousData,
    ...catalog,
  });
}

export function useInvestigation(id: string) {
  return useQuery({
    queryKey: ["investigation", id],
    queryFn: () => apiGet<InvestigationDetail>(`/investigations/${encode(id)}`),
    enabled: id !== "",
    ...catalog,
  });
}

export function useRuns(id: string, page = 1, pageSize = 100) {
  return useQuery({
    queryKey: ["investigation", id, "runs", page, pageSize],
    queryFn: () =>
      apiGet<Page<RunItem>>(`/investigations/${encode(id)}/runs`, { page, page_size: pageSize }),
    ...catalog,
  });
}

export function useVariables(id: string) {
  return useQuery({
    queryKey: ["investigation", id, "variables"],
    queryFn: () => apiGet<VariablesResponse>(`/investigations/${encode(id)}/variables`),
    ...catalog,
  });
}

export function usePublications(id: string) {
  return useQuery({
    queryKey: ["investigation", id, "publications"],
    queryFn: () => apiGet<PublicationOut[]>(`/investigations/${encode(id)}/publications`),
    ...catalog,
  });
}

export function useFacets() {
  return useQuery({
    queryKey: ["facets"],
    queryFn: () => apiGet<FacetsResponse>("/facets"),
    ...catalog,
  });
}

export function useHardware() {
  return useQuery({
    queryKey: ["hardware"],
    queryFn: () => apiGet<LineageGraph>("/hardware"),
    ...catalog,
  });
}

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: () => apiGet<ProjectOut[]>("/projects"),
    ...catalog,
  });
}

export function useRank(request: RankRequest) {
  return useQuery({
    queryKey: ["rank", request],
    queryFn: () => apiPost<RankResponse>("/rank", request),
    placeholderData: keepPreviousData,
    ...catalog,
  });
}

export function useCompare(request: CompareRequest, enabled: boolean) {
  return useQuery({
    queryKey: ["compare", request],
    queryFn: () => apiPost<CompareResponse>("/compare", request),
    enabled,
    placeholderData: keepPreviousData,
    ...catalog,
  });
}

export function useScenario(request: ScenarioRequest, enabled: boolean) {
  return useQuery({
    queryKey: ["scenario", request],
    queryFn: () => apiPost<ScenarioResponse>("/scenario", request),
    enabled,
    placeholderData: keepPreviousData,
    ...catalog,
  });
}

export function useExtractPreview(request: ExtractRequest, enabled = true) {
  return useQuery({
    queryKey: ["extract", "preview", request],
    queryFn: () => apiPost<Table>("/extract/preview", request),
    enabled,
    placeholderData: keepPreviousData,
    ...catalog,
  });
}

export function useExtractExport() {
  return useMutation({
    mutationFn: async (request: ExportRequest) =>
      saveFile(await apiDownload("/extract/export", request)),
  });
}

export function useDictionary() {
  return useQuery({
    queryKey: ["extract", "dictionary"],
    queryFn: () => apiGet<DictionaryResponse>("/extract/dictionary"),
    ...catalog,
  });
}

export function useSafetyTech() {
  return useQuery({
    queryKey: ["insights", "safety-tech"],
    queryFn: () => apiGet<SafetyTechResponse>("/insights/safety-tech"),
    ...catalog,
  });
}

export function useGaps() {
  return useQuery({
    queryKey: ["insights", "gaps"],
    queryFn: () => apiGet<GapsResponse>("/insights/gaps"),
    ...catalog,
  });
}

export function useEarthApplications(sector: EarthSector | undefined) {
  return useQuery({
    queryKey: ["earth-applications", sector ?? "all"],
    queryFn: () => apiGet<EarthApplicationsResponse>("/earth-applications", { sector }),
    ...catalog,
  });
}
