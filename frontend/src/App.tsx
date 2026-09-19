import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Cases from './pages/Cases'
import CaseDetail from './pages/CaseDetail'
import Policies from './pages/Policies'
import AuditPage from './pages/Audit'
import './index.css'

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/cases" element={<Cases />} />
            <Route path="/cases/:caseId" element={<CaseDetail />} />
            <Route path="/policies" element={<Policies />} />
            <Route path="/audit" element={<AuditPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
