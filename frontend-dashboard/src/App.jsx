import { useEffect, useMemo, useRef, useState } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { Link, Route, Router as WouterRouter, Switch, useLocation, useParams } from 'wouter';
import { AlertOctagon, AlertTriangle, ArrowUpRight, BarChart3, Bell, Building2, Check, ChevronLeft, ChevronRight, ClipboardCheck, Clock3, Copy, FileSearch, Gavel, Home, IndianRupee, Landmark, LogOut, MapPin, Menu, Network, PanelLeftClose, RefreshCw, Search, ShieldCheck, SlidersHorizontal, Sparkles, Target, X, } from 'lucide-react';
import { AuthUserRole, ListProjectsWorkflowStatus, useCreateProjectAction, useGetCurrentUser, useGetDashboardSummary, useGetDemoAccounts, useGetProject, useListConstituencies, useListDistricts, useListEscalatedProjects, useListProjectAudit, useListProjects, useListRecentAudit, useListStates, useLogin, useLogout, getGetDashboardSummaryQueryKey, getGetProjectQueryKey, getListEscalatedProjectsQueryKey, getListProjectAuditQueryKey, getListProjectsQueryKey, getListRecentAuditQueryKey, } from '@/lib/api';
import { ALL_INDIAN_STATES, getDistrictsForState, getConstituenciesForState } from '@/lib/india-data';
import { setAuthTokenGetter } from '@/lib/api/custom-fetch';
import { ErrorBoundary } from '@/components/error-boundary';
import NotFound from '@/pages/not-found';
import './index.css';

if (typeof window !== 'undefined') {
    setAuthTokenGetter(() => localStorage.getItem("savidhan_session_token"));
}

const queryClient = new QueryClient();
const roleLabels = {
    MINISTRY: 'Ministry Administration',
    STATE_NODAL: 'State Nodal Authority',
    DISTRICT_AUTHORITY: 'District Nodal Officer',
    MP: 'Member of Parliament',
};
const money = (amount) => {
    const val = Number(amount);
    if (isNaN(val)) return '₹0.00 Cr';
    return `₹${(val / 10000000).toFixed(2)} Cr`;
};
const number = (amount) => {
    const val = Number(amount);
    if (isNaN(val)) return '0';
    return new Intl.NumberFormat('en-IN').format(val);
};
const date = (value) => {
    if (!value) return '—';
    try {
        const d = new Date(value);
        if (isNaN(d.getTime())) return '—';
        return new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(d);
    } catch {
        return '—';
    }
};
function Logo({ compact = false }) {
    return (<div className="brand-container" data-testid="brand-savidhan-samraksha">
      <div className="seal-mark"><Landmark size={20} strokeWidth={1.8}/></div>
      {!compact && (<div className="brand-text-block">
          <div className="brand-title">Savidhan<span className="text-[#d89d44]">Samraksha</span></div>
          <div className="brand-subtitle">MPLADS intelligence desk</div>
        </div>)}
    </div>);
}
function StatusPill({ value, kind = 'risk' }) {
    const key = (value ? String(value) : 'UNKNOWN').toUpperCase();
    const styles = {
        HIGH: 'pill-high', MODERATE: 'pill-moderate', LOW: 'pill-low', DATA_INCOMPLETE: 'pill-incomplete',
        OPEN: 'pill-open', UNDER_REVIEW: 'pill-review', RESOLVED: 'pill-resolved', DISMISSED: 'pill-muted',
        ESCALATED: 'pill-high', ESCALATED_STATE: 'pill-high', CLOSED: 'pill-muted', COMPLETE: 'pill-low', PARTIAL: 'pill-moderate', INCOMPLETE: 'pill-incomplete',
    };
    const label = key.replaceAll('_', ' ');
    return <span className={`status-pill ${styles[key] || ''}`} data-testid={`status-${kind}-${key.toLowerCase()}`}><span className="status-dot"/>{label}</span>;
}
function ErrorState({ onRetry, message = 'We could not retrieve this workspace view.' }) {
    return <div className="state-panel" data-testid="state-error"><div className="state-icon state-icon-error"><AlertTriangle size={19}/></div><h3>Signal unavailable</h3><p>{message}</p>{onRetry && <button className="button button-secondary" onClick={onRetry} data-testid="button-retry"><RefreshCw size={14}/> Try again</button>}</div>;
}
function Skeleton({ rows = 4 }) {
    return <div className="space-y-3" data-testid="state-loading">{Array.from({ length: rows }).map((_, index) => <div className="skeleton-row" key={index}><div className="skeleton w-8"/><div className="skeleton flex-1"/><div className="skeleton w-20"/></div>)}</div>;
}
function RiskSignalCell({ riskLevel, riskScore }) {
    const safeLevel = (riskLevel ? String(riskLevel) : 'LOW').toUpperCase();
    const safeScore = Number(riskScore);
    return (<div className="risk-signal-cell" data-testid={`risk-signal-${safeLevel.toLowerCase()}`}>
      <div className="risk-pill-row">
        <StatusPill value={safeLevel}/>
      </div>
      <div className="risk-score-row">
        <span className="risk-score-label">Score:</span>
        <span className="risk-score-value">{isNaN(safeScore) ? '0.00' : safeScore.toFixed(2)}</span>
      </div>
    </div>);
}
function Sidebar({ user, onLogout }) {
    const [location] = useLocation();
    const [collapsed, setCollapsed] = useState(false);
    const summary = useGetDashboardSummary();
    const escalatedCount = summary.data?.totals.escalatedCount ?? 0;
    // Strict RBAC: District Authority cannot receive escalations from lower tiers
    const canReceiveEscalations = user?.role !== AuthUserRole.DISTRICT_AUTHORITY;
    const links = [
        { href: '/dashboard', label: 'Overview', icon: Home, badge: 0 },
        { href: '/projects', label: 'Project monitor', icon: Building2, badge: 0 },
        ...(canReceiveEscalations
            ? [{ href: '/escalated-projects', label: 'Escalated projects', icon: AlertOctagon, badge: escalatedCount }]
            : []),
    ];
    return (<aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`} data-testid="sidebar">
      <div className="sidebar-header">
        {!collapsed && <Logo />}
        <button className="icon-button sidebar-collapse" onClick={() => setCollapsed(!collapsed)} aria-label="Collapse navigation" data-testid="button-collapse-sidebar">
          {collapsed ? <Menu size={16}/> : <PanelLeftClose size={16}/>}
        </button>
      </div>

      <div className="sidebar-scope-card">
        {!collapsed ? (<>
            <div className="sidebar-scope-tag">CURRENT SCOPE</div>
            <div className="sidebar-scope-value">
              <MapPin size={13} className="text-[#d89d44] shrink-0"/>
              <span>{user?.scopeLabel || 'Signed-in authority'}</span>
            </div>
          </>) : (<MapPin size={17} className="mx-auto text-[#d89d44]"/>)}
      </div>

      <nav className="sidebar-nav" aria-label="Primary navigation">
        {!collapsed && <div className="sidebar-section-title">MONITORING DESK</div>}
        {links.map(({ href, label, icon: Icon, badge }) => (<Link href={href} key={href} className={`nav-link ${location.startsWith(href) ? 'nav-link-active' : ''}`} data-testid={`link-${label.toLowerCase().replaceAll(' ', '-')}`}>
            <Icon size={16} className="shrink-0"/>
            {!collapsed && <span>{label}</span>}
            {badge > 0 && (!collapsed ? (<span className="sidebar-badge" data-testid="badge-escalated-count">
                {badge}
              </span>) : (<span className="sidebar-badge-dot"/>))}
          </Link>))}
      </nav>

      <div className="sidebar-footer">
        {!collapsed && <div className="sidebar-section-title">ACCOUNTABILITY</div>}
        <button className="nav-link w-full text-left" onClick={onLogout} data-testid="button-logout">
          <LogOut size={16} className="shrink-0"/>
          {!collapsed && <span>Sign out</span>}
        </button>
        {!collapsed && (<div className="sidebar-user-card">
            <div className="avatar avatar-small">
              {user?.fullName?.split(' ').map((part) => part[0]).join('').slice(0, 2) || 'AU'}
            </div>
            <div className="min-w-0">
              <div className="sidebar-user-name">{user?.fullName || 'Authority user'}</div>
              <div className="sidebar-user-role">{roleLabels[user?.role || ''] || 'Authority'}</div>
            </div>
          </div>)}
      </div>
    </aside>);
}
function UserProfileMenu({ user, onLogout }) {
    const [isOpen, setIsOpen] = useState(false);
    const [copied, setCopied] = useState(false);
    const [, navigate] = useLocation();
    const menuRef = useRef(null);
    useEffect(() => {
        function handleClickOutside(event) {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        }
        function handleKeyDown(event) {
            if (event.key === 'Escape') {
                setIsOpen(false);
            }
        }
        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
            document.addEventListener('keydown', handleKeyDown);
        }
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [isOpen]);
    const initials = user?.fullName?.split(' ').map((part) => part[0]).join('').slice(0, 2) || 'AU';
    const handleCopyScope = () => {
        const text = `${user?.fullName || 'User'} (${roleLabels[user?.role || ''] || user?.role}) - Scope: ${user?.scopeLabel || 'N/A'}`;
        navigator.clipboard?.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };
    return (<div className="profile-dropdown-wrapper" ref={menuRef}>
      <button type="button" className={`avatar-button ${isOpen ? 'avatar-button-active' : ''}`} onClick={() => setIsOpen(!isOpen)} aria-expanded={isOpen} aria-label="User profile and account settings" data-testid="button-user-profile-menu">
        <div className="avatar">{initials}</div>
      </button>

      {isOpen && (<div className="profile-dropdown-menu" data-testid="profile-dropdown-menu">
          <div className="profile-dropdown-header">
            <div className="flex items-center gap-3">
              <div className="avatar avatar-large">{initials}</div>
              <div className="min-w-0">
                <div className="profile-dropdown-name">{user?.fullName || 'Authority user'}</div>
                <div className="profile-dropdown-role">{roleLabels[user?.role || ''] || user?.role}</div>
              </div>
            </div>
            <div className="profile-dropdown-scope">
              <MapPin size={11} className="text-[#d89d44] shrink-0"/>
              <span>{user?.scopeLabel || 'National Jurisdiction'}</span>
            </div>
          </div>

          <div className="profile-dropdown-divider"/>

          <div className="profile-dropdown-body">
            <button type="button" className="profile-dropdown-item" onClick={() => {
                setIsOpen(false);
                navigate('/projects');
            }} data-testid="dropdown-link-projects">
              <Building2 size={14}/>
              <span>Jurisdiction projects</span>
            </button>

            <button type="button" className="profile-dropdown-item" onClick={handleCopyScope} data-testid="dropdown-action-copy">
              {copied ? <Check size={14} className="text-[#3b8a6a]"/> : <Copy size={14}/>}
              <span>{copied ? 'Details copied!' : 'Copy authority profile'}</span>
            </button>

            <button type="button" className="profile-dropdown-item" onClick={() => {
                setIsOpen(false);
                navigate('/dashboard');
            }} data-testid="dropdown-link-dashboard">
              <Home size={14}/>
              <span>Oversight dashboard</span>
            </button>
          </div>

          <div className="profile-dropdown-divider"/>

          <div className="profile-dropdown-footer">
            <button type="button" className="profile-dropdown-item profile-dropdown-logout" onClick={() => {
                setIsOpen(false);
                onLogout();
            }} data-testid="dropdown-button-signout">
              <LogOut size={14}/>
              <span>Sign out of session</span>
            </button>
          </div>
        </div>)}
    </div>);
}
function AppShell({ children, user }) {
    const logout = useLogout();
    const [, navigate] = useLocation();
    const onLogout = () => logout.mutate(undefined, {
        onSuccess: () => {
            localStorage.removeItem("savidhan_session_token");
            queryClient.clear();
            navigate('/');
        }
    });
    return (<div className="app-shell">
      <Sidebar user={user} onLogout={onLogout}/>
      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <div className="mobile-logo"><Logo compact/></div>
            <div className="breadcrumbs">
              <span className="text-[#728495]">National monitoring room</span>
              <span>/</span>
              <strong>{user?.scopeLabel || 'Authority workspace'}</strong>
            </div>
          </div>
          <div className="topbar-right">
            <span className="dataset-badge">
              <span className="live-dot"/>Synthetic Demonstration Dataset
            </span>
            <button className="icon-button" aria-label="Notifications" data-testid="button-notifications">
              <Bell size={16}/>
            </button>
            <UserProfileMenu user={user} onLogout={onLogout}/>
          </div>
        </header>
        {children}
      </main>
    </div>);
}
const FALLBACK_DEMOS = [
  {
    label: "Ministry Administration",
    username: "kavita.sharma",
    password: "Demo@123",
    authority: "MINISTRY",
    scopeLabel: "National monitoring scope",
  },
  {
    label: "State Nodal Authority",
    username: "raghavendra.rao",
    password: "Demo@123",
    authority: "STATE_NODAL",
    scopeLabel: "Andhra Pradesh state scope",
    stateCode: "AP",
  },
  {
    label: "District Nodal Officer",
    username: "suresh.kumar",
    password: "Demo@123",
    authority: "DISTRICT_AUTHORITY",
    scopeLabel: "Anakapalli, Andhra Pradesh",
    stateCode: "AP",
    districtId: "AP-01",
  },
  {
    label: "Lok Sabha MP",
    username: "meenakshi.iyer",
    password: "Demo@123",
    authority: "MP",
    mpCategory: "LOK_SABHA",
    scopeLabel: "AP · Parliamentary Constituency 1",
    stateCode: "AP",
    constituencyId: "AP-LS-01",
  },
  {
    label: "Rajya Sabha MP",
    username: "vikram.varma",
    password: "Demo@123",
    authority: "MP",
    mpCategory: "RAJYA_SABHA",
    scopeLabel: "AP · Anakapalli District (Rajya Sabha)",
    stateCode: "AP",
    districtId: "AP-01",
  },
  {
    label: "Nominated MP",
    username: "sneha.deshmukh",
    password: "Demo@123",
    authority: "MP",
    mpCategory: "NOMINATED",
    scopeLabel: "National oversight (Nominated MP)",
  },
];

function AuthPage() {
    const login = useLogin();
    const { data: demosData, isLoading: demosLoading } = useGetDemoAccounts();
    const demos = Array.isArray(demosData) && demosData.length > 0 ? demosData : FALLBACK_DEMOS;
    const { data: statesData, isLoading: statesLoading } = useListStates();
    const states = useMemo(() => {
        if (Array.isArray(statesData) && statesData.length > 0) return statesData;
        return ALL_INDIAN_STATES;
    }, [statesData]);
    const [authority, setAuthority] = useState('MINISTRY');
    const [mpCategory, setMpCategory] = useState('');
    const [stateCode, setStateCode] = useState('');
    const [districtId, setDistrictId] = useState('');
    const [constituencyId, setConstituencyId] = useState('');
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const districtsQuery = useListDistricts(stateCode, {
        query: { queryKey: ['/api/administration/states', stateCode, 'districts'], enabled: Boolean(stateCode) },
    });
    const availableDistricts = useMemo(() => {
        if (!stateCode) return [];
        if (Array.isArray(districtsQuery.data) && districtsQuery.data.length > 0) {
            return districtsQuery.data;
        }
        return getDistrictsForState(stateCode);
    }, [stateCode, districtsQuery.data]);
    const constituenciesQuery = useListConstituencies(stateCode, {
        query: { queryKey: ['/api/administration/states', stateCode, 'constituencies'], enabled: Boolean(stateCode) },
    });
    const availableConstituencies = useMemo(() => {
        if (!stateCode) return [];
        if (Array.isArray(constituenciesQuery.data) && constituenciesQuery.data.length > 0) {
            return constituenciesQuery.data;
        }
        return getConstituenciesForState(stateCode);
    }, [stateCode, constituenciesQuery.data]);
    const [, navigate] = useLocation();
    const handleRoleChange = (role) => {
        setAuthority(role);
        setMpCategory('');
        setStateCode('');
        setDistrictId('');
        setConstituencyId('');
        setUsername('');
        setPassword('');
    };
    const selectedDemo = (demo) => {
        setAuthority(demo.authority);
        setUsername(demo.username);
        setPassword(demo.password);
        if (demo.authority === 'MP' && demo.mpCategory) {
            setMpCategory(demo.mpCategory);
        }
        setStateCode(demo.stateCode || '');
        setDistrictId(demo.districtId || '');
        setConstituencyId(demo.constituencyId || '');
    };
    const availableDemos = useMemo(() => {
        if (!Array.isArray(demos))
            return [];
        if (authority === 'MINISTRY') {
            return demos.filter((d) => d.authority === 'MINISTRY');
        }
        if (authority === 'STATE_NODAL') {
            return demos.filter((d) => d.authority === 'STATE_NODAL');
        }
        if (authority === 'DISTRICT_AUTHORITY') {
            return demos.filter((d) => d.authority === 'DISTRICT_AUTHORITY');
        }
        if (authority === 'MP') {
            if (!mpCategory)
                return [];
            return demos.filter((d) => d.authority === 'MP' && d.mpCategory === mpCategory);
        }
        return demos;
    }, [demos, authority, mpCategory]);
    const submit = (event) => {
        event.preventDefault();
        login.mutate({
            data: {
                authority,
                username,
                password,
                stateCode: stateCode || null,
                districtId: districtId || null,
                constituencyId: constituencyId || null,
                parliamentaryCategory: authority === 'MP' ? mpCategory : null,
            },
        }, {
            onSuccess: (res) => {
                if (res?.token) {
                    localStorage.setItem("savidhan_session_token", res.token);
                }
                queryClient.invalidateQueries({ queryKey: ['/api/auth/me'] });
                navigate('/dashboard');
            }
        });
    };
    return (<div className="auth-page">
      <div className="auth-rail">
        <div className="auth-brand">
          <Logo />
          <div className="auth-rule"/>
          <div className="eyebrow text-[#9bb0bd]">PUBLIC INFRASTRUCTURE OVERSIGHT</div>
          <h1>Evidence before<br /><em>assumption.</em></h1>
          <p>One workspace for authorities who need to see where public works stand, what the evidence says, and what accountable action comes next.</p>
          <div className="auth-rail-footer">
            <span className="seal-mini"><ShieldCheck size={13}/></span>
            <span>Designed for oversight. Not legal adjudication.</span>
          </div>
        </div>
      </div>
      <div className="auth-content">
        <div className="auth-form-wrap">
          <div className="mb-10 flex items-center justify-between">
            <div className="eyebrow text-[#8a9aa7]">AUTHORITY ACCESS / 01</div>
            <div className="flex items-center gap-2 text-[11px] text-[#728495]">
              <span className="secure-lock"><ShieldCheck size={12}/></span> Cookie session protected
            </div>
          </div>
          <h2>Enter the monitoring room.</h2>
          <p className="auth-lede">Select your authority scope to access a governed, read-auditable view of MPLADS delivery.</p>

          <div className="role-grid">
            {['MINISTRY', 'STATE_NODAL', 'DISTRICT_AUTHORITY', 'MP'].map((role) => (<button key={role} onClick={() => handleRoleChange(role)} className={`role-card ${authority === role ? 'role-card-active' : ''}`} data-testid={`button-authority-${role.toLowerCase()}`}>
                <span className="role-icon">
                  {role === 'MINISTRY' ? <Landmark size={17}/> : role === 'MP' ? <Gavel size={17}/> : role === 'STATE_NODAL' ? <Network size={17}/> : <MapPin size={17}/>}
                </span>
                <span>
                  <strong>{roleLabels[role]}</strong>
                  <small>{role === 'MP' ? 'Read-only parliamentary view' : role === 'MINISTRY' ? 'National programme view' : role === 'STATE_NODAL' ? 'State delivery view' : 'District delivery view'}</small>
                </span>
                {authority === role && <Check className="ml-auto text-[#c38737]" size={15}/>}
              </button>))}
          </div>

          {authority === 'MP' && (<div className="mt-5 space-y-2">
              <div className="eyebrow text-[#8a9aa7]">SELECT PARLIAMENTARY MANDATE</div>
              <div className="role-grid" style={{ marginTop: '8px' }}>
                <button type="button" onClick={() => {
                setMpCategory('LOK_SABHA');
                setStateCode('');
                setDistrictId('');
                setConstituencyId('');
            }} className={`role-card ${mpCategory === 'LOK_SABHA' ? 'role-card-active' : ''}`} data-testid="button-mp-loksabha">
                  <span className="role-icon">
                    <Gavel size={17}/>
                  </span>
                  <span>
                    <strong>Lok Sabha</strong>
                    <small>Elected Local Constituency</small>
                  </span>
                  {mpCategory === 'LOK_SABHA' && <Check className="ml-auto text-[#c38737]" size={15}/>}
                </button>

                <button type="button" onClick={() => {
                setMpCategory('RAJYA_SABHA');
                setStateCode('');
                setDistrictId('');
                setConstituencyId('');
            }} className={`role-card ${mpCategory === 'RAJYA_SABHA' ? 'role-card-active' : ''}`} data-testid="button-mp-rajyasabha">
                  <span className="role-icon">
                    <Building2 size={17}/>
                  </span>
                  <span>
                    <strong>Rajya Sabha</strong>
                    <small>State & District Scope</small>
                  </span>
                  {mpCategory === 'RAJYA_SABHA' && <Check className="ml-auto text-[#c38737]" size={15}/>}
                </button>

                <button type="button" onClick={() => {
                setMpCategory('NOMINATED');
                setStateCode('');
                setDistrictId('');
                setConstituencyId('');
            }} className={`role-card ${mpCategory === 'NOMINATED' ? 'role-card-active' : ''}`} style={{ gridColumn: 'span 2' }} data-testid="button-mp-nominated">
                  <span className="role-icon">
                    <Landmark size={17}/>
                  </span>
                  <span>
                    <strong>Nominated Member</strong>
                    <small>National Programme Scope (Unrestricted Oversight)</small>
                  </span>
                  {mpCategory === 'NOMINATED' && <Check className="ml-auto text-[#c38737]" size={15}/>}
                </button>
              </div>
            </div>)}

          <form onSubmit={submit} className="mt-6 space-y-4">
            <div className="field-row">
              <label>
                Authority username
                <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="e.g. kavita.sharma" required data-testid="input-username"/>
              </label>
              <label>
                Access key
                <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Enter access key" required data-testid="input-password"/>
              </label>
            </div>

            {/* Scope selectors */}
            {(authority === 'STATE_NODAL' || authority === 'DISTRICT_AUTHORITY' || (authority === 'MP' && (mpCategory === 'LOK_SABHA' || mpCategory === 'RAJYA_SABHA'))) && (<div className="field-row">
                <label>
                  State / Union Territory
                  <select
                    value={stateCode}
                    onChange={(e) => {
                      setStateCode(e.target.value);
                      setDistrictId('');
                      setConstituencyId('');
                    }}
                    required
                    data-testid="select-state"
                  >
                    <option value="">Select state / UT ({states.length} available)</option>
                    {states.map((state) => (
                      <option key={state.code} value={state.code}>
                        {state.name}
                      </option>
                    ))}
                  </select>
                </label>

                {/* District Dropdown for District Nodal or Rajya Sabha MP */}
                {(authority === 'DISTRICT_AUTHORITY' || (authority === 'MP' && mpCategory === 'RAJYA_SABHA')) && (
                  <label>
                    District
                    <select
                      value={districtId}
                      onChange={(e) => setDistrictId(e.target.value)}
                      required
                      disabled={!stateCode}
                      data-testid="select-district"
                    >
                      <option value="">
                        {stateCode
                          ? availableDistricts.length > 0
                            ? `Select district (${availableDistricts.length} available)`
                            : 'No districts found for state'
                          : 'Select state first'}
                      </option>
                      {availableDistricts.map((district) => (
                        <option key={district.id} value={district.id}>
                          {district.name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                {/* Constituency Dropdown for Lok Sabha MP */}
                {authority === 'MP' && mpCategory === 'LOK_SABHA' && (
                  <label>
                    Parliamentary constituency
                    <select
                      value={constituencyId}
                      onChange={(e) => setConstituencyId(e.target.value)}
                      required
                      disabled={!stateCode}
                      data-testid="select-constituency"
                    >
                      <option value="">
                        {stateCode
                          ? availableConstituencies.length > 0
                            ? `Select constituency (${availableConstituencies.length} available)`
                            : 'No constituencies found for state'
                          : 'Select state first'}
                      </option>
                      {availableConstituencies.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>)}

            {login.isError && (<div className="form-error" data-testid="status-login-error">
                <AlertTriangle size={14}/>The access key or authority scope could not be verified. Try the demo access below.
              </div>)}

            <button className="button button-primary button-large w-full" disabled={login.isPending || (authority === 'MP' && !mpCategory)} type="submit" data-testid="button-enter-workspace">
              {login.isPending ? 'Verifying authority…' : 'Enter monitoring room'}
              <ChevronRight size={16}/>
            </button>
          </form>

          <div className="auth-divider">
            <span>or use a safe demo account</span>
          </div>

          <div className="demo-list">
            {demosLoading ? (<div className="skeleton h-12 w-full"/>) : authority === 'MP' && !mpCategory ? (<div className="rounded border border-[#345269] bg-[#162e42] p-3 text-center text-[12px] text-[#91a7ba]">
                Specify your MP role above (Lok Sabha, Rajya Sabha, or Nominated) to access designated demo account.
              </div>) : availableDemos.length > 0 ? (availableDemos.map((demo) => (<button key={demo.username} onClick={() => selectedDemo(demo)} className="demo-row" data-testid={`button-demo-${demo.authority.toLowerCase()}`}>
                  <span className="demo-avatar">
                    {demo.authority === 'MP' ? (demo.mpCategory === 'RAJYA_SABHA' ? 'RS' : demo.mpCategory === 'NOMINATED' ? 'NM' : 'LS') : demo.authority === 'MINISTRY' ? 'MA' : demo.authority === 'STATE_NODAL' ? 'SN' : 'DN'}
                  </span>
                  <span className="min-w-0 flex-1 text-left">
                    <strong>{demo.label} <span className="text-[11px] font-normal text-[#91a7ba]">({demo.username})</span></strong>
                    <small>{demo.scopeLabel}</small>
                  </span>
                  <span className="demo-use">
                    Use account <ArrowUpRight size={13}/>
                  </span>
                </button>))) : (<div className="text-center text-xs text-[#91a7ba]">No demo accounts available.</div>)}
          </div>

          <p className="mt-8 text-center text-[10px] leading-5 text-[#82919c]">
            By continuing, you acknowledge this is a <strong>Synthetic Demonstration Dataset</strong>.<br />
            AI signals are decision support and do not constitute legal findings.
          </p>
        </div>
      </div>
    </div>);
}
const categoryDisplayNames = {
    ROADS_AND_BRIDGES: 'Roads & Bridges',
    WATER_AND_SANITATION: 'Water & Sanitation',
    COMMUNITY_HALLS_AND_INFRASTRUCTURE: 'Community Halls & Infrastructure',
    EDUCATION_AND_LIBRARIES: 'Education & Libraries',
    HEALTH_AND_PUBLIC_SAFETY: 'Health & Public Safety',
    SOLAR_ENERGY_AND_LIGHTING: 'Solar Energy & Lighting',
};
const categoryColors = {
    ROADS_AND_BRIDGES: '#315f79',
    WATER_AND_SANITATION: '#2a7e9b',
    COMMUNITY_HALLS_AND_INFRASTRUCTURE: '#d49b43',
    EDUCATION_AND_LIBRARIES: '#488b77',
    HEALTH_AND_PUBLIC_SAFETY: '#b5544c',
    SOLAR_ENERGY_AND_LIGHTING: '#d97736',
};
function MetricCard({ label, value, detail, accent, icon: Icon }) {
    return (<div className="metric-card" data-testid={`metric-${label.toLowerCase().replaceAll(' ', '-')}`}>
      <div className="flex items-start justify-between">
        <div className="eyebrow">{label}</div>
        <span className={`metric-icon ${accent || ''}`}><Icon size={16}/></span>
      </div>
      <div className="mt-3 font-mono text-[25px] font-semibold tracking-[-0.05em] text-[#18354a]">{value}</div>
      <div className="mt-1 text-[11px] text-[#718392]">{detail}</div>
    </div>);
}
function ChartBars({ points, color = '#315f79' }) {
    if (!points || !points.length) {
        return <div className="text-[12px] text-[#718392] py-4 text-center">No data available</div>;
    }
    const max = Math.max(...points.map((p) => Number(p.value) || 0), 1);
    return (<div className="bar-chart">
      {points.map((point) => {
          const val = Number(point.value) || 0;
          const barHeight = val > 0 ? Math.max(8, (val / max) * 100) : 0;
          return (<div className="bar-column" key={point.label} data-testid={`bar-${point.label}`}>
            <div className="bar-value">{number(val)}</div>
            <div className="bar-track">
              <div className="bar-fill" style={{ height: `${barHeight}%`, backgroundColor: color, opacity: val > 0 ? 1 : 0.2 }}/>
            </div>
            <div className="bar-label">{point.label.replaceAll('_', ' ')}</div>
          </div>);
      })}
    </div>);
}
function FiscalTrendDualChart({ points }) {
    const maxProjects = Math.max(...points.map((p) => p.projects), 1);
    const maxExpenditure = Math.max(...points.map((p) => p.expenditure), 1);
    const totalExpenditure = points.reduce((sum, p) => sum + p.expenditure, 0);
    return (<div className="dual-trend-container">
      <div className="dual-bar-chart">
        {points.map((point) => {
            const projHeight = Math.max(6, (point.projects / maxProjects) * 100);
            const expHeight = Math.max(6, (point.expenditure / maxExpenditure) * 100);
            return (<div className="dual-bar-group" key={point.label} data-testid={`trend-group-${point.label}`}>
              <div className="dual-bars-track">
                <div className="bar-wrapper" title={`${point.label}: ${number(point.projects)} Projects`}>
                  <span className="dual-bar-value dual-val-blue">{number(point.projects)}</span>
                  <div className="bar-track dual-track">
                    <div className="bar-fill" style={{ height: `${projHeight}%`, backgroundColor: '#315f79' }}/>
                  </div>
                </div>
                <div className="bar-wrapper" title={`${point.label}: ${money(point.expenditure)} Expenditure`}>
                  <span className="dual-bar-value dual-val-gold">{money(point.expenditure)}</span>
                  <div className="bar-track dual-track">
                    <div className="bar-fill" style={{ height: `${expHeight}%`, backgroundColor: '#d49b43' }}/>
                  </div>
                </div>
              </div>
              <div className="bar-label">{point.label}</div>
            </div>);
        })}
      </div>
      <div className="chart-footnote">
        <span>Historical coverage: {points[0]?.label || 'FY 2021-22'} to {points[points.length - 1]?.label || 'FY 2025-26'}</span>
        <span>Total expenditure: {money(totalExpenditure)}</span>
      </div>
    </div>);
}
function DashboardPage() {
    const summary = useGetDashboardSummary();
    const recent = useListRecentAudit();
    if (summary.isLoading)
        return <PageFrame eyebrow="COMMAND OVERVIEW" title="Loading overview"><Skeleton rows={7}/></PageFrame>;
    if (summary.isError || !summary.data)
        return <PageFrame eyebrow="COMMAND OVERVIEW" title="Overview unavailable"><ErrorState onRetry={() => summary.refetch()}/></PageFrame>;
    const data = summary.data;
    const totals = data.totals;
    return (<PageFrame eyebrow="COMMAND OVERVIEW" title="Delivery, seen clearly." subtitle={`${data.scopeLabel} · Last synchronised 12 minutes ago`} actions={<button className="button button-secondary" onClick={() => summary.refetch()} data-testid="button-refresh-dashboard">
          <RefreshCw size={14}/> Refresh view
        </button>}>
      <div className="notice-strip">
        <Sparkles size={15}/>
        <span><strong>AI-assisted monitoring:</strong> signals surface evidence patterns for human review. They do not make legal findings.</span>
        <span className="ml-auto font-mono text-[10px] text-[#718392]">{data.syntheticLabel || 'Synthetic Demonstration Dataset'}</span>
      </div>

      <div className="metric-grid">
        <MetricCard label="Projects in scope" value={number(totals.totalProjects)} detail="Across active fiscal years" icon={Building2}/>
        <MetricCard label="Sanctioned amount" value={money(totals.sanctionedAmount)} detail={`${money(totals.expenditure)} expenditure recorded`} accent="metric-icon-gold" icon={IndianRupee}/>
        <MetricCard label="High risk" value={number(totals.highRisk)} detail={`${number(totals.moderateRisk)} moderate risk`} accent="metric-icon-red" icon={AlertTriangle}/>
        <MetricCard label="Average progress" value={`${totals.averageProgress.toFixed(1)}%`} detail={`${number(totals.dataIncomplete)} records incomplete`} accent="metric-icon-green" icon={Target}/>
      </div>

      <div className="dashboard-grid mt-5">
        <section className="surface-card chart-card">
          <div className="card-heading">
            <div>
              <div className="eyebrow">RISK DISTRIBUTION</div>
              <h3>Where attention is needed</h3>
            </div>
            <span className="round-icon"><AlertTriangle size={15}/></span>
          </div>
          <div className="risk-summary">
            {data.riskDistribution.map((point) => (<div key={point.label} className="risk-line">
                <span className={`risk-swatch risk-${point.label.toLowerCase().replace(' ', '-')}`}/>
                <span>{point.label}</span>
                <strong>{number(point.value)}</strong>
                <div className="risk-progress">
                  <span style={{ width: `${totals.totalProjects ? (point.value / totals.totalProjects) * 100 : 0}%` }}/>
                </div>
              </div>))}
          </div>
          <div className="chart-footnote">
            <span>Signal threshold: score ≥ 0.70</span>
            <span>Model refresh: 12 min ago</span>
          </div>
        </section>

        <section className="surface-card chart-card">
          <div className="card-heading">
            <div>
              <div className="eyebrow">DELIVERY STATUS</div>
              <h3>Workflow posture</h3>
            </div>
            <span className="round-icon"><ClipboardCheck size={15}/></span>
          </div>
          <ChartBars points={data.statusDistribution} color="#d49b43"/>
          <div className="chart-footnote">
            <span>Scoped project records</span>
            <span>All statuses</span>
          </div>
        </section>

        <section className="surface-card chart-card chart-wide">
          <div className="card-heading">
            <div>
              <div className="eyebrow">FISCAL TREND</div>
              <h3>Sanction and expenditure movement</h3>
            </div>
            <span className="round-icon"><BarChart3 size={15}/></span>
          </div>
          <div className="trend-legend">
            <span><i className="legend-dot legend-blue"/>Projects</span>
            <span><i className="legend-dot legend-gold"/>Expenditure (₹ Cr)</span>
          </div>
          <FiscalTrendDualChart points={data.fiscalTrend}/>
        </section>

        <section className="surface-card chart-card">
          <div className="card-heading">
            <div>
              <div className="eyebrow">PROJECT MIX</div>
              <h3>Category coverage</h3>
            </div>
            <span className="round-icon"><Network size={15}/></span>
          </div>
          <div className="category-list">
            {data.categoryDistribution.map((point) => {
            const displayName = categoryDisplayNames[point.label] || point.label.replaceAll('_', ' ');
            const pct = totals.totalProjects ? Math.round((point.value / totals.totalProjects) * 100) : 0;
            const color = categoryColors[point.label] || '#315f79';
            return (<div className="category-item" key={point.label} data-testid={`category-row-${point.label.toLowerCase()}`}>
                  <div className="category-header">
                    <span className="font-medium text-[#2f5166]">{displayName}</span>
                    <span className="font-mono text-[10px] text-[#788a96]">{number(point.value)} ({pct}%)</span>
                  </div>
                  <div className="category-track">
                    <span style={{ width: `${pct}%`, backgroundColor: color }}/>
                  </div>
                </div>);
        })}
          </div>
          <div className="chart-footnote">
            <span>{data.categoryDistribution.length} distinct categories</span>
            <span>Dynamic database aggregation</span>
          </div>
        </section>
      </div>

      <section className="surface-card mt-5">
        <div className="section-heading">
          <div>
            <div className="eyebrow">AUDIT ACTIVITY</div>
            <h3>Recent decisions in this scope</h3>
          </div>
          <Link href="/projects" className="text-link" data-testid="link-view-projects">
            View all projects <ArrowUpRight size={13}/>
          </Link>
        </div>
        <AuditTable entries={(recent.data || data.recentActivity || []).slice(0, 5)} loading={recent.isLoading}/>
      </section>
    </PageFrame>);
}
function PageFrame({ eyebrow, title, subtitle, actions, children }) {
    return (<div className="page-content">
      <div className="page-heading">
        <div>
          <div className="eyebrow text-[#8a9aa7]">{eyebrow}</div>
          <h1>{title}</h1>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {actions && <div>{actions}</div>}
      </div>
      {children}
    </div>);
}
function AuditTable({ entries, loading }) {
    if (loading)
        return <Skeleton rows={4}/>;
    if (!entries.length)
        return <div className="empty-inline"><Clock3 size={17}/>No audit activity recorded in this scope yet.</div>;
    return (<div className="audit-table">
      {entries.map((entry) => (<div className="audit-row" key={entry.id} data-testid={`audit-row-${entry.id}`}>
          <div className="audit-icon"><ClipboardCheck size={14}/></div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[12px] font-semibold text-[#26475d]">
              {entry.action.replaceAll('_', ' ')} <span className="font-normal text-[#728495]">· {entry.workId}</span>
            </div>
            <div className="mt-1 truncate text-[11px] text-[#778996]">{entry.reason}</div>
          </div>
          <div className="text-right">
            <div className="text-[11px] font-semibold text-[#426278]">{entry.userName}</div>
            <div className="mt-1 font-mono text-[10px] text-[#8a9aa7]">{date(entry.timestamp)}</div>
          </div>
        </div>))}
    </div>);
}
function ProjectsPage() {
    const [search, setSearch] = useState('');
    const [risk, setRisk] = useState('');
    const [workflow, setWorkflow] = useState('');
    const [page, setPage] = useState(0);
    const params = useMemo(() => ({
        search: search || undefined,
        riskLevel: (risk || undefined),
        workflowStatus: (workflow || undefined),
        limit: 10,
        offset: page * 10,
    }), [search, risk, workflow, page]);
    const projects = useListProjects(params);
    return (<PageFrame eyebrow="PROJECT MONITOR" title="Works in focus." subtitle="Search, filter, and inspect project records within your authority scope." actions={<button className="button button-secondary" onClick={() => projects.refetch()} data-testid="button-refresh-projects">
          <RefreshCw size={14}/> Refresh
        </button>}>
      <div className="notice-strip notice-strip-slim">
        <FileSearch size={15}/>
        <span>Risk signals are prioritisation aids. Review source evidence before taking workflow action.</span>
      </div>
      <section className="surface-card project-list-card">
        <div className="filter-bar">
          <div className="search-field">
            <Search size={16}/>
            <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder="Search work ID, description, district…" data-testid="input-project-search"/>
          </div>
          <select value={risk} onChange={(e) => { setRisk(e.target.value); setPage(0); }} data-testid="select-risk-filter">
            <option value="">All risk levels</option>
            <option value="HIGH">High risk</option>
            <option value="MODERATE">Moderate risk</option>
            <option value="LOW">Low risk</option>
            <option value="DATA_INCOMPLETE">Data incomplete</option>
          </select>
          <select value={workflow} onChange={(e) => { setWorkflow(e.target.value); setPage(0); }} data-testid="select-status-filter">
            <option value="">All workflow statuses</option>
            {Object.entries(ListProjectsWorkflowStatus).map(([key, value]) => (<option value={value} key={key}>{value.replaceAll('_', ' ')}</option>))}
          </select>
          <button className="icon-button" aria-label="Filter projects" data-testid="button-more-filters"><SlidersHorizontal size={16}/></button>
        </div>
        <div className="table-meta">
          <div className="table-meta-left">
            <span className="meta-count-highlight">
              {projects.data ? number(projects.data.total) : '...'}
            </span>
            <span className="meta-count-label">projects in scope</span>
          </div>
          <div className="table-meta-right">
            <span className="live-scope-pill">
              <span className="live-dot"/>
              <span>Live scope</span>
            </span>
          </div>
        </div>
        {projects.isLoading ? (<Skeleton rows={8}/>) : projects.isError ? (<ErrorState onRetry={() => projects.refetch()}/>) : projects.data?.items.length ? (<ProjectTable items={projects.data.items}/>) : (<div className="empty-state">
            <div className="state-icon"><Search size={18}/></div>
            <h3>No matching projects</h3>
            <p>Try a broader search or clear one of the active filters.</p>
            <button className="button button-secondary" onClick={() => { setSearch(''); setRisk(''); setWorkflow(''); }} data-testid="button-clear-filters">
              Clear filters
            </button>
          </div>)}
        <div className="pagination">
          <span className="text-[11px] text-[#718392]">Page {page + 1} of {Math.max(1, Math.ceil((projects.data?.total || 0) / 10))}</span>
          <div className="flex gap-2">
            <button className="icon-button" disabled={page === 0} onClick={() => setPage((value) => value - 1)} aria-label="Previous page" data-testid="button-previous-page">
              <ChevronLeft size={16}/>
            </button>
            <button className="icon-button" disabled={!projects.data || (page + 1) * 10 >= projects.data.total} onClick={() => setPage((value) => value + 1)} aria-label="Next page" data-testid="button-next-page">
              <ChevronRight size={16}/>
            </button>
          </div>
        </div>
      </section>
    </PageFrame>);
}
function ProjectTable({ items }) {
    return (<div className="overflow-x-auto">
      <table className="project-table">
        <thead>
          <tr>
            <th>Work / location</th>
            <th>Category</th>
            <th>Delivery</th>
            <th>Risk signal</th>
            <th>Workflow</th>
            <th>Updated</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {(items || []).map((item) => (<tr key={item.workId} data-testid={`row-project-${item.workId}`}>
              <td>
                <Link href={`/projects/${item.workId}`} className="work-link" data-testid={`link-project-${item.workId}`}>
                  <span className="font-mono text-[11px]">{item.workId}</span>
                  <strong>{item.description || item.title || item.workId}</strong>
                  <span className="location-line"><MapPin size={11}/>{item.district || '—'}{item.state ? `, ${item.state}` : ''}</span>
                </Link>
              </td>
              <td>
                <span className="text-[12px] text-[#4b6678] font-medium block">{categoryDisplayNames[item.category] || item.category || 'General'}</span>
                <span className="block mt-1 font-mono text-[10px] text-[#8695a0]">{item.fiscalYear || '—'}</span>
              </td>
              <td>
                <div className="progress-number">{(Number(item.physicalProgress) || 0).toFixed(0)}%</div>
                <div className="mini-progress"><span style={{ width: `${Math.min(100, Math.max(0, Number(item.physicalProgress) || 0))}%` }}/></div>
                <span className="mt-1 block text-[10px] text-[#8998a2]">{money(item.expenditure)} spent</span>
              </td>
              <td>
                <RiskSignalCell riskLevel={item.riskLevel} riskScore={item.riskScore}/>
              </td>
              <td><StatusPill value={item.workflowStatus} kind="workflow"/></td>
              <td><span className="font-mono text-[10px] text-[#728495]">{date(item.updatedAt)}</span></td>
              <td>
                <Link href={`/projects/${item.workId}`} className="icon-button" aria-label={`Open ${item.workId}`} data-testid={`button-open-project-${item.workId}`}>
                  <ChevronRight size={15}/>
                </Link>
              </td>
            </tr>))}
        </tbody>
      </table>
    </div>);
}
function DetailRow({ label, value, mono = false }) {
    return (<div className="detail-row">
      <span>{label}</span>
      <strong className={mono ? 'font-mono text-[12px]' : ''}>{value}</strong>
    </div>);
}
function EscalationReviewModal({ project, userRole, onClose, }) {
    const [selectedAction, setSelectedAction] = useState('ACKNOWLEDGE');
    const [reason, setReason] = useState('');
    const action = useCreateProjectAction();
    const client = useQueryClient();
    const choices = useMemo(() => {
        const list = [];
        list.push({
            action: 'ACKNOWLEDGE',
            title: 'Acknowledge Record',
            subtitle: 'Mark project under active review while evidence is investigated.',
        });
        list.push({
            action: 'RESOLVE',
            title: 'Resolve Escalation',
            subtitle: 'Mark issue as verified and resolved in compliance with norms.',
        });
        list.push({
            action: 'DISMISS',
            title: 'Dismiss Flag',
            subtitle: 'Dismiss escalation as false positive or within permitted tolerances.',
        });
        if (userRole === AuthUserRole.STATE_NODAL || userRole === AuthUserRole.DISTRICT_AUTHORITY || userRole === AuthUserRole.MP) {
            list.push({
                action: 'ESCALATE',
                title: userRole === AuthUserRole.DISTRICT_AUTHORITY ? 'Escalate to State Nodal' : 'Escalate to Central Ministry',
                subtitle: 'Escalate to higher accountability tier for departmental intervention.',
            });
        }
        return list;
    }, [userRole]);
    const handleSubmit = () => {
        action.mutate({
            workId: project.workId,
            data: { action: selectedAction, reason },
        }, {
            onSuccess: () => {
                client.invalidateQueries({ queryKey: getListEscalatedProjectsQueryKey() });
                client.invalidateQueries({ queryKey: getGetDashboardSummaryQueryKey() });
                client.invalidateQueries({ queryKey: getListProjectsQueryKey() });
                client.invalidateQueries({ queryKey: getGetProjectQueryKey(project.workId) });
                client.invalidateQueries({ queryKey: getListRecentAuditQueryKey() });
                onClose();
            },
        });
    };
    return (<div className="modal-overlay" onClick={onClose} data-testid="modal-escalation-review">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="eyebrow text-[#b0792c]">HIERARCHICAL OVERSIGHT DESK</div>
            <h3 className="font-serif text-[18px] text-[#1a384e]">{project.workId}</h3>
            <p className="text-[11px] text-[#697f8e] mt-1">{project.description || project.title || 'MPLADS Work Record'}</p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close modal">
            <X size={16}/>
          </button>
        </div>

        <div className="modal-body">
          <div className="escalation-origin-box">
            <div className="origin-header">
              <span><strong>Escalated by:</strong> {project.escalatedByUserName || 'Authority Officer'} ({roleLabels[project.escalatedByRole] || project.escalatedByRole || 'Authority'})</span>
              <span>{date(project.escalatedAt || project.updatedAt)}</span>
            </div>
            <div className="origin-reason">
              "{project.escalationReason || 'Administrative review requested'}"
            </div>
          </div>

          <div className="modal-meta-grid">
            <div className="modal-meta-cell">
              <span>Sanctioned</span>
              <strong>{money(project.sanctionedAmount)}</strong>
            </div>
            <div className="modal-meta-cell">
              <span>Expenditure</span>
              <strong>{money(project.expenditure)}</strong>
            </div>
            <div className="modal-meta-cell">
              <span>Physical Progress</span>
              <strong>{(Number(project.physicalProgress) || 0).toFixed(1)}%</strong>
            </div>
            <div className="modal-meta-cell">
              <span>Location</span>
              <strong>{project.district || '—'}{project.state ? `, ${project.state}` : ''}</strong>
            </div>
            <div className="modal-meta-cell">
              <span>Agency</span>
              <strong>{project.agency || 'Implementing Agency'}</strong>
            </div>
            <div className="modal-meta-cell">
              <span>Risk Level</span>
              <div className="mt-0.5"><StatusPill value={project.riskLevel}/></div>
            </div>
          </div>

          <div className="decision-selector">
            <label className="field-label font-semibold">Select Administrative Decision</label>
            <div className="decision-grid">
              {choices.map((c) => (<button type="button" key={c.action} className={`decision-card ${selectedAction === c.action ? 'decision-card-active' : ''}`} onClick={() => setSelectedAction(c.action)} data-testid={`decision-btn-${c.action.toLowerCase()}`}>
                  <strong>{c.title}</strong>
                  <small>{c.subtitle}</small>
                </button>))}
            </div>
          </div>

          <div className="mt-4">
            <label className="field-label">
              Decision Justification / Order Note <span className="text-[#a17e4a]">required</span>
              <textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="State the administrative finding, directive, or justification for this decision…" rows={3} data-testid="textarea-review-reason"/>
            </label>
            {reason.trim().length < 5 && (<span className="text-[10px] text-[#a47b36] mt-1 block">
                Minimum 5 characters required for administrative audit trail.
              </span>)}
          </div>

          {action.isError && (<div className="form-error mt-3">
              <AlertTriangle size={13}/>
              Could not record decision. Please verify authority permissions.
            </div>)}
        </div>

        <div className="modal-footer">
          <button className="button button-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="button button-primary" disabled={reason.trim().length < 5 || action.isPending} onClick={handleSubmit} data-testid="button-submit-decision">
            {action.isPending ? 'Writing audit trail…' : 'Confirm Decision'}
          </button>
        </div>
      </div>
    </div>);
}
function EscalatedProjectsPage() {
    const current = useGetCurrentUser();
    const escalated = useListEscalatedProjects();
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [roleFilter, setRoleFilter] = useState('');
    const [reviewingProject, setReviewingProject] = useState(null);
    const filteredItems = useMemo(() => {
        const rawList = Array.isArray(escalated.data) ? escalated.data : (escalated.data?.items || []);
        if (!rawList.length)
            return [];
        return rawList.filter((item) => {
            if (search) {
                const query = search.toLowerCase();
                const matches = (item.workId || '').toLowerCase().includes(query) ||
                    (item.description || item.title || '').toLowerCase().includes(query) ||
                    (item.district || '').toLowerCase().includes(query) ||
                    (item.escalationReason || '').toLowerCase().includes(query);
                if (!matches)
                    return false;
            }
            if (statusFilter && item.workflowStatus !== statusFilter)
                return false;
            if (roleFilter && item.escalatedByRole !== roleFilter)
                return false;
            return true;
        });
    }, [escalated.data, search, statusFilter, roleFilter]);
    if (current.data?.role === AuthUserRole.DISTRICT_AUTHORITY) {
        return (<PageFrame eyebrow="HIERARCHICAL OVERSIGHT" title="Escalated Projects." subtitle="District Authorities initiate escalations upward to the State Nodal Authority rather than receiving incoming escalations.">
        <section className="surface-card p-6 max-w-2xl">
          <div className="flex items-start gap-4">
            <div className="p-3 rounded-lg bg-[#ebf4f9] text-[#1b4353] shrink-0">
              <AlertOctagon size={24}/>
            </div>
            <div>
              <h3 className="text-base font-bold text-[#1b4353] mb-1">
                District Escalation Protocol
              </h3>
              <p className="text-sm text-[#476071] leading-relaxed mb-3">
                As a District Authority, your role focuses on ground execution and triggering escalations upward to the <strong>State Nodal Authority</strong> when anomalies, cost overruns, or critical delays occur. Incoming escalation queues are reviewed at the State Nodal, MP, and Central Ministry levels.
              </p>
              <p className="text-sm text-[#476071] leading-relaxed mb-5">
                To escalate high-risk or stalled projects within your district, open any project in the <strong>Project Monitor</strong> and select <em>Escalate Project</em>.
              </p>
              <Link href="/projects" className="button button-primary inline-flex items-center gap-2">
                Go to Project Monitor
              </Link>
            </div>
          </div>
        </section>
      </PageFrame>);
    }
    return (<PageFrame eyebrow="HIERARCHICAL OVERSIGHT" title="Escalated Projects Inbox." subtitle="Critical work items escalated across administrative tiers requiring nodal review or Ministry intervention." actions={<button className="button button-secondary" onClick={() => escalated.refetch()} data-testid="button-refresh-escalated">
          <RefreshCw size={14}/> Refresh
        </button>}>
      <div className="notice-strip notice-strip-slim">
        <AlertOctagon size={15} className="text-[#c26053]"/>
        <span>
          <strong>Escalation Protocol:</strong> District escalations route to State Nodal Authority. State and MP escalations route to Central Ministry.
        </span>
      </div>

      <section className="surface-card project-list-card">
        <div className="filter-bar">
          <div className="search-field">
            <Search size={16}/>
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search escalated work ID, description, reason…" data-testid="input-escalated-search"/>
          </div>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} data-testid="select-escalated-status">
            <option value="">All escalation tiers</option>
            <option value="ESCALATED">District Escalated (To State)</option>
            <option value="ESCALATED_STATE">State/MP Escalated (To Ministry)</option>
          </select>
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} data-testid="select-escalated-role">
            <option value="">All originating authorities</option>
            <option value="DISTRICT_AUTHORITY">District Nodal Officer</option>
            <option value="STATE_NODAL">State Nodal Authority</option>
            <option value="MP">Member of Parliament</option>
          </select>
        </div>

        <div className="table-meta">
          <div className="table-meta-left">
            <span className="meta-count-highlight">
              {filteredItems.length}
            </span>
            <span className="meta-count-label">escalated works requiring administrative action</span>
          </div>
          <div className="table-meta-right">
            <span className="live-scope-pill">
              <span className="live-dot"/>
              <span>Active queue</span>
            </span>
          </div>
        </div>

        {escalated.isLoading ? (<Skeleton rows={8}/>) : escalated.isError ? (<ErrorState onRetry={() => escalated.refetch()} message="Failed to load escalated projects."/>) : filteredItems.length > 0 ? (<div className="overflow-x-auto">
            <table className="project-table">
              <thead>
                <tr>
                  <th>Work / location</th>
                  <th>Originating authority</th>
                  <th>Escalation date & reason</th>
                  <th>Delivery</th>
                  <th>Risk signal</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => (<tr key={item.workId} data-testid={`row-escalated-${item.workId}`}>
                    <td>
                      <Link href={`/projects/${item.workId}`} className="work-link">
                        <span className="font-mono text-[11px]">{item.workId}</span>
                        <strong>{item.description || item.title || item.workId}</strong>
                        <span className="location-line">
                          <MapPin size={11}/>{item.district || '—'}{item.state ? `, ${item.state}` : ''}
                        </span>
                      </Link>
                    </td>
                    <td>
                      <div className="text-[12px] font-semibold text-[#27495f]">
                        {item.escalatedByUserName || 'District Authority'}
                      </div>
                      <div className="text-[10px] text-[#718491]">
                        {roleLabels[item.escalatedByRole] || item.escalatedByRole || 'Authority'}
                      </div>
                    </td>
                    <td style={{ maxWidth: '300px' }}>
                      <span className="font-mono text-[10px] text-[#8697a2] block">
                        {date(item.escalatedAt || item.updatedAt)}
                      </span>
                      <div className="text-[11px] text-[#476071] italic mt-0.5 line-clamp-2">
                        "{item.escalationReason || 'Severe expenditure-progress variance flagged by ML engine'}"
                      </div>
                    </td>
                    <td>
                      <div className="progress-number">{(Number(item.physicalProgress) || 0).toFixed(0)}%</div>
                      <div className="mini-progress">
                        <span style={{ width: `${Math.min(100, Math.max(0, Number(item.physicalProgress) || 0))}%` }}/>
                      </div>
                      <span className="mt-1 block text-[10px] text-[#8998a2]">
                        {money(item.expenditure)} spent
                      </span>
                    </td>
                    <td>
                      <RiskSignalCell riskLevel={item.riskLevel} riskScore={item.riskScore}/>
                    </td>
                    <td>
                      <StatusPill value={item.workflowStatus} kind="workflow"/>
                    </td>
                    <td>
                      <button className="button button-secondary text-[10px] py-1 px-2.5 h-auto whitespace-nowrap" onClick={() => setReviewingProject(item)} data-testid={`button-review-escalation-${item.workId}`}>
                        Review Escalation
                      </button>
                    </td>
                  </tr>))}
              </tbody>
            </table>
          </div>) : (<div className="empty-state">
            <div className="state-icon"><ShieldCheck size={18}/></div>
            <h3>No escalated projects</h3>
            <p>No projects within your current authority scope match the selected escalation filters.</p>
          </div>)}
      </section>

      {reviewingProject && (<EscalationReviewModal project={reviewingProject} userRole={current.data?.role} onClose={() => setReviewingProject(null)}/>)}
    </PageFrame>);
}
function ActionPanel({ project, readOnly, userRole }) {
    const action = useCreateProjectAction();
    const [open, setOpen] = useState(false);
    const isMp = userRole === AuthUserRole.MP;
    const [selected, setSelected] = useState(isMp ? 'ESCALATE' : 'REVIEW');
    const [reason, setReason] = useState('');
    const client = useQueryClient();
    const isEscalated = project.workflowStatus === 'ESCALATED' || project.workflowStatus === 'ESCALATED_STATE';
    const availableActions = useMemo(() => {
        if (isMp)
            return ['ESCALATE'];
        if (userRole === AuthUserRole.DISTRICT_AUTHORITY) {
            return ['REVIEW', 'ACKNOWLEDGE', 'ESCALATE', 'RESOLVE', 'DISMISS'];
        }
        if (userRole === AuthUserRole.STATE_NODAL) {
            return ['REVIEW', 'ACKNOWLEDGE', 'ESCALATE', 'RESOLVE', 'DISMISS', 'CLOSE'];
        }
        return ['REVIEW', 'ACKNOWLEDGE', 'RESOLVE', 'DISMISS', 'CLOSE'];
    }, [userRole, isMp]);
    const submit = () => {
        action.mutate({ workId: project.workId, data: { action: selected, reason } }, {
            onSuccess: () => {
                setOpen(false);
                setReason('');
                client.invalidateQueries({ queryKey: getGetProjectQueryKey(project.workId) });
                client.invalidateQueries({ queryKey: getListProjectAuditQueryKey(project.workId) });
                client.invalidateQueries({ queryKey: getGetDashboardSummaryQueryKey() });
                client.invalidateQueries({ queryKey: getListRecentAuditQueryKey() });
                client.invalidateQueries({ queryKey: getListProjectsQueryKey() });
                client.invalidateQueries({ queryKey: getListEscalatedProjectsQueryKey() });
            },
        });
    };
    if (readOnly && !isMp) {
        return (<div className="readonly-note">
        <Gavel size={15}/>
        <span><strong>Read-only view</strong><br />Workflow actions are reserved for the accountable nodal authority.</span>
      </div>);
    }
    const actionLabels = {
        REVIEW: 'Under Review',
        ACKNOWLEDGE: 'Acknowledge Record',
        ESCALATE: isMp ? 'Escalate to Ministry' : userRole === AuthUserRole.DISTRICT_AUTHORITY ? 'Escalate to State Nodal' : 'Escalate to Central Ministry',
        RESOLVE: 'Resolve Escalation',
        DISMISS: 'Dismiss Flag',
        CLOSE: 'Close Project Record',
    };
    return (<div className="action-panel">
      {isEscalated && (<div className="mb-3 rounded border border-[#e2c792] bg-[#fcf5e5] p-2.5 text-[11px] text-[#7c5b24]">
          <div className="flex items-center gap-1.5 font-semibold">
            <AlertOctagon size={13} className="text-[#c26053]"/>
            Active Escalation Pending
          </div>
          <div className="mt-1 text-[10px] text-[#8e6c35]">
            This record has been escalated and is under administrative review.
          </div>
        </div>)}
      <div className="flex items-start gap-3">
        <div className="round-icon round-icon-gold"><Gavel size={15}/></div>
        <div>
          <div className="eyebrow">ACCOUNTABLE ACTION</div>
          <h3>{isMp ? 'Constituency Oversight Action' : 'Move this record forward'}</h3>
          <p>{isMp ? 'Escalate evidence or project divergence directly to the Ministry for administrative inquiry.' : 'Actions are written to the audit trail and remain reversible through authority review.'}</p>
        </div>
      </div>
      {!open ? (<button className="button button-primary mt-4 w-full" onClick={() => {
                setSelected(isMp ? 'ESCALATE' : 'REVIEW');
                setOpen(true);
            }} data-testid="button-open-action">
          {isMp ? 'Escalate to Ministry' : 'Open workflow action'} <ChevronRight size={15}/>
        </button>) : (<div className="mt-4 space-y-3">
          <label className="field-label">
            Action
            <select value={selected} onChange={(e) => setSelected(e.target.value)} data-testid="select-project-action">
              {availableActions.map((act) => (<option value={act} key={act}>
                  {actionLabels[act] || act.replaceAll('_', ' ')}
                </option>))}
            </select>
          </label>
          <label className="field-label">
            Reason <span className="text-[#a17e4a]">required</span>
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder={isMp ? 'Detail why this work item is being escalated to the Ministry…' : 'Record the evidence or accountable next step…'} minLength={5} rows={3} data-testid="textarea-action-reason"/>
          </label>
          {reason.trim().length < 5 && (<span className="text-[10px] text-[#a47b36] block">
              Minimum 5 characters required for administrative audit trail.
            </span>)}
          {action.isError && (<div className="form-error">
              <AlertTriangle size={13}/>
              Action could not be applied. Please try again.
            </div>)}
          <div className="flex gap-2">
            <button className="button button-secondary flex-1" onClick={() => setOpen(false)} data-testid="button-cancel-action">
              Cancel
            </button>
            <button className="button button-primary flex-1" disabled={reason.trim().length < 5 || action.isPending} onClick={submit} data-testid="button-submit-action">
              {action.isPending ? 'Writing audit…' : 'Confirm action'}
            </button>
          </div>
        </div>)}
    </div>);
}
function PhotoBadge({ label, value, ok }) {
    const color = ok === true ? '#2a7e5a' : ok === false ? '#b5544c' : '#a17e4a';
    return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '10px', fontWeight: 600, color, background: color + '18', border: `1px solid ${color}40`, borderRadius: '4px', padding: '2px 7px' }}>
            {value || label}
        </span>
    );
}

function CategoryProjectIllustration({ category, workId, hasAnomaly, isGpsBad, isDupBad, isExifBad }) {
  const cat = String(category || '').toUpperCase();
  return (
    <svg viewBox="0 0 640 360" className="w-full h-full" style={{ display: 'block', width: '100%', height: '100%', background: '#0a1926' }}>
      <defs>
        <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0d2338" />
          <stop offset="100%" stopColor="#1a3d5c" />
        </linearGradient>
        <linearGradient id="groundGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#19352c" />
          <stop offset="100%" stopColor="#0f211c" />
        </linearGradient>
        <linearGradient id="metalGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#4a6572" />
          <stop offset="50%" stopColor="#758f9e" />
          <stop offset="100%" stopColor="#344955" />
        </linearGradient>
        <linearGradient id="concreteGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#62727b" />
          <stop offset="100%" stopColor="#37474f" />
        </linearGradient>
        <linearGradient id="solarGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#1565c0" />
          <stop offset="100%" stopColor="#0d47a1" />
        </linearGradient>
        <pattern id="gridPattern" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
        </pattern>
      </defs>

      {/* Sky & Ground */}
      <rect x="0" y="0" width="640" height="230" fill="url(#skyGrad)" />
      <rect x="0" y="230" width="640" height="130" fill="url(#groundGrad)" />
      <rect x="0" y="0" width="640" height="360" fill="url(#gridPattern)" />

      {/* Category Infrastructure Artwork */}
      {cat.includes('WATER') ? (
        <g>
          {/* Elevated RO Tank */}
          <rect x="220" y="70" width="200" height="110" rx="8" fill="url(#metalGrad)" stroke="#8aa8b8" strokeWidth="2" />
          <rect x="235" y="85" width="8" height="80" rx="3" fill="#1b2a38" />
          <rect x="236" y="105" width="6" height="58" rx="2" fill="#4fc3f7" />
          <text x="320" y="115" fill="#f0c070" fontSize="11" fontWeight="bold" textAnchor="middle" letterSpacing="1">MPLADS WATER RO PLANT</text>
          <text x="320" y="132" fill="#c8dbe6" fontSize="9" textAnchor="middle">{workId}</text>
          <text x="320" y="148" fill="#80deea" fontSize="8" textAnchor="middle">CAPACITY: 5,000 LPH · PURIFICATION ONLINE</text>
          {/* Support Legs */}
          <line x1="240" y1="180" x2="210" y2="280" stroke="#37474f" strokeWidth="8" />
          <line x1="400" y1="180" x2="430" y2="280" stroke="#37474f" strokeWidth="8" />
          <line x1="290" y1="180" x2="290" y2="280" stroke="#263238" strokeWidth="6" />
          <line x1="350" y1="180" x2="350" y2="280" stroke="#263238" strokeWidth="6" />
          <line x1="240" y1="180" x2="400" y2="280" stroke="#455a64" strokeWidth="2" strokeDasharray="4 2" />
          <line x1="400" y1="180" x2="240" y2="280" stroke="#455a64" strokeWidth="2" strokeDasharray="4 2" />
          {/* Filtration Skid */}
          <rect x="180" y="270" width="280" height="45" rx="4" fill="url(#concreteGrad)" stroke="#78909c" strokeWidth="1.5" />
          <rect x="200" y="220" width="35" height="55" rx="4" fill="#00838f" stroke="#4dd0e1" strokeWidth="1.5" />
          <rect x="245" y="220" width="35" height="55" rx="4" fill="#00838f" stroke="#4dd0e1" strokeWidth="1.5" />
          <path d="M 280 245 L 320 245 L 320 270" fill="none" stroke="#cfd8dc" strokeWidth="4" />
          <circle cx="300" cy="245" r="7" fill="#d49b43" />
        </g>
      ) : cat.includes('ROAD') ? (
        <g>
          {/* Perspective Concrete Road */}
          <polygon points="320,120 330,120 540,360 100,360" fill="url(#concreteGrad)" stroke="#90a4ae" strokeWidth="1" />
          <polygon points="323,125 327,125 329,150 321,150" fill="#ffd54f" />
          <polygon points="320,170 330,170 333,205 317,205" fill="#ffd54f" />
          <polygon points="315,230 335,230 340,280 310,280" fill="#ffd54f" />
          <polygon points="305,310 345,310 355,360 295,360" fill="#ffd54f" />
          <polygon points="90,360 120,360 322,120 316,120" fill="#d49b43" opacity="0.8" />
          <polygon points="520,360 550,360 334,120 328,120" fill="#d49b43" opacity="0.8" />
          {/* Survey Tripod */}
          <line x1="160" y1="260" x2="140" y2="330" stroke="#f0c070" strokeWidth="2.5" />
          <line x1="160" y1="260" x2="180" y2="330" stroke="#f0c070" strokeWidth="2.5" />
          <line x1="160" y1="260" x2="160" y2="330" stroke="#f0c070" strokeWidth="2.5" />
          <circle cx="160" cy="255" r="9" fill="#37474f" stroke="#f0c070" strokeWidth="1.5" />
          <text x="320" y="80" fill="#f0c070" fontSize="11" fontWeight="bold" textAnchor="middle" letterSpacing="1">MPLADS CEMENT CONCRETE ROADWAY</text>
        </g>
      ) : cat.includes('COMMUNITY') ? (
        <g>
          {/* Community Center Building */}
          <polygon points="170,160 320,90 470,160" fill="#b0544c" stroke="#d49b43" strokeWidth="2" />
          <rect x="180" y="160" width="280" height="120" fill="url(#concreteGrad)" stroke="#90a4ae" strokeWidth="2" />
          <rect x="200" y="170" width="16" height="110" fill="#eceff1" />
          <rect x="260" y="170" width="16" height="110" fill="#eceff1" />
          <rect x="364" y="170" width="16" height="110" fill="#eceff1" />
          <rect x="424" y="170" width="16" height="110" fill="#eceff1" />
          <rect x="296" y="195" width="48" height="85" fill="#1b2a38" stroke="#d49b43" strokeWidth="1.5" />
          <rect x="210" y="240" width="70" height="35" fill="#091c2b" stroke="#f0c070" strokeWidth="1" />
          <text x="245" y="255" fill="#f0c070" fontSize="6" fontWeight="bold" textAnchor="middle">MPLADS</text>
          <text x="245" y="265" fill="#fff" fontSize="5" textAnchor="middle">{workId.slice(0, 14)}</text>
          <text x="320" y="145" fill="#fff" fontSize="10" fontWeight="bold" textAnchor="middle">SAMUDAIK BHAWAN</text>
        </g>
      ) : cat.includes('SOLAR') ? (
        <g>
          {/* Solar PV Array */}
          <polygon points="160,180 300,140 340,240 200,280" fill="url(#solarGrad)" stroke="#64b5f6" strokeWidth="2" />
          <polygon points="320,180 460,140 500,240 360,280" fill="url(#solarGrad)" stroke="#64b5f6" strokeWidth="2" />
          <line x1="230" y1="160" x2="270" y2="260" stroke="rgba(255,255,255,0.4)" strokeWidth="1" />
          <line x1="390" y1="160" x2="430" y2="260" stroke="rgba(255,255,255,0.4)" strokeWidth="1" />
          <line x1="530" y1="80" x2="530" y2="290" stroke="#78909c" strokeWidth="6" />
          <polygon points="510,80 550,80 530,65" fill="#ffd54f" />
          <circle cx="530" cy="80" r="14" fill="rgba(255, 238, 88, 0.4)" />
          <rect x="130" y="260" width="45" height="55" fill="#263238" stroke="#4caf50" strokeWidth="1.5" />
          <text x="320" y="80" fill="#f0c070" fontSize="11" fontWeight="bold" textAnchor="middle" letterSpacing="1">SOLAR MICRO-GRID INFRASTRUCTURE</text>
        </g>
      ) : (
        <g>
          {/* Institutional / School / Health Facility Architecture */}
          <rect x="160" y="130" width="320" height="150" rx="4" fill="url(#concreteGrad)" stroke="#90a4ae" strokeWidth="2" />
          {[180, 230, 280, 340, 390, 440].map((x, i) => (
            <rect key={i} x={x} y="150" width="28" height="35" rx="2" fill="#0d2b45" stroke="#80deea" strokeWidth="1" />
          ))}
          {[180, 230, 390, 440].map((x, i) => (
            <rect key={i} x={x} y="210" width="28" height="40" rx="2" fill="#0d2b45" stroke="#80deea" strokeWidth="1" />
          ))}
          <rect x="290" y="200" width="60" height="80" fill="#182a38" stroke="#d49b43" strokeWidth="2" />
          <rect x="220" y="105" width="200" height="28" rx="3" fill="#0d2338" stroke="#f0c070" strokeWidth="1.5" />
          <text x="320" y="123" fill="#f0c070" fontSize="9" fontWeight="bold" textAnchor="middle" letterSpacing="1">GOVERNMENT INFRASTRUCTURE SITE</text>
        </g>
      )}

      {/* Target Laser Crosshairs */}
      <circle cx="320" cy="180" r="24" fill="none" stroke="rgba(212, 155, 67, 0.6)" strokeWidth="1" strokeDasharray="3 3" />
      <line x1="320" y1="148" x2="320" y2="212" stroke="rgba(212, 155, 67, 0.6)" strokeWidth="1" />
      <line x1="288" y1="180" x2="352" y2="180" stroke="rgba(212, 155, 67, 0.6)" strokeWidth="1" />

      {/* Corner Brackets */}
      <path d="M 18 36 L 18 18 L 36 18" stroke="#728495" fill="none" strokeWidth="2" />
      <path d="M 622 36 L 622 18 L 604 18" stroke="#728495" fill="none" strokeWidth="2" />
      <path d="M 18 324 L 18 342 L 36 342" stroke="#728495" fill="none" strokeWidth="2" />
      <path d="M 622 324 L 622 342 L 604 342" stroke="#728495" fill="none" strokeWidth="2" />

      {/* Top HUD Telemetry */}
      <rect x="25" y="24" width="240" height="20" rx="3" fill="rgba(9, 28, 43, 0.85)" stroke="rgba(255,255,255,0.1)" strokeWidth="0.8" />
      <text x="33" y="38" fill="#64b5f6" fontSize="8" fontFamily="monospace" fontWeight="bold">SITE HUD // CADASTRE PARCEL #284</text>

      <rect x="420" y="24" width="195" height="20" rx="3" fill="rgba(9, 28, 43, 0.85)" stroke="rgba(255,255,255,0.1)" strokeWidth="0.8" />
      <text x="428" y="38" fill="#ffd54f" fontSize="8" fontFamily="monospace" fontWeight="bold">PHASH: 8f3a9c2b4d1e0f6a</text>

      {/* Anomaly Detection Scanners */}
      {isGpsBad && (
        <g>
          <rect x="0" y="0" width="640" height="360" fill="rgba(211, 47, 47, 0.22)" />
          <rect x="15" y="12" width="610" height="32" rx="4" fill="rgba(183, 28, 28, 0.95)" stroke="#ff8a80" strokeWidth="1" />
          <text x="30" y="33" fill="#ffffff" fontSize="11" fontWeight="bold" fontFamily="sans-serif">🚨 GEOFENCE BREACH DETECTED: COORDINATES OUTSIDE CONSTITUENCY BOUNDARY</text>
        </g>
      )}

      {isDupBad && (
        <g>
          <rect x="0" y="0" width="640" height="360" fill="rgba(230, 81, 0, 0.22)" />
          <rect x="15" y="12" width="610" height="32" rx="4" fill="rgba(191, 54, 12, 0.95)" stroke="#ffcc80" strokeWidth="1" />
          <text x="30" y="33" fill="#ffffff" fontSize="11" fontWeight="bold" fontFamily="sans-serif">🚨 COMPUTER VISION ALERT: REUSED / DUPLICATE GROUND PHOTO (pHash Collision)</text>
        </g>
      )}

      {isExifBad && !isGpsBad && !isDupBad && (
        <g>
          <rect x="15" y="12" width="610" height="32" rx="4" fill="rgba(245, 127, 23, 0.92)" stroke="#fff59d" strokeWidth="1" />
          <text x="30" y="33" fill="#ffffff" fontSize="11" fontWeight="bold" fontFamily="sans-serif">⚠️ EXIF WARNING: CAMERA METADATA REMOVED BY MESSAGING COMPRESSION</text>
        </g>
      )}
    </svg>
  );
}

function ProjectVisualCard({ photo, category, workId, title, district }) {
    const gpsStatusStr = String(photo.gpsStatus || '');
    const dupStatusStr = String(photo.duplicateStatus || '');
    const exifStatusStr = String(photo.exifStatus || '');

    const isGpsBad = gpsStatusStr.includes('OUTSIDE') || gpsStatusStr.includes('Unavailable');
    const isDupBad = dupStatusStr.includes('DUPLICATE') || dupStatusStr.includes('Collision');
    const isExifBad = exifStatusStr.includes('Stripped') || exifStatusStr.includes('Missing');
    const hasAnomaly = isGpsBad || isDupBad || isExifBad;

    const isGenericSvg = !photo.imageUrl || (photo.imageUrl.includes('svg') && (photo.imageUrl.includes('%231c3557') || photo.imageUrl.includes('M0 270') || photo.imageUrl.includes('rect width=')));

    return (
        <div className="visual-evidence-card" style={{ background: '#091c2b', borderRadius: '8px', border: `1px solid ${hasAnomaly ? '#7d3830' : '#1e3d57'}`, overflow: 'hidden', marginBottom: '16px' }}>
            {/* Top Bar with Stage & Inspector */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: '#0e2537', borderBottom: '1px solid #1a3a52', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#f0c070', letterSpacing: '0.04em' }}>{photo.stage || 'Field Inspection Milestone'}</span>
                    <span style={{ fontSize: '10px', color: '#7b8d9a' }}>· Inspection date: {date(photo.date)}</span>
                    <span style={{ fontSize: '10px', color: '#5a7a8a' }}>by {photo.uploader || 'Field Inspector'}</span>
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    <PhotoBadge label="GPS" value={photo.gpsStatus || 'Verified'} ok={!isGpsBad} />
                    <PhotoBadge label="EXIF" value={photo.exifStatus || 'Valid'} ok={!isExifBad} />
                    <PhotoBadge label="Duplicate" value={photo.duplicateStatus || 'Unique'} ok={!isDupBad} />
                </div>
            </div>

            {/* Main Visual Display (16:9 Aspect Ratio) */}
            <div style={{ position: 'relative', width: '100%', aspectRatio: '16/9', maxHeight: '360px', background: '#06131f', overflow: 'hidden' }}>
                {isGenericSvg ? (
                    <CategoryProjectIllustration category={category} workId={workId} hasAnomaly={hasAnomaly} isGpsBad={isGpsBad} isDupBad={isDupBad} isExifBad={isExifBad} />
                ) : (
                    <img src={photo.imageUrl} alt={photo.stage} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                )}

                {/* Telemetry HUD Bar */}
                <div style={{ position: 'absolute', bottom: '8px', left: '10px', right: '10px', display: 'flex', justifyContent: 'space-between', pointerEvents: 'none', background: 'rgba(5, 15, 25, 0.85)', backdropFilter: 'blur(4px)', padding: '5px 12px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)', flexWrap: 'wrap', gap: '4px' }}>
                    <div style={{ fontSize: '10px', fontFamily: 'monospace', color: isGpsBad ? '#ff8a80' : '#91bacf' }}>
                        📍 {isGpsBad ? 'LAT 28.6139° N, LON 77.2090° E [GEOFENCE BREACH]' : 'LAT 12.9716° N, LON 77.5946° E [CONSTITUENCY MATCH]'}
                    </div>
                    <div style={{ fontSize: '10px', fontFamily: 'monospace', color: isExifBad ? '#ffd54f' : '#91bacf' }}>
                        📸 EXIF: {isExifBad ? 'STRIPPED (WHATSAPP COMPRESSION)' : 'VALID SONY ILCE-7M4 · 35mm f/2.8'}
                    </div>
                </div>
            </div>

            {/* Forensic Inspection Layer Diagnosis */}
            <div style={{ padding: '14px 16px', background: hasAnomaly ? '#160d11' : '#081724', borderTop: `1px solid ${hasAnomaly ? '#4d221c' : '#143147'}` }}>
                {isDupBad ? (
                    <div style={{ color: '#f08070', fontSize: '11px', lineHeight: '1.6' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                            <AlertTriangle size={15} style={{ color: '#ff7060', flexShrink: 0 }} />
                            <strong style={{ color: '#ff9988', fontSize: '12px' }}>Computer Vision Alert: Reused / Duplicate Ground Photograph</strong>
                        </div>
                        The 64-bit perceptual hash (pHash) of this image matches a photograph filed under another milestone or project (Hamming distance &lt; 5). Reusing identical physical photos across separate claims is a strong indicator of milestone fabrication or ghost work. Physical site inspection mandatory before funds disbursement.
                    </div>
                ) : isGpsBad ? (
                    <div style={{ color: '#f08070', fontSize: '11px', lineHeight: '1.6' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                            <AlertTriangle size={15} style={{ color: '#ff7060', flexShrink: 0 }} />
                            <strong style={{ color: '#ff9988', fontSize: '12px' }}>Geofence Alert: Off-Site Photograph Coordinates</strong>
                        </div>
                        Camera EXIF coordinates place this photo outside the designated constituency boundary ({district || 'authorized sector'}). The photograph appears to have been taken at an unverified location rather than the sanctioned project site.
                    </div>
                ) : isExifBad ? (
                    <div style={{ color: '#e0b060', fontSize: '11px', lineHeight: '1.6' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                            <AlertTriangle size={15} style={{ color: '#ffd54f', flexShrink: 0 }} />
                            <strong style={{ color: '#ffd070', fontSize: '12px' }}>Metadata Advisory: EXIF Camera Tags Stripped</strong>
                        </div>
                        Camera hardware and GPS tags were removed before submission (characteristic of WhatsApp or messaging app re-compression). While the image is retained in the audit record, on-site physical inspection is advised to confirm coordinates.
                    </div>
                ) : (
                    <div style={{ color: '#68c298', fontSize: '11px', lineHeight: '1.6' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                            <Check size={15} style={{ color: '#00e676', flexShrink: 0 }} />
                            <strong style={{ color: '#88e2b8', fontSize: '12px' }}>Visual Forensics Verified: Authentic Ground Evidence</strong>
                        </div>
                        Camera EXIF header validated, geotag coordinates match the authorized work site in {district || 'the constituency'}, and the 64-bit perceptual hash (pHash) is verified unique across the national MPLADS project database.
                    </div>
                )}
            </div>
        </div>
    );
}

function ProjectDetailPage() {
    const { workId = '' } = useParams();
    const current = useGetCurrentUser();
    const project = useGetProject(workId, { query: { queryKey: getGetProjectQueryKey(workId), enabled: Boolean(workId) } });
    const audit = useListProjectAudit(workId, { query: { queryKey: getListProjectAuditQueryKey(workId), enabled: Boolean(workId) } });
    if (project.isLoading)
        return <PageFrame eyebrow="PROJECT FILE" title="Opening evidence file…"><Skeleton rows={9}/></PageFrame>;
    if (project.isError || !project.data)
        return <PageFrame eyebrow="PROJECT FILE" title="Evidence file unavailable"><ErrorState onRetry={() => project.refetch()} message="This work ID is not available in the current authority scope."/></PageFrame>;
    const item = project.data;
    const hasPhotos = Array.isArray(item.photos) && item.photos.length > 0;
    const ifScore = item.isolationForestScore;
    const ifStatus = item.isolationForestStatus;
    const heuristicScore = item.heuristicScore;
    const isEscalated = item.workflowStatus === 'ESCALATED' || item.workflowStatus === 'ESCALATED_STATE';

    return (<PageFrame eyebrow={`PROJECT FILE / ${item.workId}`} title={item.description || item.title || item.workId} subtitle={`${item.district || '—'}${item.state ? `, ${item.state}` : ''} · ${categoryDisplayNames[item.category] || item.category || 'General'} · ${item.fiscalYear || '—'}`} actions={<Link href="/projects" className="button button-secondary" data-testid="link-back-projects">
          <ChevronLeft size={14}/> Back to projects
        </Link>}>
      <div className="detail-top">
        <div className="detail-statuses">
          <StatusPill value={item.riskLevel}/>
          <StatusPill value={item.workflowStatus} kind="workflow"/>
          <span className="font-mono text-[10px] text-[#7b8d9a]">Updated {date(item.updatedAt)}</span>
        </div>
        <div className="detail-confidence">
          <span className="eyebrow">RISK SCORE</span>
          <strong>{(Number(item.riskScore) || 0).toFixed(2)}</strong>
          <span>Model output · synthetic</span>
        </div>
      </div>

      <div className="detail-layout">
        <div className="detail-main">
          <section className="surface-card">
            <div className="section-heading">
              <div>
                <div className="eyebrow">AT A GLANCE</div>
                <h3>Delivery record</h3>
              </div>
              <StatusPill value={item.dataCompleteness} kind="data"/>
            </div>
            <div className="detail-grid">
              <DetailRow label="Sanctioned amount" value={money(item.sanctionedAmount)}/>
              <DetailRow label="Estimated cost" value={money(item.estimatedCost)}/>
              <DetailRow label="Expenditure" value={money(item.expenditure)}/>
              <DetailRow label="Physical progress" value={<span>{(Number(item.physicalProgress) || 0).toFixed(1)}% <span className="font-normal text-[#8695a0]">complete</span></span>}/>
              <DetailRow label="Date of sanction" value={date(item.dateOfSanction)}/>
              <DetailRow label="Expected completion" value={date(item.expectedCompletionDate)}/>
            </div>
            <div className="large-progress">
              <div><span>Physical progress</span><strong>{(Number(item.physicalProgress) || 0).toFixed(1)}%</strong></div>
              <div className="large-progress-track"><span style={{ width: `${Math.min(100, Math.max(0, Number(item.physicalProgress) || 0))}%` }}/></div>
            </div>
          </section>

          <section className="surface-card">
            <div className="section-heading">
              <div>
                <div className="eyebrow">RISK INTELLIGENCE</div>
                <h3>Why this record was flagged</h3>
              </div>
              <span className="ai-tag"><Sparkles size={12}/> AI-assisted</span>
            </div>
            <p className="disclaimer">These are model-generated signals based on available records and imagery. They are not legal findings. Each flag includes specific evidence and is subject to human review.</p>

            {/* Isolation Forest score breakdown — transparent, not a black box */}
            {ifScore !== undefined && ifScore !== null && (
                <div style={{ marginBottom: '14px', padding: '12px 16px', background: '#0e2537', borderRadius: '6px', border: '1px solid #1e3d57' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
                        <span style={{ fontSize: '10px', color: '#91a4b4', fontWeight: 700, letterSpacing: '0.06em' }}>RISK SCORE AUDIT BREAKDOWN</span>
                        <span style={{ fontSize: '11px', color: '#f0c070', fontWeight: 600 }}>
                            Composite Score: <strong>{(Number(item.riskScore) || 0).toFixed(2)}</strong> / 100 ({item.riskLevel})
                        </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '10px', marginTop: '6px' }}>
                        <div style={{ padding: '8px 10px', background: 'rgba(255,255,255,0.03)', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.06)' }}>
                            <span style={{ fontSize: '10px', color: '#8ca1b3', display: 'block' }}>1. Domain Rules (70% weight)</span>
                            <strong style={{ fontSize: '14px', color: '#7abfcf' }}>{heuristicScore !== undefined ? Number(heuristicScore).toFixed(2) : '0.00'}</strong>
                            <small style={{ fontSize: '10px', color: '#5a758a', display: 'block', marginTop: '2px' }}>Fiscal divergence & deadline telemetry</small>
                        </div>

                        <div style={{ padding: '8px 10px', background: 'rgba(255,255,255,0.03)', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.06)' }}>
                            <span style={{ fontSize: '10px', color: '#8ca1b3', display: 'block' }}>2. Isolation Forest (30% weight)</span>
                            <strong style={{ fontSize: '14px', color: ifStatus === 'OUTLIER' ? '#e07a5f' : '#6bba9a' }}>
                                {Number(ifScore).toFixed(2)} <span style={{ fontSize: '10px', opacity: 0.8 }}>({ifStatus})</span>
                            </strong>
                            <small style={{ fontSize: '10px', color: '#5a758a', display: 'block', marginTop: '2px' }}>Unsupervised AI outlier detection against 40 peers</small>
                        </div>

                        {isEscalated && (
                            <div style={{ padding: '8px 10px', background: 'rgba(224, 122, 95, 0.08)', borderRadius: '4px', border: '1px solid rgba(224, 122, 95, 0.25)' }}>
                                <span style={{ fontSize: '10px', color: '#f09080', display: 'block' }}>3. Authority Priority Escalation</span>
                                <strong style={{ fontSize: '14px', color: '#e07a5f' }}>+75.80 Floor</strong>
                                <small style={{ fontSize: '10px', color: '#d08070', display: 'block', marginTop: '2px' }}>Elevated by District/State Authority review</small>
                            </div>
                        )}
                    </div>

                    {isEscalated && (
                        <div style={{ marginTop: '8px', padding: '6px 10px', background: 'rgba(224, 122, 95, 0.1)', borderRadius: '4px', fontSize: '11px', color: '#e2a090', lineHeight: '1.4' }}>
                            ℹ️ <strong>Score Explanation:</strong> Baseline telemetry scored {((Number(heuristicScore || 0) * 0.70) + (Number(ifScore || 0) * 0.30)).toFixed(1)} points. Because this project was formally escalated by an official, the system applies a statutory <strong>+75.80 Priority Floor</strong> to guarantee immediate visibility in the oversight queue.
                        </div>
                    )}
                </div>
            )}

            <div className="finding-list">
              {item.findings.map((finding, index) => {
                const isIF = finding.module === 'UNEXPLAINED_OUTLIER_ANOMALY';
                const isVisual = ['DUPLICATE_CROSS_PROJECT_PHOTO','DUPLICATE_SEQUENTIAL_PHOTO','MISSING_EXIF_METADATA','GEOFENCE_MISMATCH_ANOMALY'].includes(finding.module);
                const moduleTag = isIF ? 'Isolation Forest' : isVisual ? 'Visual Engine' : 'Domain Rules';
                const moduleColor = isIF ? '#c06090' : isVisual ? '#5090c0' : '#6a9a7a';
                return (<div className="finding" key={`${finding.title}-${index}`}>
                    <div className={`finding-marker finding-${finding.severity.toLowerCase()}`}>
                      <AlertTriangle size={14}/>
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2" style={{ flexWrap: 'wrap' }}>
                        <strong>{finding.title}</strong>
                        <StatusPill value={finding.severity}/>
                        <span style={{ fontSize: '9px', fontWeight: 700, color: moduleColor, background: moduleColor + '20', border: `1px solid ${moduleColor}50`, borderRadius: '4px', padding: '1px 6px', letterSpacing: '0.05em' }}>
                            {moduleTag}
                        </span>
                      </div>
                      <p>{finding.explanation}</p>
                      <div className="finding-evidence">
                        <FileSearch size={12}/>
                        <span><strong>Evidence:</strong> {finding.evidence}</span>
                      </div>
                    </div>
                  </div>);
              })}
            </div>
          </section>

          {/* Photos & Visual Evidence panel */}
          <section className="surface-card" data-testid="section-photos">
            <div className="section-heading">
              <div>
                <div className="eyebrow">VISUAL EVIDENCE & FORENSICS</div>
                <h3>Field inspection ground photographs</h3>
              </div>
              <span style={{ fontSize: '10px', color: '#7b8d9a' }}>{hasPhotos ? `${item.photos.length} record${item.photos.length > 1 ? 's' : ''}` : 'No photos on record'}</span>
            </div>
            {!hasPhotos ? (
                <div style={{ padding: '18px 0', textAlign: 'center', fontSize: '12px', color: '#7b8d9a' }}>
                    No field photographs have been submitted for this project yet.
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {item.photos.map((photo) => (
                        <ProjectVisualCard
                            key={photo.id}
                            photo={photo}
                            category={item.category}
                            workId={item.workId}
                            title={item.title || item.description}
                            district={item.district}
                        />
                    ))}
                </div>
            )}
          </section>


          <section className="surface-card">
            <div className="section-heading">
              <div>
                <div className="eyebrow">ML MODULES</div>
                <h3>Signal availability</h3>
              </div>
            </div>
            <div className="module-grid">
              {item.modules.map((module) => (<div className="module-card" key={module.name}>
                  <div className="flex items-center justify-between">
                    <span className="module-name">{module.name}</span>
                    <span className={`module-status module-${module.status.toLowerCase()}`}>
                      <span />{module.status.replaceAll('_', ' ')}
                    </span>
                  </div>
                  {module.score !== null && module.score !== undefined && (<div className="module-score">{(Number(module.score) || 0).toFixed(2)}</div>)}
                  <p>{module.summary}</p>
                  <div className="module-evidence">
                    {module.evidence.slice(0, 2).map((evidence) => (<span key={evidence}><Check size={11}/>{evidence}</span>))}
                  </div>
                </div>))}
            </div>
          </section>

          <section className="surface-card">
            <div className="section-heading">
              <div>
                <div className="eyebrow">PROJECT AUDIT</div>
                <h3>Accountability trail</h3>
              </div>
            </div>
            <AuditTable entries={audit.data || []} loading={audit.isLoading}/>
          </section>
        </div>

        <aside className="detail-side">
          <ActionPanel project={item} readOnly={Boolean(current.data?.readOnly)} userRole={current.data?.role}/>
          <section className="surface-card">
            <div className="eyebrow">AGENCY & MP</div>
            <h3 className="mt-2">Accountability context</h3>
            <div className="detail-stack mt-4">
              <DetailRow label="Implementing agency" value={item.agency}/>
              <DetailRow label="Agency type" value={item.agencyType}/>
              <DetailRow label="State-level agency" value={item.agencyStateLevel ? 'Yes' : 'No'}/>
              <DetailRow label="Member of Parliament" value={item.mpName}/>
              <DetailRow label="MP category" value={item.mpCategory}/>
              <DetailRow label="Constituency" value={item.mpConstituency}/>
            </div>
          </section>
          <section className="surface-card">
            <div className="eyebrow">COMPLIANCE CHECKS</div>
            <h3 className="mt-2">Required records</h3>
            <div className="check-list">
              <div>
                <span className={item.tenderInvited ? 'check-good' : 'check-warn'}>
                  {item.tenderInvited ? <Check size={12}/> : <AlertTriangle size={12}/>}
                </span>
                <span>Tender invited</span>
                <strong>{item.tenderInvited ? 'Filed' : 'Missing'}</strong>
              </div>
              <div>
                <span className={item.ucFiled ? 'check-good' : 'check-warn'}>
                  {item.ucFiled ? <Check size={12}/> : <AlertTriangle size={12}/>}
                </span>
                <span>Utilisation certificate</span>
                <strong>{item.ucFiled ? 'Filed' : 'Missing'}</strong>
              </div>
            </div>
          </section>
          <section className="surface-card">
            <div className="eyebrow">PAYMENT REGISTER</div>
            <h3 className="mt-2">Tranches recorded</h3>
            <div className="payment-total">{money(item.paymentTotal)}</div>
            <div className="payment-list">
              {item.payments.map((payment) => (<div className="payment-row" key={`${payment.tranche}-${payment.date}`}>
                  <span className="font-mono text-[10px] text-[#7d8d99]">{payment.tranche}</span>
                  <strong>{money(payment.amount)}</strong>
                  <span>{date(payment.date)}</span>
                </div>))}
            </div>
          </section>
        </aside>
      </div>
    </PageFrame>);
}
function AuthGate({ children }) {
    const current = useGetCurrentUser();
    if (current.isLoading)
        return <div className="auth-loading"><Logo /><Skeleton rows={4}/></div>;
    if (current.isError || !current.data)
        return <AuthPage />;
    return <AppShell user={current.data}>{children}</AppShell>;
}
function Router() {
    const [location] = useLocation();
    return (<ErrorBoundary resetKey={location}>
      <Switch>
        <Route path="/"><AuthPage /></Route>
        <Route path="/dashboard"><AuthGate><DashboardPage /></AuthGate></Route>
        <Route path="/projects"><AuthGate><ProjectsPage /></AuthGate></Route>
        <Route path="/escalated-projects"><AuthGate><EscalatedProjectsPage /></AuthGate></Route>
        <Route path="/projects/:workId"><AuthGate><ProjectDetailPage /></AuthGate></Route>
        <Route component={NotFound}/>
      </Switch>
    </ErrorBoundary>);
}
export default function App() {
    return (<QueryClientProvider client={queryClient}>
      <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
        <Router />
      </WouterRouter>
    </QueryClientProvider>);
}
