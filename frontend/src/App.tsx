import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/Layout'
import { Landing } from './pages/Landing'
import { FspAuth, Login, Register, Verify } from './pages/Auth'
import { Methodology } from './pages/Methodology'
import { NotFound } from './pages/NotFound'
import { CandidateDashboard } from './pages/candidate/Dashboard'
import { CandidateProfile } from './pages/candidate/Profile'
import { Testing } from './pages/candidate/Testing'
import { TestRunner } from './pages/candidate/TestRunner'
import { GradePage } from './pages/candidate/Grade'
import { CandidateInvitations } from './pages/candidate/Invitations'
import { VacancyDetail, VacancyList } from './pages/candidate/Vacancies'
import { Applications } from './pages/candidate/Applications'
import { CandidateTasks } from './pages/candidate/Tasks'
import { CandidateSettings } from './pages/candidate/Settings'
import { EmployerDashboard } from './pages/employer/Dashboard'
import { NeedForm, Needs } from './pages/employer/Needs'
import { NeedDetail } from './pages/employer/NeedDetail'
import { SelectionPage, Selections } from './pages/employer/Selection'
import { CandidateSearch } from './pages/employer/Search'
import { CandidateView } from './pages/employer/CandidateView'
import { EmployerInvitations } from './pages/employer/Invitations'
import { Shortlist } from './pages/employer/Shortlist'
import { EmployerTasks } from './pages/employer/Tasks'
import { CompanyPage } from './pages/employer/Company'
import { AdminItems } from './pages/admin/Items'

export default function App() {
  return (
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
  )
}
