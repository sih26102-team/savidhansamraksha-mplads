import { useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { Link, Route, Router as WouterRouter, Switch, useLocation, useParams } from 'wouter';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  Bell,
  Building2,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  FileSearch,
  FileText,
  Filter,
  Gavel,
  Home,
  IndianRupee,
  Landmark,
  LogOut,
  MapPin,
  Menu,
  Network,
  PanelLeftClose,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Target,
  UploadCloud,
  UserRound,
  X,
} from 'lucide-react';
import {
  AuthUserRole,
  LoginInputAuthority,
  ListProjectsRiskLevel,
  ListProjectsWorkflowStatus,
  ProjectActionInputAction,
  useCreateProjectAction,
  useGetCurrentUser,
  useGetDashboardSummary,
  useGetDemoAccounts,
  useGetProject,
  useListConstituencies,
  useListDistricts,
  useListProjectAudit,
  useListProjects,
  useListRecentAudit,
  useListStates,
  useLogin,
  useLogout,
  getGetDashboardSummaryQueryKey,
  getGetProjectQueryKey,
  getListProjectAuditQueryKey,
  getListProjectsQueryKey,
  getListRecentAuditQueryKey,
} from '@workspace/api-client-react';
import type { AuthUser, ProjectListItem, ProjectDetail, AuditEntry } from '@workspace/api-client-react';
import { ErrorBoundary } from '@/components/error-boundary';
import NotFound from '@/pages/not-found';
import './index.css';

const queryClient = new QueryClient();

const roleLabels: Record<string, string> = {
  MINISTRY: 'Ministry Administration',
  STATE_NODAL: 'State Nodal Authority',
  DISTRICT_AUTHORITY: 'District Nodal Officer',
  MP: 'Member of Parliament',
};

const money = (amount: number) => `₹${(amount / 10000000).toFixed(2)} Cr`;
const number = (amount: number) => new Intl.NumberFormat('en-IN').format(amount);
const date = (value: string) => new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value));

function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3" data-testid="brand-savidhan-samraksha">
      <div className="seal-mark"><Landmark size={21} strokeWidth={1.8} /></div>
      {!compact && <div><div className="font-serif text-[20px] leading-none tracking-tight">Savidhan<span className="text-[#d89d44]">Samraksha</span></div><div className="mt-1 font-mono text-[8px] uppercase tracking-[0.18em] text-[#91a7ba]">MPLADS intelligence desk</div></div>}
    </div>
  );
}

function StatusPill({ value, kind = 'risk' }: { value: string; kind?: 'risk' | 'workflow' | 'data' }) {
  const key = value.toUpperCase();
  const styles: Record<string, string> = {
    HIGH: 'pill-high', MODERATE: 'pill-moderate', LOW: 'pill-low', DATA_INCOMPLETE: 'pill-incomplete',
    OPEN: 'pill-open', UNDER_REVIEW: 'pill-review', RESOLVED: 'pill-resolved', DISMISSED: 'pill-muted',
    ESCALATED: 'pill-high', CLOSED: 'pill-muted', COMPLETE: 'pill-low', PARTIAL: 'pill-moderate', INCOMPLETE: 'pill-incomplete',
  };
  const label = key.replaceAll('_', ' ');
  return <span className={`status-pill ${styles[key] || ''}`} data-testid={`status-${kind}-${key.toLowerCase()}`}><span className="status-dot" />{label}</span>;
}

function ErrorState({ onRetry, message = 'We could not retrieve this workspace view.' }: { onRetry?: () => void; message?: string }) {
  return <div className="state-panel" data-testid="state-error"><div className="state-icon state-icon-error"><AlertTriangle size={19} /></div><h3>Signal unavailable</h3><p>{message}</p>{onRetry && <button className="button button-secondary" onClick={onRetry} data-testid="button-retry"><RefreshCw size={14} /> Try again</button>}</div>;
}

function Skeleton({ rows = 4 }: { rows?: number }) {
  return <div className="space-y-3" data-testid="state-loading">{Array.from({ length: rows }).map((_, index) => <div className="skeleton-row" key={index}><div className="skeleton w-8" /><div className="skeleton flex-1" /><div className="skeleton w-20" /></div>)}</div>;
}

function Sidebar({ user, onLogout }: { user?: AuthUser; onLogout: () => void }) {
  const [location] = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const links = [{ href: '/dashboard', label: 'Overview', icon: Home }, { href: '/projects', label: 'Project monitor', icon: Building2 }];
  return <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`} data-testid="sidebar">
    <div className="flex items-center justify-between px-5 py-5">{!collapsed && <Logo />}<button className="icon-button sidebar-collapse" onClick={() => setCollapsed(!collapsed)} aria-label="Collapse navigation" data-testid="button-collapse-sidebar">{collapsed ? <Menu size={18} /> : <PanelLeftClose size={18} />}</button></div>
    <div className="mx-4 mt-4 rounded-sm border border-[#345269] bg-[#1c3a50] px-3 py-3">{!collapsed ? <><div className="eyebrow text-[#8fa9bc]">CURRENT SCOPE</div><div className="mt-1 flex items-center gap-2 text-[13px] font-semibold text-[#f3f6f7]"><MapPin size={13} className="text-[#d89d44]" />{user?.scopeLabel || 'Signed-in authority'}</div></> : <MapPin size={17} className="mx-auto text-[#d89d44]" />}</div>
    <nav className="mt-7 px-3" aria-label="Primary navigation">{!collapsed && <div className="eyebrow mb-2 px-3 text-[#7691a5]">MONITORING DESK</div>}{links.map(({ href, label, icon: Icon }) => <Link href={href} key={href} className={`nav-link ${location.startsWith(href) ? 'nav-link-active' : ''}`} data-testid={`link-${label.toLowerCase().replace(' ', '-')}`}><Icon size={17} />{!collapsed && <span>{label}</span>}{location.startsWith(href) && !collapsed && <span className="nav-active-line" />}</Link>)}</nav>
    <div className="mt-auto px-3 pb-4">{!collapsed && <div className="eyebrow mb-2 px-3 text-[#7691a5]">ACCOUNTABILITY</div>}<button className="nav-link w-full" onClick={onLogout} data-testid="button-logout"><LogOut size={17} />{!collapsed && <span>Sign out</span>}</button>{!collapsed && <div className="mt-5 border-t border-[#345269] px-3 pt-4"><div className="flex items-center gap-2"><div className="avatar avatar-small">{user?.fullName?.split(' ').map((part) => part[0]).join('').slice(0, 2) || 'AU'}</div><div className="min-w-0"><div className="truncate text-[12px] font-semibold text-[#ecf1f2]">{user?.fullName || 'Authority user'}</div><div className="truncate text-[10px] text-[#8fa9bc]">{roleLabels[user?.role || ''] || 'Authority'}</div></div></div></div>}</div>
  </aside>;
}

function AppShell({ children, user }: { children: ReactNode; user?: AuthUser }) {
  const logout = useLogout();
  const [, navigate] = useLocation();
  const onLogout = () => logout.mutate(undefined, { onSuccess: () => { queryClient.clear(); navigate('/'); } });
  return <div className="app-shell"><Sidebar user={user} onLogout={onLogout} /><main className="main-area"><header className="topbar"><div className="flex min-w-0 items-center gap-3"><div className="mobile-logo"><Logo compact /></div><div className="breadcrumbs"><span className="text-[#728495]">National monitoring room</span><span>/</span><strong>{user?.scopeLabel || 'Authority workspace'}</strong></div></div><div className="flex items-center gap-3"><span className="dataset-badge"><span className="live-dot" />Synthetic Demonstration Dataset</span><button className="icon-button" aria-label="Notifications" data-testid="button-notifications"><Bell size={17} /></button><div className="avatar">{user?.fullName?.split(' ').map((part) => part[0]).join('').slice(0, 2) || 'AU'}</div></div></header>{children}</main></div>;
}

function AuthPage() {
  const login = useLogin();
  const { data: demos, isLoading: demosLoading } = useGetDemoAccounts();
  const { data: states, isLoading: statesLoading } = useListStates();
  const [authority, setAuthority] = useState<LoginInputAuthority>('MINISTRY');
  const [stateCode, setStateCode] = useState('');
  const [districtId, setDistrictId] = useState('');
  const [constituencyId, setConstituencyId] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const districts = useListDistricts(stateCode, { query: { queryKey: ['/api/administration/states', stateCode, 'districts'], enabled: Boolean(stateCode) } });
  const constituencies = useListConstituencies(stateCode, { query: { queryKey: ['/api/administration/states', stateCode, 'constituencies'], enabled: Boolean(stateCode) } });
  const [, navigate] = useLocation();
  const selectedDemo = (demo: { username: string; password: string; authority: string }) => { setAuthority(demo.authority as LoginInputAuthority); setUsername(demo.username); setPassword(demo.password); };
  const submit = (event: FormEvent) => { event.preventDefault(); login.mutate({ data: { authority, username, password, stateCode: stateCode || null, districtId: districtId || null, constituencyId: constituencyId || null, parliamentaryCategory: authority === 'MP' ? 'MPLADS' : null } }, { onSuccess: () => navigate('/dashboard') }); };
  return <div className="auth-page"><div className="auth-rail"><div className="auth-brand"><Logo /><div className="auth-rule" /><div className="eyebrow text-[#9bb0bd]">PUBLIC INFRASTRUCTURE OVERSIGHT</div><h1>Evidence before<br /><em>assumption.</em></h1><p>One workspace for authorities who need to see where public works stand, what the evidence says, and what accountable action comes next.</p><div className="auth-rail-footer"><span className="seal-mini"><ShieldCheck size={13} /></span><span>Designed for oversight. Not legal adjudication.</span></div></div></div><div className="auth-content"><div className="auth-form-wrap"><div className="mb-10 flex items-center justify-between"><div className="eyebrow text-[#8a9aa7]">AUTHORITY ACCESS / 01</div><div className="flex items-center gap-2 text-[11px] text-[#728495]"><span className="secure-lock"><ShieldCheck size={12} /></span> Cookie session protected</div></div><h2>Enter the monitoring room.</h2><p className="auth-lede">Select your authority scope to access a governed, read-auditable view of MPLADS delivery.</p><div className="role-grid">{(['MINISTRY', 'STATE_NODAL', 'DISTRICT_AUTHORITY', 'MP'] as const).map((role) => <button key={role} onClick={() => setAuthority(role)} className={`role-card ${authority === role ? 'role-card-active' : ''}`} data-testid={`button-authority-${role.toLowerCase()}`}><span className="role-icon">{role === 'MINISTRY' ? <Landmark size={17} /> : role === 'MP' ? <Gavel size={17} /> : role === 'STATE_NODAL' ? <Network size={17} /> : <MapPin size={17} />}</span><span><strong>{roleLabels[role]}</strong><small>{role === 'MP' ? 'Read-only constituency view' : role === 'MINISTRY' ? 'National programme view' : role === 'STATE_NODAL' ? 'State delivery view' : 'District delivery view'}</small></span>{authority === role && <Check className="ml-auto text-[#c38737]" size={15} />}</button>)}</div><form onSubmit={submit} className="mt-7 space-y-4"><div className="field-row"><label>Authority username<input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="e.g. ministry.demo" required data-testid="input-username" /></label><label>Access key<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Enter access key" required data-testid="input-password" /></label></div>{authority !== 'MINISTRY' && <div className="field-row"><label>State / Union Territory<select value={stateCode} onChange={(e) => { setStateCode(e.target.value); setDistrictId(''); setConstituencyId(''); }} required data-testid="select-state"><option value="">Select state</option>{states?.map((state) => <option key={state.code} value={state.code}>{state.name}</option>)}</select></label>{authority === 'DISTRICT_AUTHORITY' && <label>District<select value={districtId} onChange={(e) => setDistrictId(e.target.value)} required data-testid="select-district"><option value="">Select district</option>{districts.data?.map((district) => <option key={district.id} value={district.id}>{district.name}</option>)}</select></label>}{authority === 'MP' && <label>Parliamentary constituency<select value={constituencyId} onChange={(e) => setConstituencyId(e.target.value)} required data-testid="select-constituency"><option value="">Select constituency</option>{constituencies.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}</div>}{login.isError && <div className="form-error" data-testid="status-login-error"><AlertTriangle size={14} />The access key or authority scope could not be verified. Try the demo access below.</div>}<button className="button button-primary button-large w-full" disabled={login.isPending || statesLoading} type="submit" data-testid="button-enter-workspace">{login.isPending ? 'Verifying authority…' : 'Enter monitoring room'}<ChevronRight size={16} /></button></form><div className="auth-divider"><span>or use a safe demo account</span></div><div className="demo-list">{demosLoading ? <div className="skeleton h-12 w-full" /> : demos?.map((demo) => <button key={demo.username} onClick={() => selectedDemo(demo)} className="demo-row" data-testid={`button-demo-${demo.authority.toLowerCase()}`}><span className="demo-avatar">{demo.authority === 'MP' ? 'MP' : demo.authority === 'MINISTRY' ? 'MA' : demo.authority === 'STATE_NODAL' ? 'SN' : 'DN'}</span><span className="min-w-0 flex-1 text-left"><strong>{demo.label}</strong><small>{demo.scopeLabel}</small></span><span className="demo-use">Use account <ArrowUpRight size={13} /></span></button>)}</div><p className="mt-8 text-center text-[10px] leading-5 text-[#82919c]">By continuing, you acknowledge this is a <strong>Synthetic Demonstration Dataset</strong>.<br />AI signals are decision support and do not constitute legal findings.</p></div></div></div>;
}

function MetricCard({ label, value, detail, accent, icon: Icon }: { label: string; value: string; detail: string; accent?: string; icon: typeof Activity }) {
  return <div className="metric-card" data-testid={`metric-${label.toLowerCase().replaceAll(' ', '-')}`}><div className="flex items-start justify-between"><div className="eyebrow">{label}</div><span className={`metric-icon ${accent || ''}`}><Icon size={16} /></span></div><div className="mt-3 font-mono text-[25px] font-semibold tracking-[-0.05em] text-[#18354a]">{value}</div><div className="mt-1 text-[11px] text-[#718392]">{detail}</div></div>;
}

function ChartBars({ points, color = '#315f79' }: { points: { label: string; value: number }[]; color?: string }) {
  const max = Math.max(...points.map((p) => p.value), 1);
  return <div className="bar-chart">{points.map((point) => <div className="bar-column" key={point.label} data-testid={`bar-${point.label}`}><div className="bar-value">{number(point.value)}</div><div className="bar-track"><div className="bar-fill" style={{ height: `${Math.max(5, point.value / max * 100)}%`, backgroundColor: color }} /></div><div className="bar-label">{point.label}</div></div>)}</div>;
}

function DashboardPage() {
  const summary = useGetDashboardSummary();
  const recent = useListRecentAudit();
  if (summary.isLoading) return <PageFrame eyebrow="COMMAND OVERVIEW" title="Loading overview"><Skeleton rows={7} /></PageFrame>;
  if (summary.isError || !summary.data) return <PageFrame eyebrow="COMMAND OVERVIEW" title="Overview unavailable"><ErrorState onRetry={() => summary.refetch()} /></PageFrame>;
  const data = summary.data;
  const totals = data.totals;
  return <PageFrame eyebrow="COMMAND OVERVIEW" title="Delivery, seen clearly." subtitle={`${data.scopeLabel} · Last synchronised 12 minutes ago`} actions={<button className="button button-secondary" onClick={() => summary.refetch()} data-testid="button-refresh-dashboard"><RefreshCw size={14} /> Refresh view</button>}><div className="notice-strip"><Sparkles size={15} /><span><strong>AI-assisted monitoring:</strong> signals surface evidence patterns for human review. They do not make legal findings.</span><span className="ml-auto font-mono text-[10px] text-[#718392]">{data.syntheticLabel || 'Synthetic Demonstration Dataset'}</span></div><div className="metric-grid"><MetricCard label="Projects in scope" value={number(totals.totalProjects)} detail="Across active fiscal years" icon={Building2} /><MetricCard label="Sanctioned amount" value={money(totals.sanctionedAmount)} detail={`${money(totals.expenditure)} expenditure recorded`} accent="metric-icon-gold" icon={IndianRupee} /><MetricCard label="High risk" value={number(totals.highRisk)} detail={`${number(totals.moderateRisk)} moderate risk`} accent="metric-icon-red" icon={AlertTriangle} /><MetricCard label="Average progress" value={`${totals.averageProgress.toFixed(1)}%`} detail={`${number(totals.dataIncomplete)} records incomplete`} accent="metric-icon-green" icon={Target} /></div><div className="dashboard-grid mt-5"><section className="surface-card chart-card"><div className="card-heading"><div><div className="eyebrow">RISK DISTRIBUTION</div><h3>Where attention is needed</h3></div><span className="round-icon"><AlertTriangle size={15} /></span></div><div className="risk-summary">{data.riskDistribution.map((point) => <div key={point.label} className="risk-line"><span className={`risk-swatch risk-${point.label.toLowerCase().replace(' ', '-')}`} /><span>{point.label}</span><strong>{number(point.value)}</strong><div className="risk-progress"><span style={{ width: `${totals.totalProjects ? point.value / totals.totalProjects * 100 : 0}%` }} /></div></div>)}</div><div className="chart-footnote"><span>Signal threshold: score ≥ 0.70</span><span>Model refresh: 12 min ago</span></div></section><section className="surface-card chart-card"><div className="card-heading"><div><div className="eyebrow">DELIVERY STATUS</div><h3>Workflow posture</h3></div><span className="round-icon"><ClipboardCheck size={15} /></span></div><ChartBars points={data.statusDistribution} color="#d49b43" /><div className="chart-footnote"><span>Scoped project records</span><span>All statuses</span></div></section><section className="surface-card chart-card chart-wide"><div className="card-heading"><div><div className="eyebrow">FISCAL TREND</div><h3>Sanction and expenditure movement</h3></div><span className="round-icon"><BarChart3 size={15} /></span></div><div className="trend-legend"><span><i className="legend-dot legend-blue" />Projects</span><span><i className="legend-dot legend-gold" />Expenditure index</span></div><ChartBars points={data.fiscalTrend.map((point) => ({ label: point.label, value: point.projects }))} /><div className="chart-footnote"><span>FY 2021–22 to FY 2024–25</span><span>Values are synthetic</span></div></section><section className="surface-card chart-card"><div className="card-heading"><div><div className="eyebrow">PROJECT MIX</div><h3>Category coverage</h3></div><span className="round-icon"><Network size={15} /></span></div><div className="category-list">{data.categoryDistribution.slice(0, 5).map((point) => <div className="category-row" key={point.label}><span>{point.label}</span><strong>{number(point.value)}</strong><div className="category-track"><span style={{ width: `${totals.totalProjects ? point.value / totals.totalProjects * 100 : 0}%` }} /></div></div>)}</div></section></div><section className="surface-card mt-5"><div className="section-heading"><div><div className="eyebrow">AUDIT ACTIVITY</div><h3>Recent decisions in this scope</h3></div><Link href="/projects" className="text-link" data-testid="link-view-projects">View all projects <ArrowUpRight size={13} /></Link></div><AuditTable entries={(recent.data || data.recentActivity || []).slice(0, 5)} loading={recent.isLoading} /></section></PageFrame>;
}

function PageFrame({ eyebrow, title, subtitle, actions, children }: { eyebrow: string; title: string; subtitle?: string; actions?: ReactNode; children: ReactNode }) {
  return <div className="page-content"><div className="page-heading"><div><div className="eyebrow text-[#8a9aa7]">{eyebrow}</div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>{actions && <div>{actions}</div>}</div>{children}</div>;
}

function AuditTable({ entries, loading }: { entries: AuditEntry[]; loading?: boolean }) {
  if (loading) return <Skeleton rows={4} />;
  if (!entries.length) return <div className="empty-inline"><Clock3 size={17} />No audit activity recorded in this scope yet.</div>;
  return <div className="audit-table">{entries.map((entry) => <div className="audit-row" key={entry.id} data-testid={`audit-row-${entry.id}`}><div className="audit-icon"><ClipboardCheck size={14} /></div><div className="min-w-0 flex-1"><div className="truncate text-[12px] font-semibold text-[#26475d]">{entry.action.replaceAll('_', ' ')} <span className="font-normal text-[#728495]">· {entry.workId}</span></div><div className="mt-1 truncate text-[11px] text-[#778996]">{entry.reason}</div></div><div className="text-right"><div className="text-[11px] font-semibold text-[#426278]">{entry.userName}</div><div className="mt-1 font-mono text-[10px] text-[#8a9aa7]">{date(entry.timestamp)}</div></div></div>)}</div>;
}

function ProjectsPage() {
  const [search, setSearch] = useState('');
  const [risk, setRisk] = useState('');
  const [workflow, setWorkflow] = useState('');
  const [page, setPage] = useState(0);
  const params = useMemo(() => ({ search: search || undefined, riskLevel: (risk || undefined) as ListProjectsRiskLevel | undefined, workflowStatus: (workflow || undefined) as ListProjectsWorkflowStatus | undefined, limit: 10, offset: page * 10 }), [search, risk, workflow, page]);
  const projects = useListProjects(params);
  return <PageFrame eyebrow="PROJECT MONITOR" title="Works in focus." subtitle="Search, filter, and inspect project records within your authority scope." actions={<button className="button button-secondary" onClick={() => projects.refetch()} data-testid="button-refresh-projects"><RefreshCw size={14} /> Refresh</button>}><div className="notice-strip notice-strip-slim"><FileSearch size={15} /><span>Risk signals are prioritisation aids. Review source evidence before taking workflow action.</span></div><section className="surface-card project-list-card"><div className="filter-bar"><div className="search-field"><Search size={16} /><input value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder="Search work ID, description, district…" data-testid="input-project-search" /></div><select value={risk} onChange={(e) => { setRisk(e.target.value); setPage(0); }} data-testid="select-risk-filter"><option value="">All risk levels</option><option value="HIGH">High risk</option><option value="MODERATE">Moderate risk</option><option value="LOW">Low risk</option><option value="DATA_INCOMPLETE">Data incomplete</option></select><select value={workflow} onChange={(e) => { setWorkflow(e.target.value); setPage(0); }} data-testid="select-status-filter"><option value="">All workflow statuses</option>{Object.entries(ListProjectsWorkflowStatus).map(([key, value]) => <option value={value} key={key}>{value.replaceAll('_', ' ')}</option>)}</select><button className="icon-button" aria-label="Filter projects" data-testid="button-more-filters"><SlidersHorizontal size={16} /></button></div><div className="table-meta"><span>{projects.data ? `${number(projects.data.total)} projects in scope` : 'Loading project records'}</span><span className="ml-auto flex items-center gap-2"><span className="live-dot" />Live scope</span></div>{projects.isLoading ? <Skeleton rows={8} /> : projects.isError ? <ErrorState onRetry={() => projects.refetch()} /> : projects.data?.items.length ? <ProjectTable items={projects.data.items} /> : <div className="empty-state"><div className="state-icon"><Search size={18} /></div><h3>No matching projects</h3><p>Try a broader search or clear one of the active filters.</p><button className="button button-secondary" onClick={() => { setSearch(''); setRisk(''); setWorkflow(''); }} data-testid="button-clear-filters">Clear filters</button></div>}<div className="pagination"><span className="text-[11px] text-[#718392]">Page {page + 1} of {Math.max(1, Math.ceil((projects.data?.total || 0) / 10))}</span><div className="flex gap-2"><button className="icon-button" disabled={page === 0} onClick={() => setPage((value) => value - 1)} aria-label="Previous page" data-testid="button-previous-page"><ChevronLeft size={16} /></button><button className="icon-button" disabled={!projects.data || (page + 1) * 10 >= projects.data.total} onClick={() => setPage((value) => value + 1)} aria-label="Next page" data-testid="button-next-page"><ChevronRight size={16} /></button></div></div></section></PageFrame>;
}

function ProjectTable({ items }: { items: ProjectListItem[] }) {
  return <div className="overflow-x-auto"><table className="project-table"><thead><tr><th>Work / location</th><th>Category</th><th>Delivery</th><th>Risk signal</th><th>Workflow</th><th>Updated</th><th /></tr></thead><tbody>{items.map((item) => <tr key={item.workId} data-testid={`row-project-${item.workId}`}><td><Link href={`/projects/${item.workId}`} className="work-link" data-testid={`link-project-${item.workId}`}><span className="font-mono text-[11px]">{item.workId}</span><strong>{item.description}</strong><span className="location-line"><MapPin size={11} />{item.district}, {item.state}</span></Link></td><td><span className="text-[12px] text-[#4b6678]">{item.category}</span><span className="block mt-1 font-mono text-[10px] text-[#8695a0]">{item.fiscalYear}</span></td><td><div className="progress-number">{item.physicalProgress.toFixed(0)}%</div><div className="mini-progress"><span style={{ width: `${item.physicalProgress}%` }} /></div><span className="mt-1 block text-[10px] text-[#8998a2]">{money(item.expenditure)} spent</span></td><td><div className="flex flex-col gap-1"><StatusPill value={item.riskLevel} /><span className="font-mono text-[10px] text-[#8b99a2]">score {item.riskScore.toFixed(2)}</span></div></td><td><StatusPill value={item.workflowStatus} kind="workflow" /></td><td><span className="font-mono text-[10px] text-[#728495]">{date(item.updatedAt)}</span></td><td><Link href={`/projects/${item.workId}`} className="icon-button" aria-label={`Open ${item.workId}`} data-testid={`button-open-project-${item.workId}`}><ChevronRight size={15} /></Link></td></tr>)}</tbody></table></div>;
}

function DetailRow({ label, value, mono = false }: { label: string; value: ReactNode; mono?: boolean }) { return <div className="detail-row"><span>{label}</span><strong className={mono ? 'font-mono text-[12px]' : ''}>{value}</strong></div>; }

function ActionPanel({ project, readOnly }: { project: ProjectDetail; readOnly: boolean }) {
  const action = useCreateProjectAction();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<ProjectActionInputAction>('REVIEW');
  const [reason, setReason] = useState('');
  const client = useQueryClient();
  const submit = () => { action.mutate({ workId: project.workId, data: { action: selected, reason } }, { onSuccess: () => { setOpen(false); setReason(''); client.invalidateQueries({ queryKey: getGetProjectQueryKey(project.workId) }); client.invalidateQueries({ queryKey: getListProjectAuditQueryKey(project.workId) }); client.invalidateQueries({ queryKey: getGetDashboardSummaryQueryKey() }); client.invalidateQueries({ queryKey: getListRecentAuditQueryKey() }); client.invalidateQueries({ queryKey: getListProjectsQueryKey() }); } }); };
  if (readOnly) return <div className="readonly-note"><Gavel size={15} /><span><strong>Read-only constituency view</strong><br />Workflow actions are reserved for the accountable nodal authority.</span></div>;
  return <div className="action-panel"><div className="flex items-start gap-3"><div className="round-icon round-icon-gold"><Gavel size={15} /></div><div><div className="eyebrow">ACCOUNTABLE ACTION</div><h3>Move this record forward</h3><p>Actions are written to the audit trail and remain reversible through authority review.</p></div></div>{!open ? <button className="button button-primary mt-4 w-full" onClick={() => setOpen(true)} data-testid="button-open-action">Open workflow action <ChevronRight size={15} /></button> : <div className="mt-4 space-y-3"><label className="field-label">Action<select value={selected} onChange={(e) => setSelected(e.target.value as ProjectActionInputAction)} data-testid="select-project-action">{Object.entries(ProjectActionInputAction).map(([key, value]) => <option value={value} key={key}>{value.replaceAll('_', ' ')}</option>)}</select></label><label className="field-label">Reason <span className="text-[#a17e4a]">required</span><textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Record the evidence or accountable next step…" minLength={5} rows={3} data-testid="textarea-action-reason" /></label>{action.isError && <div className="form-error"><AlertTriangle size={13} />Action could not be applied. Please try again.</div>}<div className="flex gap-2"><button className="button button-secondary flex-1" onClick={() => setOpen(false)} data-testid="button-cancel-action">Cancel</button><button className="button button-primary flex-1" disabled={reason.trim().length < 5 || action.isPending} onClick={submit} data-testid="button-submit-action">{action.isPending ? 'Writing audit…' : 'Confirm action'}</button></div></div>}</div>;
}

function ProjectDetailPage() {
  const { workId = '' } = useParams<{ workId: string }>();
  const current = useGetCurrentUser();
  const project = useGetProject(workId, { query: { queryKey: getGetProjectQueryKey(workId), enabled: Boolean(workId) } });
  const audit = useListProjectAudit(workId, { query: { queryKey: getListProjectAuditQueryKey(workId), enabled: Boolean(workId) } });
  if (project.isLoading) return <PageFrame eyebrow="PROJECT FILE" title="Opening evidence file…"><Skeleton rows={9} /></PageFrame>;
  if (project.isError || !project.data) return <PageFrame eyebrow="PROJECT FILE" title="Evidence file unavailable"><ErrorState onRetry={() => project.refetch()} message="This work ID is not available in the current authority scope." /></PageFrame>;
  const item = project.data;
  return <PageFrame eyebrow={`PROJECT FILE / ${item.workId}`} title={item.description} subtitle={`${item.district}, ${item.state} · ${item.category} · ${item.fiscalYear}`} actions={<Link href="/projects" className="button button-secondary" data-testid="link-back-projects"><ChevronLeft size={14} /> Back to projects</Link>}><div className="detail-top"><div className="detail-statuses"><StatusPill value={item.riskLevel} /><StatusPill value={item.workflowStatus} kind="workflow" /><span className="font-mono text-[10px] text-[#7b8d9a]">Updated {date(item.updatedAt)}</span></div><div className="detail-confidence"><span className="eyebrow">RISK SCORE</span><strong>{item.riskScore.toFixed(2)}</strong><span>Model output · synthetic</span></div></div><div className="detail-layout"><div className="detail-main"><section className="surface-card"><div className="section-heading"><div><div className="eyebrow">AT A GLANCE</div><h3>Delivery record</h3></div><StatusPill value={item.dataCompleteness} kind="data" /></div><div className="detail-grid"><DetailRow label="Sanctioned amount" value={money(item.sanctionedAmount)} /><DetailRow label="Estimated cost" value={money(item.estimatedCost)} /><DetailRow label="Expenditure" value={money(item.expenditure)} /><DetailRow label="Physical progress" value={<span>{item.physicalProgress.toFixed(1)}% <span className="font-normal text-[#8695a0]">complete</span></span>} /><DetailRow label="Date of sanction" value={date(item.dateOfSanction)} /><DetailRow label="Expected completion" value={date(item.expectedCompletionDate)} /></div><div className="large-progress"><div><span>Physical progress</span><strong>{item.physicalProgress.toFixed(1)}%</strong></div><div className="large-progress-track"><span style={{ width: `${item.physicalProgress}%` }} /></div></div></section><section className="surface-card"><div className="section-heading"><div><div className="eyebrow">RISK INTELLIGENCE</div><h3>Why this record was flagged</h3></div><span className="ai-tag"><Sparkles size={12} /> AI-assisted</span></div><p className="disclaimer">These are model-generated signals based on available records and imagery. They are not legal findings.</p><div className="finding-list">{item.findings.map((finding, index) => <div className="finding" key={`${finding.title}-${index}`}><div className={`finding-marker finding-${finding.severity.toLowerCase()}`}><AlertTriangle size={14} /></div><div className="min-w-0"><div className="flex items-center gap-2"><strong>{finding.title}</strong><StatusPill value={finding.severity} /></div><p>{finding.explanation}</p><div className="finding-evidence"><FileSearch size={12} /><span><strong>Evidence:</strong> {finding.evidence}</span></div></div></div>)}</div></section><section className="surface-card"><div className="section-heading"><div><div className="eyebrow">ML MODULES</div><h3>Signal availability</h3></div></div><div className="module-grid">{item.modules.map((module) => <div className="module-card" key={module.name}><div className="flex items-center justify-between"><span className="module-name">{module.name}</span><span className={`module-status module-${module.status.toLowerCase()}`}><span />{module.status.replaceAll('_', ' ')}</span></div>{module.score !== null && module.score !== undefined && <div className="module-score">{module.score.toFixed(2)}</div>}<p>{module.summary}</p><div className="module-evidence">{module.evidence.slice(0, 2).map((evidence) => <span key={evidence}><Check size={11} />{evidence}</span>)}</div></div>)}</div></section><section className="surface-card"><div className="section-heading"><div><div className="eyebrow">PROJECT AUDIT</div><h3>Accountability trail</h3></div></div><AuditTable entries={audit.data || []} loading={audit.isLoading} /></section></div><aside className="detail-side"><ActionPanel project={item} readOnly={Boolean(current.data?.readOnly || current.data?.role === AuthUserRole.MP)} /><section className="surface-card"><div className="eyebrow">AGENCY & MP</div><h3 className="mt-2">Accountability context</h3><div className="detail-stack mt-4"><DetailRow label="Implementing agency" value={item.agency} /><DetailRow label="Agency type" value={item.agencyType} /><DetailRow label="State-level agency" value={item.agencyStateLevel ? 'Yes' : 'No'} /><DetailRow label="Member of Parliament" value={item.mpName} /><DetailRow label="MP category" value={item.mpCategory} /><DetailRow label="Constituency" value={item.mpConstituency} /></div></section><section className="surface-card"><div className="eyebrow">COMPLIANCE CHECKS</div><h3 className="mt-2">Required records</h3><div className="check-list"><div><span className={item.tenderInvited ? 'check-good' : 'check-warn'}>{item.tenderInvited ? <Check size={12} /> : <AlertTriangle size={12} />}</span><span>Tender invited</span><strong>{item.tenderInvited ? 'Filed' : 'Missing'}</strong></div><div><span className={item.ucFiled ? 'check-good' : 'check-warn'}>{item.ucFiled ? <Check size={12} /> : <AlertTriangle size={12} />}</span><span>Utilisation certificate</span><strong>{item.ucFiled ? 'Filed' : 'Missing'}</strong></div></div></section><section className="surface-card"><div className="eyebrow">PAYMENT REGISTER</div><h3 className="mt-2">Tranches recorded</h3><div className="payment-total">{money(item.paymentTotal)}</div><div className="payment-list">{item.payments.map((payment) => <div className="payment-row" key={`${payment.tranche}-${payment.date}`}><span className="font-mono text-[10px] text-[#7d8d99]">{payment.tranche}</span><strong>{money(payment.amount)}</strong><span>{date(payment.date)}</span></div>)}</div></section></aside></div></PageFrame>;
}

function AuthGate({ children }: { children: ReactNode }) {
  const current = useGetCurrentUser();
  if (current.isLoading) return <div className="auth-loading"><Logo /><Skeleton rows={4} /></div>;
  if (current.isError || !current.data) return <AuthPage />;
  return <AppShell user={current.data}>{children}</AppShell>;
}

function Router() {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}><Switch><Route path="/"><AuthPage /></Route><Route path="/dashboard"><AuthGate><DashboardPage /></AuthGate></Route><Route path="/projects"><AuthGate><ProjectsPage /></AuthGate></Route><Route path="/projects/:workId"><AuthGate><ProjectDetailPage /></AuthGate></Route><Route component={NotFound} /></Switch></ErrorBoundary>;
}

export default function App() {
  return <QueryClientProvider client={queryClient}><WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}><Router /></WouterRouter></QueryClientProvider>;
}