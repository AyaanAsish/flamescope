{{/* Chart name. */}}
{{- define "flamescope.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Labels shared by every object. */}}
{{- define "flamescope.labels" -}}
app.kubernetes.io/name: {{ include "flamescope.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
{{- end -}}

{{/* Selector labels for one component; call with (dict "root" $ "component" "api"). */}}
{{- define "flamescope.selectorLabels" -}}
app.kubernetes.io/name: {{ include "flamescope.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Image reference; call with (dict "root" $ "image" .Values.image.api). */}}
{{- define "flamescope.image" -}}
{{- printf "%s%s:%s" .root.Values.image.registry .image.repository .image.tag -}}
{{- end -}}

{{/* DATABASE_URL, derived from the postgres values unless given explicitly. */}}
{{- define "flamescope.databaseUrl" -}}
{{- if .Values.databaseUrl -}}
{{- .Values.databaseUrl -}}
{{- else -}}
{{- with .Values.postgres -}}
{{- printf "postgresql+psycopg://%s:%s@db:%v/%s" .user .password $.Values.db.port .db -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/* Pod security context compatible with the OpenShift restricted SCC: no fixed UID. */}}
{{- define "flamescope.podSecurityContext" -}}
runAsNonRoot: true
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{/* Container security context: read-only root filesystem, no privilege, no capabilities. */}}
{{- define "flamescope.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}
