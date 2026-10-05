import { lazy, Suspense, type ComponentType } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/Layout'
import { PageLoader } from './components/ui'
import { Landing } from './pages/Landing'
import { FspAuth, Login, Register, Verify } from './pages/Auth'
import { NotFound } from './pages/NotFound'

// Разбиение бандла по маршрутам: кабинеты, графики и методика загружаются по требованию.
function page<T extends Record<string, unknown>>(loader: () => Promise<T>, name: keyof T) {
  return lazy(() => loader().then(m => ({ default: m[name] as ComponentType<any> })))
}

const Methodology = page(() => import('./pages/Methodology'), 'Methodology')
const CandidateDashboard = page(() => import('./pages/candidate/Dashboard'), 'CandidateDashboard')
const CandidateProfile = page(() => import('./pages/candidate/Profile'), 'CandidateProfile')
const Testing = page(() => import('./pages/candidate/Testing'), 'Testing')
const TestRunner = page(() => import('./pages/candidate/TestRunner'), 'TestRunner')
const GradePage = page(() => import('./pages/candidate/Grade'), 'GradePage')
const CandidateInvitations = page(() => import('./pages/candidate/Invitations'), 'CandidateInvitations')
const VacancyList = page(() => import('./pages/candidate/Vacancies'), 'VacancyList')
const VacancyDetail = page(() => import('./pages/candidate/Vacancies'), 'VacancyDetail')
const Applications = page(() => import('./pages/candidate/Applications'), 'Applications')
const CandidateTasks = page(() => import('./pages/candidate/Tasks'), 'CandidateTasks')
const CandidateSettings = page(() => import('./pages/candidate/Settings'), 'CandidateSettings')
const EmployerDashboard = page(() => import('./pages/employer/Dashboard'), 'EmployerDashboard')
const Needs = page(() => import('./pages/employer/Needs'), 'Needs')
const NeedForm = page(() => import('./pages/employer/Needs'), 'NeedForm')
const NeedDetail = page(() => import('./pages/employer/NeedDetail'), 'NeedDetail')
const Selections = page(() => import('./pages/employer/Selection'), 'Selections')
const SelectionPage = page(() => import('./pages/employer/Selection'), 'SelectionPage')
const CandidateSearch = page(() => import('./pages/employer/Search'), 'CandidateSearch')
const CandidateView = page(() => import('./pages/employer/CandidateView'), 'CandidateView')
const EmployerInvitations = page(() => import('./pages/employer/Invitations'), 'EmployerInvitations')
const Shortlist = page(() => import('./pages/employer/Shortlist'), 'Shortlist')
const EmployerTasks = page(() => import('./pages/employer/Tasks'), 'EmployerTasks')
const CompanyPage = page(() => import('./pages/employer/Company'), 'CompanyPage')
const AdminItems = page(() => import('./pages/admin/Items'), 'AdminItems')

export default function App() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-6xl p-10"><PageLoader /></div>}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/verify" element={<Verify />} />
        <Route path="/auth/fsp" element={<FspAuth />} />
        <Route path="/methodology" element={<Methodology />} />

        <Route path="/candidate" element={<AppShell role="candidate" />}>
          <Route index element={<CandidateDashboard />} />
          <Route path="profile" element={<CandidateProfile />} />
          <Route path="testing" element={<Testing />} />
          <Route path="testing/:token" element={<TestRunner />} />
          <Route path="grade" element={<GradePage />} />
          <Route path="invitations" element={<CandidateInvitations />} />
          <Route path="vacancies" element={<VacancyList />} />
          <Route path="vacancies/:id" element={<VacancyDetail />} />
          <Route path="applications" element={<Applications />} />
          <Route path="tasks" element={<CandidateTasks />} />
          <Route path="settings" element={<CandidateSettings />} />
        </Route>

        <Route path="/employer" element={<AppShell role="employer" />}>
          <Route index element={<EmployerDashboard />} />
          <Route path="needs" element={<Needs />} />
          <Route path="needs/new" element={<NeedForm />} />
          <Route path="needs/:id" element={<NeedDetail />} />
          <Route path="needs/:id/edit" element={<NeedForm />} />
          <Route path="vacancies/:id" element={<NeedDetail />} />
          <Route path="selections" element={<Selections />} />
          <Route path="selections/:id" element={<SelectionPage />} />
          <Route path="search" element={<CandidateSearch />} />
          <Route path="candidates/:id" element={<CandidateView />} />
          <Route path="invitations" element={<EmployerInvitations />} />
          <Route path="shortlist" element={<Shortlist />} />
          <Route path="tasks" element={<EmployerTasks />} />
          <Route path="company" element={<CompanyPage />} />
        </Route>

        <Route path="/admin" element={<AppShell role="admin" />}>
          <Route index element={<AdminItems />} />
        </Route>

        <Route path="/home" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}
